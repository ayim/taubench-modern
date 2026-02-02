"""SQLite foreign key inspector implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from structlog import get_logger

from agent_platform.server.dialect.foreign_key_inspector_base import ForeignKeyInspector
from agent_platform.server.dialect.types import ConstraintData
from agent_platform.server.kernel.ibis import AsyncIbisConnection, AsyncSqliteConnection

if TYPE_CHECKING:
    import pandas

    from agent_platform.core.payloads.data_connection import (
        ForeignKeyInfo,
        TableToInspect,
    )

logger = get_logger(__name__)


async def _cursor_to_dataframe(connection: AsyncSqliteConnection, query: str) -> pandas.DataFrame:
    """Execute a query via raw_sql and convert the cursor result to a DataFrame.

    This is needed for SQLite PRAGMA queries which can't go through ibis.sql()
    because ibis wraps queries in CREATE TEMPORARY VIEW which fails for PRAGMA.

    Args:
        connection: The async ibis connection
        query: SQL query to execute

    Returns:
        pandas DataFrame with query results
    """
    import pandas

    cursor = await connection.raw_sql(query)
    try:
        if cursor.description is None:
            # No results (e.g., empty table)
            return pandas.DataFrame()
        columns: list[str] = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        return pandas.DataFrame(rows, columns=columns)  # type: ignore[arg-type]
    finally:
        cursor.close()


class SQLiteForeignKeyInspector(ForeignKeyInspector):
    """Foreign key inspector for SQLite databases."""

    async def get_foreign_keys(
        self,
        connection: AsyncIbisConnection,
        tables: list[TableToInspect],
    ) -> dict[str, list[ForeignKeyInfo]]:
        """Get foreign key constraints from SQLite using PRAGMA foreign_key_list.

        SQLite stores foreign key information in the database schema and provides
        the PRAGMA foreign_key_list command to retrieve it.
        """
        from agent_platform.core.payloads.data_connection import ForeignKeyInfo

        if not isinstance(connection, AsyncSqliteConnection):
            raise TypeError("connection must be an AsyncSqliteConnection")

        sqlite_connection: AsyncSqliteConnection = connection

        if not tables:
            return {}

        result: dict[str, list[ForeignKeyInfo]] = {}

        for table in tables:
            try:
                # Use PRAGMA foreign_key_list to get FK information
                # Returns: id, seq, table, from, to, on_update, on_delete, match
                pragma_query = f"PRAGMA foreign_key_list({table.name})"
                df = await _cursor_to_dataframe(sqlite_connection, pragma_query)

                if df.empty:
                    continue

                rows = df.to_dict(orient="records")

                # Group FK columns by constraint ID
                # In SQLite, the 'id' column groups related columns of the same FK constraint
                # Use temporary dict to track columns by sequence before converting to lists
                temp_constraints: dict[int, dict] = {}
                for row in rows:
                    fk_id = row["id"]
                    seq = row["seq"]  # Sequence number for multi-column FKs

                    if fk_id not in temp_constraints:
                        temp_constraints[fk_id] = {
                            "source_table": table.name,
                            "target_table": row["table"],
                            "source_columns_by_seq": {},
                            "target_columns_by_seq": {},
                            "on_delete": row.get("on_delete"),
                            "on_update": row.get("on_update"),
                        }

                    # Store columns by their sequence number
                    temp_constraints[fk_id]["source_columns_by_seq"][seq] = row["from"]
                    temp_constraints[fk_id]["target_columns_by_seq"][seq] = row["to"]

                # Convert to ConstraintData with properly ordered columns
                constraints_by_id: dict[int, ConstraintData] = {}
                for fk_id, temp_data in temp_constraints.items():
                    # Sort by sequence number and extract column names
                    source_columns = [
                        temp_data["source_columns_by_seq"][k] for k in sorted(temp_data["source_columns_by_seq"].keys())
                    ]
                    target_columns = [
                        temp_data["target_columns_by_seq"][k] for k in sorted(temp_data["target_columns_by_seq"].keys())
                    ]

                    constraints_by_id[fk_id] = {
                        "source_table": temp_data["source_table"],
                        "target_table": temp_data["target_table"],
                        "source_columns": source_columns,
                        "target_columns": target_columns,
                        "on_delete": temp_data["on_delete"],
                        "on_update": temp_data["on_update"],
                    }

                # Convert to ForeignKeyInfo objects
                for fk_id, constraint_data in constraints_by_id.items():
                    source_columns = constraint_data["source_columns"]
                    target_columns = constraint_data["target_columns"]

                    # Create a constraint name (SQLite doesn't provide names)
                    constraint_name = f"fk_{constraint_data['source_table']}_{constraint_data['target_table']}_{fk_id}"

                    fk_info = ForeignKeyInfo(
                        constraint_name=constraint_name,
                        source_table=constraint_data["source_table"],
                        source_columns=source_columns,
                        target_table=constraint_data["target_table"],
                        target_columns=target_columns,
                        on_delete=self._parse_foreign_key_action(constraint_data["on_delete"]),
                        on_update=self._parse_foreign_key_action(constraint_data["on_update"]),
                    )
                    result.setdefault(table.name, []).append(fk_info)

            except Exception as e:
                logger.warning(f"Failed to query FK constraints from SQLite for table {table.name}: {e}")
                continue

        return result

    async def get_primary_keys(
        self,
        connection: AsyncSqliteConnection,
        tables: list[TableToInspect],
    ) -> dict[str, list[str]]:
        """Get primary key columns from SQLite using PRAGMA table_info.

        SQLite's PRAGMA table_info returns column information including which
        columns are part of the primary key (pk column > 0).
        """
        if not isinstance(connection, AsyncSqliteConnection):
            raise TypeError("connection must be an AsyncSqliteConnection")
        sqlite_connection: AsyncSqliteConnection = connection

        if not tables:
            return {}

        result: dict[str, list[str]] = {}

        for table in tables:
            try:
                # Use PRAGMA table_info to get column information
                # Returns: cid, name, type, notnull, dflt_value, pk
                # The 'pk' column indicates: 0 = not PK, >0 = position in PK
                pragma_query = f"PRAGMA table_info({table.name})"
                df = await _cursor_to_dataframe(sqlite_connection, pragma_query)

                if df.empty:
                    continue

                # Filter for PK columns (pk > 0) and sort by pk position
                import pandas as pd

                pk_filtered = df[df["pk"] > 0]
                assert isinstance(pk_filtered, pd.DataFrame)
                pk_rows = pk_filtered.sort_values(by="pk")
                pk_columns = pk_rows["name"].tolist()

                if pk_columns:
                    result[table.name] = pk_columns

            except Exception as e:
                logger.warning(f"Failed to query PK constraints from SQLite for table {table.name}: {e}")
                continue

        return result
