import json
import typing
from pathlib import Path

import pytest

from agent_platform.core.errors.base import PlatformError
from server.tests.storage_fixtures import *  # noqa: F403

if typing.TYPE_CHECKING:
    from sqlglot.dialects.dialect import DialectType

    from agent_platform.core.payloads.data_connection import DataConnectionsInspectResponse
    from agent_platform.core.payloads.semantic_data_model_payloads import (
        GenerateSemanticDataModelResponse,
        TableInfo,
    )
    from agent_platform.server.data_frames.data_frames_kernel import DataFramesKernel
    from agent_platform.server.data_frames.data_node import DataNodeResult
    from agent_platform.server.storage.sqlite import SQLiteStorage


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


@pytest.mark.asyncio
async def test_create_data_frame_from_sql_computation():  # noqa: PLR0915
    import io

    import pyarrow.parquet as pq
    from tests.data_frames.fixtures import StorageStub

    from agent_platform.server.auth import AuthedUser
    from agent_platform.server.data_frames.data_frames_from_computation import (
        create_data_frame_from_sql_computation_api,
    )
    from agent_platform.server.data_frames.data_frames_kernel import DataFramesKernel
    from agent_platform.server.storage.base import BaseStorage

    storage_stub = StorageStub()
    tid = storage_stub.thread.tid

    await storage_stub.create_in_memory_data_frame(
        name="in_memory_data_frame", contents={"col1": [1, 2, 3], "col2": [4, 5, 6]}
    )

    new_data_frame_name = "test_data_frame"
    sql_query = "SELECT * FROM in_memory_data_frame WHERE col1 <= 2"
    description = "Test data frame"

    base_storage = typing.cast(BaseStorage, storage_stub)
    user = typing.cast(AuthedUser, storage_stub.thread.user)

    result, sliced_data = await create_data_frame_from_sql_computation_api(
        DataFramesKernel(base_storage, user, tid),
        base_storage,
        new_data_frame_name,
        sql_query,
        dialect="duckdb",
        description=description,
        num_samples=1,
    )

    assert sliced_data.rows == [[1, 4]]  # First row only

    assert result.platform_data_frame.name == new_data_frame_name
    assert result.platform_data_frame.sample_rows == [[1, 4], [2, 5]]
    assert storage_stub.data_frames[-1].name == new_data_frame_name

    assert result.platform_data_frame.num_rows == 2
    assert result.platform_data_frame.column_headers == ["col1", "col2"]
    assert result.platform_data_frame.sql_dialect == "duckdb"

    loaded = json.loads(typing.cast(bytes, result.slice(offset=0, limit=1, output_format="json")))
    assert loaded == [{"col1": 1, "col2": 4}]

    loaded = json.loads(typing.cast(bytes, result.slice(offset=0, limit=2, output_format="json")))
    assert loaded == [{"col1": 1, "col2": 4}, {"col1": 2, "col2": 5}]

    loaded = json.loads(
        typing.cast(
            bytes, result.slice(offset=0, limit=2, output_format="json", column_names=["col1"])
        )
    )
    assert loaded == [{"col1": 1}, {"col1": 2}]

    loaded = json.loads(
        typing.cast(
            bytes,
            result.slice(
                offset=0,
                limit=2,
                output_format="json",
                column_names=["col1"],
                order_by="-col1",
            ),
        )
    )
    assert loaded == [{"col1": 2}, {"col1": 1}]

    loaded = json.loads(
        typing.cast(
            bytes,
            result.slice(
                offset=0,
                limit=2,
                output_format="json",
                column_names=["col1"],
                order_by="col1",
            ),
        )
    )
    assert loaded == [{"col1": 1}, {"col1": 2}]

    as_parquet = typing.cast(
        bytes, result.slice(offset=0, limit=2, output_format="parquet", column_names=["col1"])
    )

    table = pq.read_table(io.BytesIO(as_parquet))
    assert table.column_names == ["col1"]
    assert table.to_pylist() == [{"col1": 1}, {"col1": 2}]

    # Now, create a new computation that uses the previous one as a source
    new_data_frame_name = "test_data_frame_2"
    sql_query = "SELECT * FROM test_data_frame WHERE col1 <= 1"
    description = "Test data frame 2"

    result, sliced_data = await create_data_frame_from_sql_computation_api(
        DataFramesKernel(base_storage, user, tid),
        base_storage,
        new_data_frame_name,
        sql_query,
        dialect="postgres",
        description=description,
    )

    assert sliced_data.rows == []  # No rows requested

    assert result.platform_data_frame.name == new_data_frame_name
    assert result.platform_data_frame.sample_rows == [[1, 4]]
    assert storage_stub.data_frames[-1].name == new_data_frame_name

    assert result.platform_data_frame.num_rows == 1
    assert result.platform_data_frame.sql_dialect == "postgres"

    loaded = json.loads(typing.cast(bytes, result.slice(offset=0, limit=1, output_format="json")))
    assert loaded == [{"col1": 1, "col2": 4}]

    loaded = json.loads(typing.cast(bytes, result.slice(offset=0, limit=2, output_format="json")))
    # Still same (we only have one row in this query)
    assert loaded == [{"col1": 1, "col2": 4}]


