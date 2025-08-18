import typing
from pathlib import Path

import pytest

if typing.TYPE_CHECKING:
    from sqlglot.dialects.dialect import DialectType

    from agent_platform.core.data_frames.data_frames import PlatformDataFrame


def verify_safe_select(sql: str, dialect: "DialectType | None" = None) -> None:
    """
    Check if the sql is a safe select statement (we just want to read, not write data).
    """
    import sqlglot  # That's what ibis uses to parse the sql internally.

    expressions = sqlglot.parse(sql, dialect=dialect)

    for expr in expressions:
        assert expr is not None, f"Expected expression, got: {expr}"
        assert hasattr(expr, "key"), f"Expected expression with key, got: {expr}"
        if expr.key != "select":
            raise ValueError(f"SQL is not a SELECT statement: {sql}. Found: {expr.key}")


def test_is_safe_select():
    verify_safe_select("SELECT * FROM table", dialect="postgres")
    verify_safe_select("SELECT * FROM table", dialect="sqlite")
    verify_safe_select("SELECT * FROM table WHERE condition")
    verify_safe_select("SELECT * FROM table WHERE condition LIMIT 10")
    verify_safe_select("SELECT * FROM table WHERE condition LIMIT 10 OFFSET 5")
    verify_safe_select("SELECT * FROM table WHERE condition LIMIT 10 OFFSET 5")

    with pytest.raises(ValueError, match=".*Found: insert.*"):
        verify_safe_select("SELECT * FROM table; INSERT INTO table (column) VALUES (value)")
    with pytest.raises(ValueError, match=".*Found: update.*"):
        verify_safe_select("UPDATE table SET column = value WHERE condition; SELECT * FROM table")
    with pytest.raises(ValueError, match=".*Found: delete.*"):
        verify_safe_select(
            "SELECT * FROM table; DELETE FROM table WHERE condition; SELECT * FROM table"
        )
    with pytest.raises(ValueError, match=".*Found: drop.*"):
        verify_safe_select("DROP TABLE table")
    with pytest.raises(ValueError, match=".*Found: alter.*"):
        verify_safe_select("ALTER TABLE table ADD COLUMN column TEXT")
    with pytest.raises(ValueError, match=".*Found: alter.*"):
        verify_safe_select("ALTER TABLE table DROP COLUMN column")


def create_sqlite_database(db_path: Path):
    import sqlite3

    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE mytable (user_id INTEGER, mycolumn TEXT)")
    conn.execute("INSERT INTO mytable (user_id, mycolumn) VALUES (1, 'London')")
    conn.execute("INSERT INTO mytable (user_id, mycolumn) VALUES (2, 'Paris')")
    conn.execute("INSERT INTO mytable (user_id, mycolumn) VALUES (3, 'Berlin')")

    conn.execute("CREATE TABLE other_table (user_id INTEGER, other_column TEXT)")
    conn.execute("INSERT INTO other_table (user_id, other_column) VALUES (1, 'A')")
    conn.execute("INSERT INTO other_table (user_id, other_column) VALUES (2, 'B')")
    conn.execute("INSERT INTO other_table (user_id, other_column) VALUES (3, 'C')")
    conn.commit()
    conn.close()


def test_ibis_database_connection(datadir: Path):
    """
    This is a unit test just to check the capabilities of ibis connecting
    to a database and creating data frames from it.
    """
    import ibis

    sqlite_db_path = datadir / "input2.db"
    create_sqlite_database(sqlite_db_path)

    con = ibis.sqlite.connect(sqlite_db_path)
    df = con.sql("SELECT * FROM mytable")  # i.e.: a previous generated data frame
    df2 = con.sql("SELECT * FROM other_table")  # i.e.: another previous generated data frame

    # After having created data frames, to keep in the "SQL" world (as opposed to
    # the "python" world where we could filter it doing df.filter(...)),
    # apparently the trick is to create the sql by hand referencing those as
    # their SQL.
    # i.e.:
    sql = f"""
    -- This is a preamble that the framework would need to do automatically.
    WITH df AS (
    {con.compile(df)}
    ),
    df2 AS (
    {con.compile(df2)}
    )
    -- This would be the actual computation given by the LLM/user.
    SELECT
    df.user_id,
    df.mycolumn,
    df2.other_column
    FROM df
    LEFT JOIN df2
    ON df.user_id = df2.user_id
    """

    verify_safe_select(sql)  # just check our validation works
    joined = con.sql(sql)

    # In theory, the computation only happens here!
    # This means that we can do computations on the data frames without
    # materializing them in the python world.
    assert joined.to_pandas().to_dict(orient="records") == [
        {"user_id": 1, "mycolumn": "London", "other_column": "A"},
        {"user_id": 2, "mycolumn": "Paris", "other_column": "B"},
        {"user_id": 3, "mycolumn": "Berlin", "other_column": "C"},
    ]


