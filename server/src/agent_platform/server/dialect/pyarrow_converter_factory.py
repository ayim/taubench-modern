"""Factory for creating dialect-specific PyArrow converters."""

from __future__ import annotations

from structlog import get_logger

from agent_platform.server.dialect.pyarrow_converter_base import PyArrowConverter

logger = get_logger(__name__)


class PyArrowConverterFactory:
    """Factory for creating appropriate PyArrow converter based on database engine."""

    @staticmethod
    def create(engine: str) -> PyArrowConverter:
        """Create PyArrow converter for the specified database engine.

        Args:
            engine: Database engine name (postgres, mysql, sqlite, etc.)

        Returns:
            Appropriate PyArrowConverter implementation for the dialect
        """
        from agent_platform.server.dialect.databricks import DatabricksPyArrowConverter
        from agent_platform.server.dialect.duckdb import DuckDBPyArrowConverter
        from agent_platform.server.dialect.mysql import MySQLPyArrowConverter
        from agent_platform.server.dialect.postgres import PostgresPyArrowConverter
        from agent_platform.server.dialect.redshift import RedshiftPyArrowConverter
        from agent_platform.server.dialect.snowflake import SnowflakePyArrowConverter
        from agent_platform.server.dialect.sqlite import SQLitePyArrowConverter

        mapping = {
            "postgres": PostgresPyArrowConverter,
            "mysql": MySQLPyArrowConverter,
            "redshift": RedshiftPyArrowConverter,
            "snowflake": SnowflakePyArrowConverter,
            "databricks": DatabricksPyArrowConverter,
            "duckdb": DuckDBPyArrowConverter,
            "sqlite": SQLitePyArrowConverter,
        }

        converter_class = mapping.get(engine)
        if not converter_class:
            supported_engines = ", ".join(mapping.keys())
            msg = f"Unsupported database engine: '{engine}'. Supported engines: {supported_engines}"
            raise ValueError(msg)

        return converter_class()
