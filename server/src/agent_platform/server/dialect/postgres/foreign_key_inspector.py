"""PostgreSQL foreign key inspector implementation."""

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


class PostgresForeignKeyInspector(ForeignKeyInspector):
    """Foreign key inspector for PostgreSQL databases."""

    async def get_foreign_keys(
        self,
        connection: AsyncIbisConnection,
        tables: list[TableToInspect],
    ) -> dict[str, list[ForeignKeyInfo]]:
        """Get foreign key constraints from PostgreSQL information_schema."""
        from agent_platform.core.payloads.data_connection import ForeignKeyInfo

        if not tables:
            return {}

        # Build list of table names to inspect
        table_names = [t.name for t in tables]
        schema_name = tables[0].schema if tables[0].schema else "public"

        table_list = ", ".join([f"'{name}'" for name in table_names])

        # Use information_schema with proper handling for composite foreign keys.
        # The key is to join key_column_usage twice:
        # - kcu_src: source columns from the FK constraint (has ordinal_position)
        # - kcu_tgt: target columns from the referenced PK/unique constraint
        # By matching on ordinal_position, we get the correct 1:1 column mapping.
        # Note: constraint_column_usage cannot be used for composite FKs as it
        # lacks ordinal_position, causing incorrect Cartesian products.
        query = f"""
        SELECT
            tc.constraint_name,
            tc.table_name AS source_table,
            kcu_src.column_name AS source_column,
            kcu_tgt.table_name AS target_table,
            kcu_tgt.column_name AS target_column,
            rc.delete_rule AS on_delete,
            rc.update_rule AS on_update,
            kcu_src.ordinal_position
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu_src
            ON tc.constraint_name = kcu_src.constraint_name
            AND tc.table_schema = kcu_src.table_schema
        JOIN information_schema.referential_constraints rc
            ON rc.constraint_name = tc.constraint_name
            AND rc.constraint_schema = tc.table_schema
        -- Join key_column_usage for the TARGET constraint (PK/unique being referenced)
        -- Match by ordinal_position to get correct 1:1 column pairing for composite keys
        JOIN information_schema.key_column_usage kcu_tgt
            ON kcu_tgt.constraint_name = rc.unique_constraint_name
            AND kcu_tgt.table_schema = rc.unique_constraint_schema
            AND kcu_tgt.ordinal_position = kcu_src.ordinal_position
        WHERE tc.constraint_type = 'FOREIGN KEY'
            AND tc.table_schema = '{schema_name}'
            AND tc.table_name IN ({table_list})
        ORDER BY tc.constraint_name, kcu_src.ordinal_position
        """

        result_table = await connection.sql(query)
        df = await result_table.to_pandas()
        rows = df.to_dict(orient="records")

        # Group FK columns by constraint - columns are now correctly paired by position
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
        """Get primary key columns from PostgreSQL information_schema."""
        if not tables:
            return {}

        # Build list of table names to inspect
        table_names = [t.name for t in tables]
        schema_name = tables[0].schema if tables[0].schema else "public"

        table_list = ", ".join([f"'{name}'" for name in table_names])

        # Use raw SQL query to access information_schema tables
        query = f"""
        SELECT
            tc.table_name,
            kcu.column_name,
            kcu.ordinal_position
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        WHERE tc.constraint_type = 'PRIMARY KEY'
            AND tc.table_schema = '{schema_name}'
            AND tc.table_name IN ({table_list})
        ORDER BY tc.table_name, kcu.ordinal_position
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