def test_ibis_pandas_computation(datadir: Path):
    """
    This is a unit test just to check the capabilities of ibis connecting
    to a database or with in-memory data frames (pyarrow).
    """
    # Create a sqlite database with a table

    import ibis
    import pyarrow

    sqlite_db_path = datadir / "input2.db"

    create_sqlite_database(sqlite_db_path)

    pyarrow_df = pyarrow.Table.from_pydict({"user_id": [1, 2, 3], "value": [100, 200, 300]})

    # We can run the sql as needed.
    sql_statement = "SELECT user_id, other_column FROM other_table"
    verify_safe_select(sql_statement, dialect="sqlite")

    # Extract information from the sqlite database (we need to know the dialect as well
    # as the connection information).
    sqlite_con = ibis.sqlite.connect(sqlite_db_path)
    # We can pass an input dialect to be converted to the output dialect (backend-specific).
    result = sqlite_con.sql(sql_statement, dialect="sqlite")

    # Note: we cannot do computations with ibis through different backends
    # (so, we always need to "materialize" the data frames if more than one
    # data frame is used)
    # If this isn't done, we'd have an error such as:
    # ibis.common.exceptions.IbisError: Multiple backends found for this expression

    # We can create a table from an in-memory dataframe using duckdb as the backend
    con = ibis.duckdb.connect()
    con.create_table("input1", pyarrow_df)
    con.create_table("input2", result.to_pyarrow())

    # 3. Example: inner join on 'user_id'
    duckdb_sql = """SELECT
        "input1"."user_id",
        "input1"."value",
        "input2"."other_column"
    FROM "input1" AS "input1"
    INNER JOIN "input2" AS "input2"
        ON "input1"."user_id" = "input2"."user_id"
    """
    expr = con.sql(duckdb_sql)

    result_table = expr.to_pyarrow()  # pyarrow table

    assert result_table.to_pylist() == [
        {"user_id": 1, "value": 100, "other_column": "A"},
        {"user_id": 2, "value": 200, "other_column": "B"},
        {"user_id": 3, "value": 300, "other_column": "C"},
    ]


class _UserStub:
    def __init__(self):
        from uuid import uuid4

        self.user_id = str(uuid4())


class _ThreadStub:
    def __init__(self):
        from uuid import uuid4

        self.tid = str(uuid4())
        self.agent_id = str(uuid4())
        self.user = _UserStub()


class _StorageStub:
    def __init__(self):
        from agent_platform.core.data_frames.data_frames import PlatformDataFrame

        self.thread = _ThreadStub()
        self.data_frames: list[PlatformDataFrame] = []

    async def get_thread(self, user_id: str, tid: str) -> _ThreadStub:
        assert tid == self.thread.tid
        return self.thread

    async def list_data_frames(self, tid: str) -> "list[PlatformDataFrame]":
        assert tid == self.thread.tid
        return self.data_frames

    async def save_data_frame(self, data_frame: "PlatformDataFrame") -> None:
        self.data_frames.append(data_frame)

    async def create_in_memory_data_frame(self, name: str, contents: dict[str, list]):
        import datetime
        import io
        from uuid import uuid4

        import pyarrow.parquet

        from agent_platform.core.data_frames.data_frames import PlatformDataFrame

        pyarrow_df = pyarrow.Table.from_pydict(contents)

        stream = io.BytesIO()
        pyarrow.parquet.write_table(pyarrow_df, stream)

        self.data_frames.append(
            PlatformDataFrame(
                data_frame_id=str(uuid4()),
                name=name,
                user_id=self.thread.user.user_id,
                agent_id=self.thread.agent_id,
                thread_id=self.thread.tid,
                num_rows=pyarrow_df.shape[0],
                num_columns=pyarrow_df.shape[1],
                column_headers=list(pyarrow_df.schema.names),
                input_id_type="in_memory",
                created_at=datetime.datetime.now(datetime.UTC),
                parquet_contents=stream.getvalue(),
                computation_input_sources={},
            )
        )


@pytest.mark.asyncio
async def test_create_data_frame_from_sql_computation():
    from agent_platform.server.auth import AuthedUser
    from agent_platform.server.data_frames.data_frames_from_computation import (
        create_data_frame_from_sql_computation,
    )
    from agent_platform.server.data_frames.data_frames_kernel import DataFramesKernel
    from agent_platform.server.storage.base import BaseStorage

    storage_stub = _StorageStub()
    tid = storage_stub.thread.tid

    await storage_stub.create_in_memory_data_frame(
        name="in_memory_data_frame", contents={"col1": [1, 2, 3], "col2": [4, 5, 6]}
    )

    new_data_frame_name = "test_data_frame"
    sql_query = "SELECT * FROM in_memory_data_frame WHERE col1 <= 2"
    description = "Test data frame"

    base_storage = typing.cast(BaseStorage, storage_stub)
    user = typing.cast(AuthedUser, storage_stub.thread.user)

    result = await create_data_frame_from_sql_computation(
        DataFramesKernel(base_storage, user, tid),
        base_storage,
        new_data_frame_name,
        sql_query,
        dialect="duckdb",
        description=description,
    )

    assert result.platform_data_frame.name == new_data_frame_name
    assert storage_stub.data_frames[-1].name == new_data_frame_name

    assert result.platform_data_frame.num_rows == 2
    assert result.platform_data_frame.column_headers == ["col1", "col2"]
    assert result.platform_data_frame.sql_dialect == "duckdb"

    # Now, create a new computation that uses the previous one as a source
    new_data_frame_name = "test_data_frame_2"
    sql_query = "SELECT * FROM test_data_frame WHERE col1 <= 1"
    description = "Test data frame 2"

    result = await create_data_frame_from_sql_computation(
        DataFramesKernel(base_storage, user, tid),
        base_storage,
        new_data_frame_name,
        sql_query,
        dialect="postgres",
        description=description,
    )

    assert result.platform_data_frame.name == new_data_frame_name
    assert storage_stub.data_frames[-1].name == new_data_frame_name

    assert result.platform_data_frame.num_rows == 1
    assert result.platform_data_frame.sql_dialect == "postgres"
