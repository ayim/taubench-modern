"""Foreign key and primary key inspection base interface.

This module provides the base interface for database-specific inspectors to extract
foreign key constraints and primary key definitions from database connections.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from structlog import get_logger

if TYPE_CHECKING:
    from agent_platform.core.payloads.data_connection import (
        ForeignKeyAction,
        ForeignKeyInfo,
        TableToInspect,
    )
    from agent_platform.server.kernel.ibis_async_proxy import AsyncIbisConnection

logger = get_logger(__name__)


class ForeignKeyInspector:
    """Base class for extracting FK/PK metadata from databases."""

    @staticmethod
    def _parse_foreign_key_action(action_str: str | None) -> ForeignKeyAction | None:
        """Parse foreign key action string to ForeignKeyAction enum.

        Database systems return actions in uppercase from INFORMATION_SCHEMA or metadata queries.
        Common values: CASCADE, RESTRICT, SET NULL, NO ACTION, SET DEFAULT

        Args:
            action_str: Foreign key action string from database metadata

        Returns:
            ForeignKeyAction enum value or None if action is unknown/not specified
        """
        from agent_platform.core.payloads.data_connection import ForeignKeyAction

        if not action_str:
            return None

        # Normalize to uppercase and strip whitespace
        normalized = action_str.strip().upper()

        # Standard SQL foreign key action mapping
        action_map = {
            "CASCADE": ForeignKeyAction.CASCADE,
            "RESTRICT": ForeignKeyAction.RESTRICT,
            "SET NULL": ForeignKeyAction.SET_NULL,
            "SET DEFAULT": ForeignKeyAction.SET_DEFAULT,
            "NO ACTION": ForeignKeyAction.NO_ACTION,
        }

        action = action_map.get(normalized)
        if action is None:
            logger.warning(
                f"Unknown foreign key action '{action_str}', "
                f"will be treated as None. Known actions: {list(action_map.keys())}"
            )
        return action

    async def get_foreign_keys(
        self,
        connection: AsyncIbisConnection,
        tables: list[TableToInspect],
    ) -> dict[str, list[ForeignKeyInfo]]:
        """Get foreign key constraints for the specified tables.

        Args:
            connection: Database connection object (ibis connection)
            tables: List of tables to inspect

        Returns:
            Dictionary mapping table_name -> list of ForeignKeyInfo
        """
        return {}

    async def get_primary_keys(
        self,
        connection: AsyncIbisConnection,
        tables: list[TableToInspect],
    ) -> dict[str, list[str]]:
        """Get primary key columns for the specified tables.

        Args:
            connection: Database connection object (ibis connection)
            tables: List of tables to inspect

        Returns:
            Dictionary mapping table_name -> list of PK column names
        """
        return {}
