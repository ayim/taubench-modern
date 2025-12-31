"""Unit tests for dialect inspectors with simple implementations (Snowflake, Databricks, Redshift)."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from agent_platform.core.payloads.data_connection import TableToInspect
from agent_platform.server.dialect.databricks import DatabricksForeignKeyInspector
from agent_platform.server.dialect.foreign_key_inspector_base import ForeignKeyInspector
from agent_platform.server.dialect.redshift import RedshiftForeignKeyInspector
from agent_platform.server.dialect.snowflake import SnowflakeForeignKeyInspector


class TestSimpleForeignKeyInspectors:
    """Test foreign key inspectors with simple implementations.

    These inspectors (Snowflake, Databricks, Redshift) all return empty dicts
    because FK/PK constraints are informational only and not enforced in these databases.
    """

    @pytest.mark.parametrize(
        "inspector_class",
        [
            SnowflakeForeignKeyInspector,
            DatabricksForeignKeyInspector,
            RedshiftForeignKeyInspector,
        ],
        ids=["snowflake", "databricks", "redshift"],
    )
    @pytest.mark.asyncio
    async def test_get_foreign_keys_returns_empty_dict(self, inspector_class: type[ForeignKeyInspector]):
        """Test that inspector returns empty dict for foreign keys."""
        inspector = inspector_class()
        mock_connection = AsyncMock()

        tables = [
            TableToInspect(name="customers", database="test_db", schema="public", columns_to_inspect=None),
            TableToInspect(name="orders", database="test_db", schema="public", columns_to_inspect=None),
        ]

        result = await inspector.get_foreign_keys(mock_connection, tables)

        assert result == {}
        assert isinstance(result, dict)

    @pytest.mark.parametrize(
        "inspector_class",
        [
            SnowflakeForeignKeyInspector,
            DatabricksForeignKeyInspector,
            RedshiftForeignKeyInspector,
        ],
        ids=["snowflake", "databricks", "redshift"],
    )
    @pytest.mark.asyncio
    async def test_get_primary_keys_returns_empty_dict(self, inspector_class: type[ForeignKeyInspector]):
        """Test that inspector returns empty dict for primary keys."""
        inspector = inspector_class()
        mock_connection = AsyncMock()

        tables = [
            TableToInspect(name="customers", database="test_db", schema="public", columns_to_inspect=None),
            TableToInspect(name="orders", database="test_db", schema="public", columns_to_inspect=None),
        ]

        result = await inspector.get_primary_keys(mock_connection, tables)

        assert result == {}
        assert isinstance(result, dict)
