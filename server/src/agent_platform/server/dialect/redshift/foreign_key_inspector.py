"""Redshift foreign key inspector implementation."""

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


class RedshiftForeignKeyInspector(ForeignKeyInspector):
    """Foreign key inspector for Redshift.

    Note: Redshift FK/PK constraints are informational only and not enforced.
    They cannot be reliably used for relationship detection.
    """

    async def get_foreign_keys(
        self,
        connection: AsyncIbisConnection,
        tables: list[TableToInspect],
    ) -> dict[str, list[ForeignKeyInfo]]:
        """Get foreign key constraints from Redshift.

        Note: Redshift FK constraints are informational only and not enforced.
        Returns empty dict as FK constraints are not reliable for relationship detection.
        """
        logger.debug("Redshift FK constraints are informational only and not fully supported")
        return await super().get_foreign_keys(connection, tables)

    async def get_primary_keys(
        self,
        connection: AsyncIbisConnection,
        tables: list[TableToInspect],
    ) -> dict[str, list[str]]:
        """Get primary key columns from Redshift.

        Note: Redshift PK constraints are informational only and not enforced.
        Returns empty dict as PK constraints are not reliable for relationship detection.
        """
        logger.debug("Redshift PK constraints are informational only and not fully supported")
        return await super().get_primary_keys(connection, tables)