def _read_from_excel_as_parquet(file_path: Path) -> bytes:
    import io

    import pyarrow
    import pyarrow.parquet as pq

    from agent_platform.server.data_frames.data_reader import ExcelDataReader

    file_bytes = file_path.read_bytes()
    reader = ExcelDataReader(file_bytes, sheet_name="Sheet1")
    assert reader.has_multiple_sheets() is False
    sheet = next(reader.iter_sheets())
    assert sheet.name == "Sheet1"
    assert sheet.num_columns == 16

    as_ibis = sheet.to_ibis()

    # Convert pyarrow.lib.RecordBatch to Table, then to parquet format in-memory
    buffer = io.BytesIO()
    table = pyarrow.Table.from_batches([as_ibis])
    pq.write_table(table, buffer)
    return buffer.getvalue()


def _read_from_csv_as_parquet(file_path: Path) -> bytes:
    import io

    import pyarrow
    import pyarrow.parquet as pq

    from agent_platform.server.data_frames.data_reader import CsvDataReader

    file_bytes = file_path.read_bytes()
    reader = CsvDataReader(file_bytes)
    assert reader.has_multiple_sheets() is False
    sheet = next(reader.iter_sheets())
    assert sheet.name is None

    as_ibis = sheet.to_ibis()

    # Convert pyarrow.Table or pyarrow.RecordBatch to Table, then to parquet format in-memory
    if isinstance(as_ibis, pyarrow.Table):
        table = as_ibis
    else:
        table = pyarrow.Table.from_batches([as_ibis])
    buffer = io.BytesIO()
    pq.write_table(table, buffer)
    return buffer.getvalue()


@pytest.mark.asyncio
async def test_create_data_frame_from_sql_computation_with_null_data_csv(
    datadir: Path, file_regression, tmp_path: Path
):
    from sema4ai.actions import Table
    from tests.data_frames.fixtures import StorageStub

    from agent_platform.server.auth.handlers import AuthedUser
    from agent_platform.server.data_frames.data_frames_from_computation import (
        create_data_frame_from_sql_computation_api,
    )
    from agent_platform.server.data_frames.data_frames_kernel import DataFramesKernel
    from agent_platform.server.storage.base import BaseStorage

    storage_stub = StorageStub()
    tid = storage_stub.thread.tid

    parquet_contents = _read_from_csv_as_parquet(datadir / "example.csv")

    await storage_stub.create_in_memory_data_frame_from_parquet_contents(
        name="in_memory_data_frame", contents=parquet_contents
    )

    new_data_frame_name = "test_data_frame"
    sql_query = "SELECT * FROM in_memory_data_frame"
    description = "Test data frame"

    base_storage = typing.cast(BaseStorage, storage_stub)
    user = typing.cast(AuthedUser, storage_stub.thread.user)

    data_node, _sliced_data = await create_data_frame_from_sql_computation_api(
        DataFramesKernel(base_storage, user, tid),
        base_storage,
        new_data_frame_name,
        sql_query,
        dialect="duckdb",
        description=description,
    )
    sliced = typing.cast(Table, data_node.slice(offset=0, limit=1, output_format="table"))
    file_regression.check(json.dumps(sliced.model_dump(), indent=2), basename="sliced-table-csv")

    data_node.list_sample_rows(num_samples=2)

    sliced_json = typing.cast(bytes, data_node.slice(offset=0, limit=1, output_format="json"))

    file_regression.check(sliced_json.decode("utf-8"), basename="sliced-json-csv")


