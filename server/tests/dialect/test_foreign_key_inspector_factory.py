"""Unit tests for ForeignKeyInspectorFactory."""

from __future__ import annotations

import pytest

from agent_platform.server.dialect import ForeignKeyInspector, ForeignKeyInspectorFactory
from agent_platform.server.dialect.databricks import DatabricksForeignKeyInspector
from agent_platform.server.dialect.mysql import MySQLForeignKeyInspector
from agent_platform.server.dialect.postgres import PostgresForeignKeyInspector
from agent_platform.server.dialect.redshift import RedshiftForeignKeyInspector
from agent_platform.server.dialect.snowflake import SnowflakeForeignKeyInspector
from agent_platform.server.dialect.sqlite import SQLiteForeignKeyInspector


class TestForeignKeyInspectorFactory:
    """Test ForeignKeyInspectorFactory.create method."""

    def test_create_postgres_inspector(self):
        """Test that factory creates PostgresForeignKeyInspector for postgres engine."""
        inspector = ForeignKeyInspectorFactory.create("postgres")
        assert isinstance(inspector, PostgresForeignKeyInspector)
        assert isinstance(inspector, ForeignKeyInspector)

    def test_create_mysql_inspector(self):
        """Test that factory creates MySQLForeignKeyInspector for mysql engine."""
        inspector = ForeignKeyInspectorFactory.create("mysql")
        assert isinstance(inspector, MySQLForeignKeyInspector)
        assert isinstance(inspector, ForeignKeyInspector)

    def test_create_sqlite_inspector(self):
        """Test that factory creates SQLiteForeignKeyInspector for sqlite engine."""
        inspector = ForeignKeyInspectorFactory.create("sqlite")
        assert isinstance(inspector, SQLiteForeignKeyInspector)
        assert isinstance(inspector, ForeignKeyInspector)

    def test_create_snowflake_inspector(self):
        """Test that factory creates SnowflakeForeignKeyInspector for snowflake engine."""
        inspector = ForeignKeyInspectorFactory.create("snowflake")
        assert isinstance(inspector, SnowflakeForeignKeyInspector)
        assert isinstance(inspector, ForeignKeyInspector)

    def test_create_databricks_inspector(self):
        """Test that factory creates DatabricksForeignKeyInspector for databricks engine."""
        inspector = ForeignKeyInspectorFactory.create("databricks")
        assert isinstance(inspector, DatabricksForeignKeyInspector)
        assert isinstance(inspector, ForeignKeyInspector)

    def test_create_redshift_inspector(self):
        """Test that factory creates RedshiftForeignKeyInspector for redshift engine."""
        inspector = ForeignKeyInspectorFactory.create("redshift")
        assert isinstance(inspector, RedshiftForeignKeyInspector)
        assert isinstance(inspector, ForeignKeyInspector)

    def test_create_unsupported_engine_raises_value_error(self):
        """Test that factory raises ValueError for unsupported database engines."""
        with pytest.raises(ValueError, match="No ForeignKeyInspector implementation available for engine") as exc_info:
            ForeignKeyInspectorFactory.create("oracle")

        error_message = str(exc_info.value)
        assert "No ForeignKeyInspector implementation available for engine: oracle" in error_message
