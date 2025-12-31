"""Factory for creating dialect-specific foreign key inspectors."""

from __future__ import annotations

from structlog import get_logger

from agent_platform.server.dialect.foreign_key_inspector_base import ForeignKeyInspector

logger = get_logger(__name__)


class ForeignKeyInspectorFactory:
    """Factory for creating appropriate FK inspector based on database engine."""

    @staticmethod
    def create(engine: str) -> ForeignKeyInspector:
        """Create FK inspector for the specified database engine.

        Args:
            engine: Database engine name (postgres, mysql, sqlite, etc.)

        Returns:
            Appropriate ForeignKeyInspector implementation
        """
        from agent_platform.server.dialect.databricks import DatabricksForeignKeyInspector
        from agent_platform.server.dialect.mysql import MySQLForeignKeyInspector
        from agent_platform.server.dialect.postgres import PostgresForeignKeyInspector
        from agent_platform.server.dialect.redshift import RedshiftForeignKeyInspector
        from agent_platform.server.dialect.snowflake import SnowflakeForeignKeyInspector
        from agent_platform.server.dialect.sqlite import SQLiteForeignKeyInspector

        mapping = {
            "postgres": PostgresForeignKeyInspector,
            "mysql": MySQLForeignKeyInspector,
            "redshift": RedshiftForeignKeyInspector,
            "snowflake": SnowflakeForeignKeyInspector,
            "databricks": DatabricksForeignKeyInspector,
            "sqlite": SQLiteForeignKeyInspector,
        }
        inspector_class = mapping.get(engine)
        if not inspector_class:
            raise ValueError(
                f"No ForeignKeyInspector implementation available for engine: {engine}. "
                f"Supported engines: {', '.join(mapping.keys())}."
            )
        return inspector_class()