@pytest.mark.asyncio
async def test_create_data_frame_from_sql_computation_with_dates(datadir: Path, file_regression):
    from sema4ai.actions import Table
    from tests.data_frames.fixtures import StorageStub

    from agent_platform.server.auth.handlers import AuthedUser
    from agent_platform.server.data_frames.data_frames_from_computation import (
        create_data_frame_from_sql_computation_api,
    )
    from agent_platform.server.data_frames.data_frames_kernel import DataFramesKernel
    from agent_platform.server.storage.base import BaseStorage

    storage_stub = StorageStub()
    tid = storage_stub.thread.tid

    parquet_contents = _read_from_excel_as_parquet(datadir / "example.ods")

    await storage_stub.create_in_memory_data_frame_from_parquet_contents(
        name="in_memory_data_frame", contents=parquet_contents
    )

    new_data_frame_name = "test_data_frame"
    sql_query = "SELECT * FROM in_memory_data_frame"
    description = "Test data frame"

    base_storage = typing.cast(BaseStorage, storage_stub)
    user = typing.cast(AuthedUser, storage_stub.thread.user)

    data_node, _sliced_data = await create_data_frame_from_sql_computation_api(
        DataFramesKernel(base_storage, user, tid),
        base_storage,
        new_data_frame_name,
        sql_query,
        dialect="duckdb",
        description=description,
    )
    sliced = typing.cast(Table, data_node.slice(offset=0, limit=1, output_format="table"))
    file_regression.check(json.dumps(sliced.model_dump(), indent=2), basename="sliced-table")

    data_node.list_sample_rows(num_samples=2)

    sliced_json = typing.cast(bytes, data_node.slice(offset=0, limit=1, output_format="json"))

    file_regression.check(sliced_json.decode("utf-8"), basename="sliced-json")


@pytest.mark.asyncio
async def test_create_data_frame_from_sql_computation_with_cte(file_regression):
    from sema4ai.actions import Table
    from tests.data_frames.fixtures import StorageStub

    from agent_platform.server.auth import AuthedUser
    from agent_platform.server.data_frames.data_frames_from_computation import (
        create_data_frame_from_sql_computation_api,
    )
    from agent_platform.server.data_frames.data_frames_kernel import DataFramesKernel
    from agent_platform.server.storage.base import BaseStorage

    storage_stub = StorageStub()
    tid = storage_stub.thread.tid

    await storage_stub.create_in_memory_data_frame(
        name="in_memory_data_frame1", contents={"col1": [1, 2, 3], "col2": [4, 5, 6]}
    )
    await storage_stub.create_in_memory_data_frame(
        name="in_memory_data_frame2", contents={"col1": [1, 2, 3], "col3": [7, 8, 9]}
    )

    new_data_frame_name = "test_data_frame"
    sql_query = """
    WITH cte AS (
        SELECT * FROM in_memory_data_frame1
        WHERE col1 <= 2
    ),
    cte2 AS (
        SELECT * FROM in_memory_data_frame2
        WHERE col1 <= 2
    )
    SELECT cte.col1, cte.col2, cte2.col3
    FROM cte
    JOIN cte2 ON cte.col1 = cte2.col1
    """
    description = "Test data frame"

    base_storage = typing.cast(BaseStorage, storage_stub)
    user = typing.cast(AuthedUser, storage_stub.thread.user)

    result, _sliced_data = await create_data_frame_from_sql_computation_api(
        DataFramesKernel(base_storage, user, tid),
        base_storage,
        new_data_frame_name,
        sql_query,
        dialect="duckdb",
        description=description,
    )

    sliced_table = typing.cast(Table, result.slice(offset=0, limit=1, output_format="table"))
    file_regression.check(
        json.dumps(sliced_table.model_dump(), indent=2), basename="sliced-table-cte"
    )

    # Now do a new cte on top of the previous one
    new_data_frame_name = "test_data_frame_2"
    sql_query = """
    WITH cte AS (
        SELECT * FROM test_data_frame
        WHERE col1 <= 1
    )
    SELECT * FROM cte
    """
    description = "Test data frame 2"

    result, _sliced_data = await create_data_frame_from_sql_computation_api(
        DataFramesKernel(base_storage, user, tid),
        base_storage,
        new_data_frame_name,
        sql_query,
        dialect="duckdb",
        description=description,
    )

    sliced_table = typing.cast(Table, result.slice(offset=0, limit=1, output_format="table"))
    file_regression.check(
        json.dumps(sliced_table.model_dump(), indent=2), basename="sliced-table-cte-2"
    )


