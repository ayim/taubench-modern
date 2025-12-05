from sema4ai.data import DataSource


def migrate_tables(engine: str, datasource: DataSource):
    if engine != "postgres":
        raise ValueError(f"Unsupported engine: {engine}")

    _migrate_postgres(datasource)


def _migrate_postgres(datasource: DataSource):
    """
    Migrate the tables for the data models library.

    Args:
        datasource: The data source connection

    Returns:
        None
    """
    _postgres_migrations = [
        """
        ALTER TABLE IF EXISTS data_models ADD COLUMN IF NOT EXISTS summary TEXT;
        """,
        """
        ALTER TABLE IF EXISTS document_layouts ADD COLUMN IF NOT EXISTS summary TEXT;
        """,
        """
        ALTER TABLE IF EXISTS document_layouts ADD COLUMN IF NOT EXISTS extraction_config JSONB;
        """,
        """
        ALTER TABLE IF EXISTS document_layouts ADD COLUMN IF NOT EXISTS system_prompt TEXT;
        """,
        """
        ALTER TABLE IF EXISTS data_models ADD COLUMN IF NOT EXISTS base_config JSONB;
        """,
    ]

    for migration in _postgres_migrations:
        datasource.native_query(migration)
