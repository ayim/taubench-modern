"""
Factory functions for creating database adapters and view generators.
"""

from sema4ai_docint.logging import logger

from .adapters import DBAdapter, PostgresAdapter
from .views import ViewGenerator


def create_db_adapter(db_type: str, **kwargs) -> DBAdapter:
    """
    Create a database adapter for the specified database type.

    Args:
        db_type: The database type (e.g., "postgres")
        **kwargs: Additional configuration parameters for the adapter

    Returns:
        An appropriate DBAdapter instance

    Raises:
        ValueError: If the database type is not supported
    """
    db_type = db_type.lower()

    if db_type == "postgres":
        logger.info("Creating PostgreSQL adapter")
        return PostgresAdapter()
    else:
        raise ValueError(f"Unsupported database type: {db_type}")


def create_view_generator(
    db_type: str = "postgres",
    source_table_name: str = "docs",
    document_column_name: str = "doc",
    **kwargs,
) -> ViewGenerator:
    """
    Create a ViewGenerator with the appropriate database adapter.

    Args:
        db_type: The database type (e.g., "postgres")
        source_table_name: The name of the table containing the JSON documents
        document_column_name: The column name containing the JSON document
        **kwargs: Additional configuration parameters

    Returns:
        A configured ViewGenerator instance
    """
    db_adapter = create_db_adapter(db_type, **kwargs)
    logger.info(
        f"Creating ViewGenerator for {db_type} with source_table_name={source_table_name}, "
        f"document_column_name={document_column_name}"
    )
    return ViewGenerator(
        source_table_name=source_table_name,
        document_column_name=document_column_name,
        db_adapter=db_adapter,
    )