class _DataFramesChecker:
    def __init__(self, sqlite_storage: "SQLiteStorage", tmpdir: Path):
        from server.tests.storage.sample_model_creator import SampleModelCreator

        self.sqlite_storage = sqlite_storage
        self.tmpdir = tmpdir

        self.model_creator = SampleModelCreator(sqlite_storage, tmpdir)

    async def setup(self):
        from agent_platform.server.auth.handlers import AuthedUser, User

        await self.model_creator.setup()

        # Setup user and thread
        user_id = await self.model_creator.get_user_id()
        self.user = typing.cast(AuthedUser, User(user_id=user_id, sub=""))
        self.agent = await self.model_creator.obtain_sample_agent()
        self.thread = await self.model_creator.obtain_sample_thread()
        self.tid = self.thread.thread_id

    def convert_inspect_response_to_tables_info(
        self,
        inspect_response: "DataConnectionsInspectResponse",
    ) -> "list[TableInfo]":
        from agent_platform.core.payloads.semantic_data_model_payloads import (
            ColumnInfo,
            TableInfo,
        )

        tables_info: list[TableInfo] = []
        for table in inspect_response.tables:
            columns: list[ColumnInfo] = []
            for column in table.columns:
                columns.append(
                    ColumnInfo(
                        name=column.name,
                        data_type=column.data_type,
                        sample_values=column.sample_values,
                    )
                )
            tables_info.append(
                TableInfo(
                    name=table.name,
                    columns=columns,
                    database=table.database,
                    schema=table.schema,
                    description=table.description,
                )
            )
        return tables_info

    async def inspect_data_connection(
        self, data_connection_id: str
    ) -> "DataConnectionsInspectResponse":
        from agent_platform.core.payloads.data_connection import DataConnectionsInspectRequest
        from agent_platform.server.api.private_v2.data_connections import inspect_data_connection

        inspect_response = await inspect_data_connection(
            connection_id=data_connection_id,
            request=DataConnectionsInspectRequest(
                tables_to_inspect=None,
                inspect_columns=True,
                n_sample_rows=5,
            ),
            user=self.user,
            storage=self.model_creator.storage,
        )

        return inspect_response

    async def generate_semantic_data_model(
        self, tables_info: "list[TableInfo]", data_connection_id: str, agent_id: str | None = None
    ) -> "GenerateSemanticDataModelResponse":
        from agent_platform.core.payloads.semantic_data_model_payloads import (
            DataConnectionInfo,
            GenerateSemanticDataModelPayload,
        )
        from agent_platform.server.api.private_v2.semantic_data_model_api import (
            generate_semantic_data_model,
        )

        # Generate the semantic data model
        generated_model = await generate_semantic_data_model(
            payload=GenerateSemanticDataModelPayload(
                name="generated_semantic_model",
                description="A generated semantic model for testing",
                data_connections_info=[
                    DataConnectionInfo(
                        data_connection_id=data_connection_id,
                        tables_info=tables_info,
                    )
                ],
                files_info=[],
                agent_id=agent_id,
            ),
            user=self.user,
            storage=self.model_creator.storage,
        )

        return generated_model

    def create_data_frames_kernel(self) -> "DataFramesKernel":
        from agent_platform.server.data_frames.data_frames_kernel import DataFramesKernel

        return DataFramesKernel(self.model_creator.storage, self.user, self.tid)

    async def create_data_frame_from_sql_computation_api(
        self, name: str, sql_query: str, description: str, dialect: str = "duckdb"
    ) -> "DataNodeResult":
        from agent_platform.server.data_frames.data_frames_from_computation import (
            create_data_frame_from_sql_computation_api,
        )

        result, _sliced_data = await create_data_frame_from_sql_computation_api(
            self.create_data_frames_kernel(),
            self.model_creator.storage,
            name,
            sql_query,
            dialect=dialect,
            description=description,
        )
        return result


