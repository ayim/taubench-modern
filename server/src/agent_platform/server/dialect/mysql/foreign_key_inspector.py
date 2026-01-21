"""MySQL foreign key inspector implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from structlog import get_logger

from agent_platform.server.dialect.foreign_key_inspector_base import ForeignKeyInspector
from agent_platform.server.dialect.types import ConstraintData

if TYPE_CHECKING:
    from agent_platform.core.payloads.data_connection import (
        ForeignKeyInfo,
        TableToInspect,
    )
    from agent_platform.server.kernel.ibis_async_proxy import AsyncIbisConnection

logger = get_logger(__name__)


class MySQLForeignKeyInspector(ForeignKeyInspector):
    """Foreign key inspector for MySQL databases."""

    async def get_foreign_keys(
        self,
        connection: AsyncIbisConnection,
        tables: list[TableToInspect],
    ) -> dict[str, list[ForeignKeyInfo]]:
        """Get foreign key constraints from MySQL information_schema."""
        from agent_platform.core.payloads.data_connection import ForeignKeyInfo

        if not tables:
            return {}

        # Build list of table names to inspect
        table_names = [t.name for t in tables]
        # database and schema are synonyms for mysql, but Ibis only implements current_schema()
        database_name = tables[0].database if tables[0].database else await connection.get_current_schema()

        table_list = ", ".join([f"'{name}'" for name in table_names])

        # Use raw SQL query to access information_schema tables
        query = f"""
        SELECT
            kcu.CONSTRAINT_NAME AS constraint_name,
            kcu.TABLE_NAME AS source_table,
            kcu.COLUMN_NAME AS source_column,
            kcu.REFERENCED_TABLE_NAME AS target_table,
            kcu.REFERENCED_COLUMN_NAME AS target_column,
            rc.DELETE_RULE AS on_delete,
            rc.UPDATE_RULE AS on_update,
            kcu.ORDINAL_POSITION AS ordinal_position
        FROM information_schema.KEY_COLUMN_USAGE kcu
        JOIN information_schema.REFERENTIAL_CONSTRAINTS rc
            ON kcu.CONSTRAINT_NAME = rc.CONSTRAINT_NAME
            AND kcu.TABLE_SCHEMA = rc.CONSTRAINT_SCHEMA
        WHERE kcu.TABLE_SCHEMA = '{database_name}'
            AND kcu.TABLE_NAME IN ({table_list})
            AND kcu.REFERENCED_TABLE_NAME IS NOT NULL
        ORDER BY kcu.CONSTRAINT_NAME, kcu.ORDINAL_POSITION
        """

        result_table = await connection.sql(query)
        df = await result_table.to_pandas()
        rows = df.to_dict(orient="records")

        # Group FK columns by constraint
        constraints_by_name: dict[str, ConstraintData] = {}
        for row in rows:
            constraint_name = row["constraint_name"]

            if constraint_name not in constraints_by_name:
                constraints_by_name[constraint_name] = {
                    "source_table": row["source_table"],
                    "target_table": row["target_table"],
                    "source_columns": [],
                    "target_columns": [],
                    "on_delete": row["on_delete"],
                    "on_update": row["on_update"],
                }

            constraints_by_name[constraint_name]["source_columns"].append(row["source_column"])
            constraints_by_name[constraint_name]["target_columns"].append(row["target_column"])

        # Convert to ForeignKeyInfo objects grouped by table
        result: dict[str, list[ForeignKeyInfo]] = {}
        for constraint_name, constraint_data in constraints_by_name.items():
            source_table = constraint_data["source_table"]

            fk_info = ForeignKeyInfo(
                constraint_name=constraint_name,
                source_table=source_table,
                source_columns=constraint_data["source_columns"],
                target_table=constraint_data["target_table"],
                target_columns=constraint_data["target_columns"],
                on_delete=self._parse_foreign_key_action(constraint_data["on_delete"]),
                on_update=self._parse_foreign_key_action(constraint_data["on_update"]),
            )
            result.setdefault(source_table, []).append(fk_info)

        return result

    async def get_primary_keys(
        self,
        connection: AsyncIbisConnection,
        tables: list[TableToInspect],
    ) -> dict[str, list[str]]:
        """Get primary key columns from MySQL information_schema."""
        if not tables:
            return {}

        # Build list of table names to inspect
        table_names = [t.name for t in tables]
        # database and schema are synonyms for mysql, but Ibis only implements current_schema()
        database_name = tables[0].database if tables[0].database else await connection.get_current_schema()

        table_list = ", ".join([f"'{name}'" for name in table_names])

        # Use raw SQL query to access information_schema tables
        query = f"""
        SELECT
            TABLE_NAME,
            COLUMN_NAME,
            ORDINAL_POSITION
        FROM information_schema.KEY_COLUMN_USAGE
        WHERE TABLE_SCHEMA = '{database_name}'
            AND TABLE_NAME IN ({table_list})
            AND CONSTRAINT_NAME = 'PRIMARY'
        ORDER BY TABLE_NAME, ORDINAL_POSITION
        """

        result_table = await connection.sql(query)
        df = await result_table.to_pandas()
        rows = df.values.tolist()

        # Group PK columns by table
        result: dict[str, list[str]] = {}
        for row in rows:
            table_name, column_name, _ = row
            result.setdefault(table_name, []).append(column_name)

        return result
