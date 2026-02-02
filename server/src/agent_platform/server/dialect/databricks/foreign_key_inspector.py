"""Databricks foreign key inspector implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from structlog import get_logger

from agent_platform.server.dialect.foreign_key_inspector_base import ForeignKeyInspector

if TYPE_CHECKING:
    from agent_platform.core.payloads.data_connection import (
        ForeignKeyInfo,
        TableToInspect,
    )
    from agent_platform.server.kernel.ibis import AsyncIbisConnection

logger = get_logger(__name__)


class DatabricksForeignKeyInspector(ForeignKeyInspector):
    """Foreign key inspector for Databricks."""

    async def get_foreign_keys(
        self,
        connection: AsyncIbisConnection,
        tables: list[TableToInspect],
    ) -> dict[str, list[ForeignKeyInfo]]:
        """Get foreign key constraints from Databricks.

        Note: Databricks FK constraints are informational only and not enforced.
        Returns empty dict as FK constraints are not reliable for relationship detection.
        """
        logger.debug("Databricks FK constraints are informational only and not fully supported yet")
        return await super().get_foreign_keys(connection, tables)

    async def get_primary_keys(
        self,
        connection: AsyncIbisConnection,
        tables: list[TableToInspect],
    ) -> dict[str, list[str]]:
        """Get primary key columns from Databricks.

        Note: Databricks PK constraints are informational only and not enforced.
        Returns empty dict as PK constraints are not reliable for relationship detection.
        """
        logger.debug("Databricks PK constraints are informational only and not fully supported")
        return await super().get_primary_keys(connection, tables)