@pytest.fixture
async def dfs_checker(sqlite_storage, tmpdir):
    ret = _DataFramesChecker(sqlite_storage, tmpdir)
    await ret.setup()
    return ret


@pytest.mark.asyncio
async def __manual_test_inspect_manual_postgres_data_connection(
    file_regression, dfs_checker: _DataFramesChecker, resources_dir
):
    """
    This is a manual test to be used to inspect some connection by
    manually changing the settings of the database to connect to.
    """
    from uuid import uuid4

    from agent_platform.core.data_connections.data_connections import DataConnection
    from agent_platform.core.payloads.data_connection import PostgresDataConnectionConfiguration

    data_connection = DataConnection(
        id=str(uuid4()),
        name="test_connection",
        description="Test data connection: test_connection",
        engine="postgres",
        configuration=PostgresDataConnectionConfiguration(
            host="localhost",
            port=5432,
            database="dvd_rental",
            user="xxx",
            password="xxx",
        ),
        external_id=None,
        created_at=None,
        updated_at=None,
    )

    await dfs_checker.model_creator.storage.set_data_connection(data_connection)

    inspect_response = await dfs_checker.inspect_data_connection(data_connection.id)

    tables_info = dfs_checker.convert_inspect_response_to_tables_info(inspect_response)

    generated_model = await dfs_checker.generate_semantic_data_model(
        tables_info=tables_info,
        data_connection_id=data_connection.id,
    )
    assert generated_model.semantic_model is not None


@pytest.mark.parametrize("raise_error", [True, False])
@pytest.mark.asyncio
async def test_create_data_frame_from_sql_computation_with_semantic_data_model(
    file_regression, dfs_checker: _DataFramesChecker, resources_dir, monkeypatch, raise_error
):
    from sema4ai.actions import Table

    from agent_platform.server.kernel.data_connection_inspector import DataConnectionInspector

    # Create a data connection and a semantic data model
    db_file_path = resources_dir / "data_frames" / "combined_data.sqlite"
    data_connection = await dfs_checker.model_creator.obtain_sample_data_connection(
        db_file_path=db_file_path
    )

    raised_error = False

    if raise_error:

        def _raise_error(self, *args, **kwargs):
            nonlocal raised_error
            raised_error = True
            raise Exception("Expected test error")

        monkeypatch.setattr(
            DataConnectionInspector,
            "_select_with_limit",
            _raise_error,
        )

    inspect_response = await dfs_checker.inspect_data_connection(data_connection.id)
    if raise_error:
        assert raised_error, "Expected error to be raised when inspecting the data connection"

    tables_info = dfs_checker.convert_inspect_response_to_tables_info(inspect_response)

    generated_model = await dfs_checker.generate_semantic_data_model(
        tables_info=tables_info,
        data_connection_id=data_connection.id,
    )

    # Ok, a basic model was created, let's change the logical name of the table
    tables = generated_model.semantic_model.get("tables", [])
    if not tables:
        raise Exception("No tables found in the semantic data model")
    for table in tables:
        name = table.get("name")
        if not name:
            raise Exception("No name found in the table")

        if name == "artificial_intelligence_number_training_datapoints":
            table["name"] = "ai_training_datapoints"

    semantic_data_model_id = await dfs_checker.model_creator.storage.set_semantic_data_model(
        semantic_data_model_id=None,
        semantic_model=generated_model.semantic_model,
        data_connection_ids=[data_connection.id],
        file_references=[],
    )

    # Assign the semantic data model to the agent
    await dfs_checker.model_creator.storage.set_agent_semantic_data_models(
        agent_id=dfs_checker.agent.agent_id,
        semantic_data_model_ids=[semantic_data_model_id],
    )

    result = await dfs_checker.create_data_frame_from_sql_computation_api(
        "test_data_frame",
        "SELECT * FROM ai_training_datapoints",
        description="Test data frame",
    )

    sliced_table = typing.cast(Table, result.slice(offset=0, limit=10, output_format="table"))
    file_regression.check(
        json.dumps(sliced_table.model_dump(), indent=2), basename="sliced-table-semantic-data-model"
    )


