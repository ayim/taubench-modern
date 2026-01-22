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

        # Use pg_catalog (PostgreSQL-specific) for reliable FK detection.
        # This approach works for both simple and composite foreign keys:
        # - Uses LATERAL join with synchronized unnest() to properly pair source/target columns
        # - Avoids cartesian products by matching columns by their array position
        # - Works regardless of whether unique_constraint_name is populated in information_schema
        #
        # Why pg_catalog instead of information_schema:
        # - information_schema.referential_constraints.unique_constraint_name can be NULL
        # - pg_catalog.pg_constraint always has complete FK metadata (conkey/confkey arrays)
        query = f"""
        SELECT
          con.conname AS constraint_name,
          src_tbl.relname AS source_table,
          src_attr.attname AS source_column,
          tgt_tbl.relname AS target_table,
          tgt_attr.attname AS target_column,

          CASE con.confdeltype
            WHEN 'a' THEN 'NO ACTION'
            WHEN 'r' THEN 'RESTRICT'
            WHEN 'c' THEN 'CASCADE'
            WHEN 'n' THEN 'SET NULL'
            WHEN 'd' THEN 'SET DEFAULT'
          END AS on_delete,

          CASE con.confupdtype
            WHEN 'a' THEN 'NO ACTION'
            WHEN 'r' THEN 'RESTRICT'
            WHEN 'c' THEN 'CASCADE'
            WHEN 'n' THEN 'SET NULL'
            WHEN 'd' THEN 'SET DEFAULT'
          END AS on_update
        FROM (VALUES
            ('{schema_name}', ARRAY[{table_list}])
         ) AS p(schema_name, table_names)

        -- Filter to just foreign-key constraints
        JOIN pg_constraint con
          ON con.contype = 'f'

        -- Join the source table (regular or partitioned)
        JOIN pg_class src_tbl
          ON src_tbl.oid = con.conrelid
         AND src_tbl.relkind IN ('r','p')

        JOIN pg_namespace src_ns
          ON src_ns.oid = src_tbl.relnamespace

        -- Join the target table (regular or partitioned)
        JOIN pg_class tgt_tbl
          ON tgt_tbl.oid = con.confrelid
         AND tgt_tbl.relkind IN ('r','p')
        JOIN pg_namespace tgt_ns
          ON tgt_ns.oid = tgt_tbl.relnamespace

        -- Expand composite FKs: each row is one matching source/target column, with its position.
        JOIN LATERAL unnest(con.conkey, con.confkey) WITH ORDINALITY
          AS u(left_attnum, right_attnum, ord)
          ON true

        -- get the source column name
        JOIN pg_attribute src_attr
          ON src_attr.attrelid = con.conrelid
         AND src_attr.attnum   = u.left_attnum
         AND NOT src_attr.attisdropped

        -- get the target column name
        JOIN pg_attribute tgt_attr
          ON tgt_attr.attrelid = con.confrelid
         AND tgt_attr.attnum   = u.right_attnum
         AND NOT tgt_attr.attisdropped

        WHERE
          src_ns.nspname = p.schema_name
          AND tgt_ns.nspname = p.schema_name
          AND src_tbl.relname = ANY(p.table_names)
          AND tgt_tbl.relname = ANY(p.table_names)

        ORDER BY
          source_table, constraint_name
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