async def check(
    sql_query,
    file_regression,
    *,
    dialect: str = "duckdb",
    create_data_frames: dict[str, dict] | None = None,
):
    """
    Check that the sql query can be executed and that the result is as expected.
    Args:
        create_data_frames: dict[str, dict]
            A dictionary of data frames to create. The key is the name of the data frame and the
            value is a dictionary of column name to column values.
    """
    from sema4ai.actions import Table
    from tests.data_frames.fixtures import StorageStub

    from agent_platform.server.auth import AuthedUser
    from agent_platform.server.data_frames.data_frames_from_computation import (
        create_data_frame_from_sql_computation_api,
    )
    from agent_platform.server.data_frames.data_frames_kernel import DataFramesKernel
    from agent_platform.server.storage.base import BaseStorage

    storage_stub = StorageStub()
    tid = storage_stub.thread.tid

    if create_data_frames is not None:
        for name, contents in create_data_frames.items():
            await storage_stub.create_in_memory_data_frame(name=name, contents=contents)

    new_data_frame_name = "test_data_frame"
    description = "Test data frame"

    base_storage = typing.cast(BaseStorage, storage_stub)
    user = typing.cast(AuthedUser, storage_stub.thread.user)

    result, _sliced_data = await create_data_frame_from_sql_computation_api(
        DataFramesKernel(base_storage, user, tid),
        base_storage,
        new_data_frame_name,
        sql_query,
        dialect=dialect,
        description=description,
    )

    sliced_table = typing.cast(Table, result.slice(offset=0, limit=10, output_format="table"))
    file_regression.check(json.dumps(sliced_table.model_dump(), indent=2))


@pytest.mark.asyncio
async def test_create_data_frame_no_input(file_regression):
    await check("SELECT 1", file_regression)


@pytest.mark.asyncio
async def test_create_data_frame_from_values(file_regression):
    await check("SELECT * FROM (VALUES (1), (2)) AS v(x)", file_regression)


@pytest.mark.asyncio
async def test_create_data_frame_from_func(file_regression):
    await check("SELECT * FROM generate_series(1, 3) AS g(i)", file_regression)


@pytest.mark.asyncio
async def test_create_data_frame_from_unnest(file_regression):
    await check("SELECT * FROM UNNEST([1, 2, 3]) AS u", file_regression)


@pytest.mark.asyncio
async def test_create_data_frame_union(file_regression):
    await check(
        """
SELECT * FROM a
UNION ALL
SELECT * FROM b""",
        file_regression,
        create_data_frames={"a": {"col1": [1, 2, 3]}, "b": {"col1": [4, 5, 6]}},
    )


@pytest.mark.asyncio
async def test_create_data_frame_scope_alias(file_regression):
    # This fails in duckdb: it cannot deal with this structure (but we do go on to execute it)
    with pytest.raises(PlatformError, match="Catalog Error: Table with name w does not exist!"):
        await check(
            """
SELECT * FROM w
WHERE EXISTS (
  WITH w AS (SELECT 1)
  SELECT 1
)""",
            file_regression,
        )


@pytest.mark.asyncio
async def test_create_data_frame_from_wrapper(file_regression):
    # This fails at parsing
    with pytest.raises(PlatformError, match="Parser Error: syntax error at or near"):
        await check(
            "SELECT * FROM TABLE(generator(rowcount => 10))", file_regression, dialect="snowflake"
        )


@pytest.mark.asyncio
async def test_create_data_frame_from_dual(file_regression):
    # Currently this fails in our part... we could make it go a bit forward
    # and ignore that table, but then it'll fail just a bit later as duckdb doesn't support it.
    with pytest.raises(PlatformError, match="not found"):
        await check("SELECT 1 FROM DUAL", file_regression, dialect="oracle")
