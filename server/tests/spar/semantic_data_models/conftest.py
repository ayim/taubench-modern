import os
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator

    from agent_platform.orchestrator.agent_server_client import AgentServerClient

    from agent_platform.core.data_connections import DataConnection
    from agent_platform.core.payloads.data_connection import (
        DatabricksDataConnectionConfiguration,
        DataConnectionConfiguration,
        DataConnectionEngine,
        MySQLDataConnectionConfiguration,
        PostgresDataConnectionConfiguration,
        RedshiftDataConnectionConfiguration,
        SnowflakeDataConnectionConfiguration,
    )


@pytest.fixture(scope="session")
def semantic_data_model_resources_path(spar_resources_path: Path) -> Path:
    return spar_resources_path / "semantic_data_models"


@pytest.fixture(scope="module", params=["postgres", "snowflake", "mysql", "databricks", "redshift"])
def engine(request: pytest.FixtureRequest) -> "DataConnectionEngine":
    """
    Parametrized fixture that provides the database engine to test against.

    When you add more engines, just add them to the params list:
    @pytest.fixture(params=["postgres", "snowflake", "mysql", "bigquery"])

    All tests that use this fixture (or fixtures that depend on it) will run
    once for each engine in the params list.

    Note: Snowflake and MySQL tests are automatically skipped if not available.
    PostgreSQL tests always run (using local Docker with hardcoded test credentials).

    Environment variables to control test execution:
    - SKIP_MYSQL_TESTS=0: Enable MySQL tests locally (default: skip in CI)
    - Snowflake requires: SNOWFLAKE_ACCOUNT, SNOWFLAKE_USERNAME, SNOWFLAKE_PASSWORD, SNOWFLAKE_WAREHOUSE
    """
    engine_name = request.param

    # Skip MySQL tests by default (not available in CI)
    # Set SKIP_MYSQL_TESTS=0 to run MySQL tests locally
    skip_mysql = os.getenv("SKIP_MYSQL_TESTS", "1").lower() not in ("0", "false", "no")
    if engine_name == "mysql" and skip_mysql:
        pytest.skip(
            "MySQL tests skipped: MySQL is not available in CI environment. "
            "To run MySQL tests locally, set SKIP_MYSQL_TESTS=0 environment variable."
        )

    # Skip Snowflake tests if credentials are not configured
    if engine_name == "snowflake":
        required_env_vars = [
            "SNOWFLAKE_ACCOUNT",
            "SNOWFLAKE_USERNAME",
            "SNOWFLAKE_PASSWORD",
            "SNOWFLAKE_WAREHOUSE",
        ]
        missing_vars = [var for var in required_env_vars if not os.getenv(var)]

        if missing_vars:
            missing = ", ".join(missing_vars)
            pytest.skip(f"Missing environment variables: {missing}.")

    # Skip Databricks tests if credentials are not configured
    if engine_name == "databricks":
        required_env_vars = [
            "DATABRICKS_SERVER_HOSTNAME",
            "DATABRICKS_HTTP_PATH",
            "DATABRICKS_ACCESS_TOKEN",
        ]
        missing_vars = [var for var in required_env_vars if not os.getenv(var)]

        if missing_vars:
            missing = ", ".join(missing_vars)
            pytest.skip(f"Missing environment variables: {missing}.")

    # Skip Redshift tests if credentials are not configured
    if engine_name == "redshift":
        required_env_vars = [
            "REDSHIFT_HOST",
            "REDSHIFT_PORT",
            "REDSHIFT_DATABASE",
            "REDSHIFT_USER",
            "REDSHIFT_PASSWORD",
        ]
        missing_vars = [var for var in required_env_vars if not os.getenv(var)]

        if missing_vars:
            missing = ", ".join(missing_vars)
            pytest.skip(f"Missing environment variables: {missing}.")

    return engine_name


@pytest.fixture(scope="module")
def sdm_seed_data_connection_configuration(
    engine: "DataConnectionEngine",
) -> "DataConnectionConfiguration":
    """
    Fixture that provides a DataConnectionConfiguration used to seed test data directly
    into the database for testing purposes. This connection is only used within the pytest
    code to initialize and seed the database and is not used by the agent server.

    It can be overridden via environment variables with the following pattern:

        SDM_SEED_DATA_CONNECTION_{ENGINE}_{ATTRIBUTE} where {ENGINE} is the engine to test against
        and {ATTRIBUTE} is the attribute to override. Attirbute name needs to match the
        expected attribute for the given engine based on the DataConnectionConfiguration class.
    """
    from dataclasses import fields

    from agent_platform.core.payloads.data_connection import (
        DatabricksDataConnectionConfiguration,
        MySQLDataConnectionConfiguration,
        PostgresDataConnectionConfiguration,
        RedshiftDataConnectionConfiguration,
        SnowflakeDataConnectionConfiguration,
    )

    attributes_to_collect: list[str] = []
    attributes_to_apply: dict[str, Any] = {}

    match engine:
        case "postgres":
            fields_to_collect = fields(PostgresDataConnectionConfiguration)
        case "snowflake":
            fields_to_collect = fields(SnowflakeDataConnectionConfiguration)
        case "databricks":
            fields_to_collect = fields(DatabricksDataConnectionConfiguration)
        case "redshift":
            fields_to_collect = fields(RedshiftDataConnectionConfiguration)
        case "mysql":
            fields_to_collect = fields(MySQLDataConnectionConfiguration)
        case _:
            raise ValueError(f"Unsupported engine: {engine}")

    attributes_to_collect = [f.name for f in fields_to_collect]
    for attribute in attributes_to_collect:
        attribute_value = os.getenv(f"SDM_SEED_DATA_CONNECTION_{engine.upper()}_{attribute.upper()}", None)
        if attribute_value is not None:
            attributes_to_apply[attribute] = attribute_value

    # Now we create the needed config and apply overrides or return defaults
    match engine:
        case "postgres":
            defaults = {
                "host": "localhost",
                "port": 5432,
                "database": "agents",
                "user": "agents",
                "password": "agents",
            }
            config = {**defaults, **attributes_to_apply}
            return PostgresDataConnectionConfiguration(**config)
        case "snowflake":
            defaults = {
                "credential_type": "user_password",
                "account": os.getenv("SNOWFLAKE_ACCOUNT"),
                "user": os.getenv("SNOWFLAKE_USERNAME"),
                "password": os.getenv("SNOWFLAKE_PASSWORD"),
                "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH"),
                "database": "SNOWFLAKE_SAMPLE_DATA",  # Placeholder, will be replaced by test DB
                "schema": "PUBLIC",  # Placeholder, will be replaced by test schema
                "role": os.getenv("SNOWFLAKE_ROLE", "SYSADMIN"),
            }
            config = {**defaults, **attributes_to_apply}
            return SnowflakeDataConnectionConfiguration(**config)
        case "databricks":
            defaults = {
                "server_hostname": os.getenv("DATABRICKS_SERVER_HOSTNAME", None),
                "http_path": os.getenv("DATABRICKS_HTTP_PATH", None),
                "access_token": os.getenv("DATABRICKS_ACCESS_TOKEN", None),
                "catalog": os.getenv("DATABRICKS_CATALOG", "hive_metastore"),
                # Base schema, will create test schema within
                "schema": os.getenv("DATABRICKS_SCHEMA", "default"),
            }
            config = {**defaults, **attributes_to_apply}
            return DatabricksDataConnectionConfiguration(**config)
        case "redshift":
            defaults = {
                "host": os.getenv("REDSHIFT_HOST"),
                "port": int(os.getenv("REDSHIFT_PORT", "5439")),
                "database": os.getenv("REDSHIFT_DATABASE"),
                "user": os.getenv("REDSHIFT_USER"),
                "password": os.getenv("REDSHIFT_PASSWORD"),
                "schema": os.getenv("REDSHIFT_SCHEMA", "public"),  # Base schema
            }
            config = {**defaults, **attributes_to_apply}
            return RedshiftDataConnectionConfiguration(**config)
        case "mysql":
            defaults = {
                "host": "127.0.0.1",  # Use 127.0.0.1 to force TCP/IP instead of Unix socket
                "port": 3306,
                "database": "mydb",
                "user": "root",
                "password": "mymysql",
            }
            config = {**defaults, **attributes_to_apply}
            return MySQLDataConnectionConfiguration(**config)


def _load_sql_files(
    resources_path: Path,
    engine: "DataConnectionEngine",
) -> tuple[str, str]:
    """
    Load schema and data SQL files for the given engine.

    Args:
        resources_path: Base path to semantic data model resources
        engine: Database engine type

    Returns:
        tuple[str, str]: (schema_sql, data_sql)

    Raises:
        FileNotFoundError: If required SQL files are not found
    """
    schema_file = resources_path / engine / "schema.sql"

    # Try engine-specific data file first, fall back to shared
    engine_data_file = resources_path / engine / "data.sql"
    shared_data_file = resources_path / "shared" / "data.sql"

    data_file = engine_data_file if engine_data_file.exists() else shared_data_file

    if not schema_file.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_file}\nExpected schema file for {engine} engine.")

    if not data_file.exists():
        raise FileNotFoundError(f"Data file not found: {data_file}\nExpected data file for {engine} engine.")

    schema_sql = schema_file.read_text()
    data_sql = data_file.read_text()

    return schema_sql, data_sql


@contextmanager
def _initialize_postgres_database(
    config: "PostgresDataConnectionConfiguration",
    resources_path: Path,
) -> "Generator[str, Any, Any]":
    """
    Context manager that initializes a Postgres database for testing.

    Creates a unique schema, loads the DDL and DML, then cleans up on exit.

    Args:
        config: Postgres connection configuration
        resources_path: Path to semantic data model resources

    Yields:
        str: The test schema name that was created
    """
    import sqlalchemy as sa

    # Generate a unique schema name for test isolation
    test_schema = f"test_sdm_{uuid.uuid4().hex[:8]}"

    # Build connection URL for SQLAlchemy
    # Default to sslmode=disable for internal Docker connections if not specified
    sslmode = config.sslmode.value if config.sslmode else "disable"
    db_url = (
        f"postgresql+psycopg://{config.user}:{config.password}"
        f"@{config.host}:{int(config.port)}"
        f"/{config.database}?sslmode={sslmode}"
    )

    # Create SQLAlchemy engine (sync for fixture simplicity)
    sa_engine = sa.create_engine(db_url, echo=False)

    # Load SQL files
    schema_sql, data_sql = _load_sql_files(resources_path, "postgres")

    try:
        with sa_engine.begin() as conn:
            # Create the test schema
            conn.execute(sa.text(f"CREATE SCHEMA {test_schema}"))

            # Set the search path to our test schema so all tables get created there
            conn.execute(sa.text(f"SET search_path TO {test_schema}"))

            # Load schema (DDL) - engine-specific
            conn.execute(sa.text(schema_sql))

            # Load data (DML) - shared across engines
            conn.execute(sa.text(data_sql))

            # Load edge case schema and data if they exist
            edge_case_schema_file = resources_path / "postgres" / "edge_cases_schema.sql"
            edge_case_data_file = resources_path / "postgres" / "edge_cases_data.sql"

            if edge_case_schema_file.exists():
                edge_case_schema_sql = edge_case_schema_file.read_text()
                conn.execute(sa.text(edge_case_schema_sql))

            if edge_case_data_file.exists():
                edge_case_data_sql = edge_case_data_file.read_text()
                conn.execute(sa.text(edge_case_data_sql))

            # Load documents schema and data for JSON/JSONB testing
            documents_schema_file = resources_path / "postgres" / "documents_schema.sql"
            documents_data_file = resources_path / "postgres" / "documents_data.sql"

            if documents_schema_file.exists():
                documents_schema_sql = documents_schema_file.read_text()
                conn.execute(sa.text(documents_schema_sql))

            if documents_data_file.exists():
                documents_data_sql = documents_data_file.read_text()
                conn.execute(sa.text(documents_data_sql))

            # Load composite FK schema for testing composite foreign key detection
            composite_fk_schema_file = resources_path / "postgres" / "composite_fk_schema.sql"
            if composite_fk_schema_file.exists():
                composite_fk_schema_sql = composite_fk_schema_file.read_text(encoding="utf-8")
                conn.execute(sa.text(composite_fk_schema_sql))

            # Load UNIQUE INDEX FK schema for testing BIRD database scenario
            # where FKs reference UNIQUE INDEX instead of PRIMARY KEY
            unique_index_fk_schema_file = resources_path / "postgres" / "unique_index_fk_schema.sql"
            if unique_index_fk_schema_file.exists():
                unique_index_fk_schema_sql = unique_index_fk_schema_file.read_text(encoding="utf-8")
                conn.execute(sa.text(unique_index_fk_schema_sql))

            # Load PK + UNIQUE CONSTRAINT FK schema for testing FK detection
            # when parent table has both PRIMARY KEY and separate UNIQUE CONSTRAINT
            pk_unique_constraint_fk_schema_file = resources_path / "postgres" / "pk_unique_constraint_fk_schema.sql"
            if pk_unique_constraint_fk_schema_file.exists():
                pk_unique_constraint_fk_schema_sql = pk_unique_constraint_fk_schema_file.read_text(encoding="utf-8")
                conn.execute(sa.text(pk_unique_constraint_fk_schema_sql))

        yield test_schema

    finally:
        # Cleanup: drop the schema and everything in it
        try:
            with sa_engine.begin() as conn:
                conn.execute(sa.text(f"DROP SCHEMA IF EXISTS {test_schema} CASCADE"))
        except Exception as e:
            print(f"Warning: Failed to drop test schema {test_schema}: {e}")
        finally:
            sa_engine.dispose()


@contextmanager
def _initialize_mysql_database(
    config: "MySQLDataConnectionConfiguration",
    resources_path: Path,
) -> "Generator[str, Any, Any]":
    """
    Context manager that initializes a MySQL database for testing.

    Creates a unique database, loads the DDL and DML, then cleans up on exit.

    Args:
        config: MySQL connection configuration
        resources_path: Path to semantic data model resources

    Yields:
        str: The test database name that was created
    """
    import MySQLdb

    # Generate a unique database name for test isolation
    test_database = f"test_sdm_{uuid.uuid4().hex[:8]}"

    # Connect to MySQL (without specifying a database initially)
    # Force TCP/IP connection by using 127.0.0.1 instead of localhost
    host = "127.0.0.1" if config.host == "localhost" else config.host
    conn = MySQLdb.connect(
        host=host,
        port=int(config.port),
        user=config.user,
        password=config.password,
    )

    try:
        cursor = conn.cursor()

        # Create the test database
        cursor.execute(f"CREATE DATABASE {test_database}")
        cursor.execute(f"USE {test_database}")

        # Load SQL files
        schema_sql, data_sql = _load_sql_files(resources_path, "mysql")

        # Execute DDL (schema)
        # Split by semicolon and execute each statement
        for statement in schema_sql.split(";"):
            statement = statement.strip()  # noqa: PLW2901
            if statement:
                cursor.execute(statement)

        # Execute DML (data)
        for statement in data_sql.split(";"):
            statement = statement.strip()  # noqa: PLW2901
            if statement:
                cursor.execute(statement)

        # Load edge case schema and data if they exist
        edge_case_schema_file = resources_path / "mysql" / "edge_cases_schema.sql"
        edge_case_data_file = resources_path / "mysql" / "edge_cases_data.sql"

        if edge_case_schema_file.exists():
            edge_case_schema_sql = edge_case_schema_file.read_text()
            for statement in edge_case_schema_sql.split(";"):
                statement = statement.strip()  # noqa: PLW2901
                if statement:
                    cursor.execute(statement)

        if edge_case_data_file.exists():
            edge_case_data_sql = edge_case_data_file.read_text()
            for statement in edge_case_data_sql.split(";"):
                statement = statement.strip()  # noqa: PLW2901
                if statement:
                    cursor.execute(statement)

        # Load composite FK schema for testing composite foreign key detection
        composite_fk_schema_file = resources_path / "mysql" / "composite_fk_schema.sql"
        if composite_fk_schema_file.exists():
            composite_fk_schema_sql = composite_fk_schema_file.read_text(encoding="utf-8")
            for statement in composite_fk_schema_sql.split(";"):
                statement = statement.strip()  # noqa: PLW2901
                if statement:
                    cursor.execute(statement)

        # Load UNIQUE INDEX FK schema for testing the scenario
        # where FKs reference UNIQUE INDEX instead of PRIMARY KEY
        unique_index_fk_schema_file = resources_path / "mysql" / "unique_index_fk_schema.sql"
        if unique_index_fk_schema_file.exists():
            unique_index_fk_schema_sql = unique_index_fk_schema_file.read_text(encoding="utf-8")
            for statement in unique_index_fk_schema_sql.split(";"):
                statement = statement.strip()  # noqa: PLW2901
                if statement:
                    cursor.execute(statement)

        # Load PK + UNIQUE CONSTRAINT FK schema for testing FK detection
        # when parent table has both PRIMARY KEY and separate UNIQUE CONSTRAINT
        pk_unique_constraint_fk_schema_file = resources_path / "mysql" / "pk_unique_constraint_fk_schema.sql"
        if pk_unique_constraint_fk_schema_file.exists():
            pk_unique_constraint_fk_schema_sql = pk_unique_constraint_fk_schema_file.read_text(encoding="utf-8")
            for statement in pk_unique_constraint_fk_schema_sql.split(";"):
                statement = statement.strip()  # noqa: PLW2901
                if statement:
                    cursor.execute(statement)

        conn.commit()

        yield test_database

    finally:
        # Cleanup: drop the database
        try:
            cursor.execute(f"DROP DATABASE IF EXISTS {test_database}")
            conn.commit()
        except Exception as e:
            print(f"Warning: Failed to drop test database {test_database}: {e}")
        finally:
            cursor.close()
            conn.close()


@contextmanager
def _initialize_snowflake_database(
    config: "SnowflakeDataConnectionConfiguration",
    resources_path: Path,
) -> "Generator[str, Any, Any]":
    """
    Context manager that initializes a Snowflake database for testing.

    Creates a unique database, loads the DDL and DML, then cleans up on exit.

    Args:
        config: Snowflake connection configuration
        resources_path: Path to semantic data model resources

    Yields:
        str: The test database name that was created
    """
    import snowflake.connector

    # Generate unique database name
    test_database = f"TEST_SDM_{uuid.uuid4().hex[:8].upper()}"

    # Connect to Snowflake
    conn_params = {
        "user": config.user,
        "password": config.password,
        "account": config.account,
        "warehouse": config.warehouse,
    }
    if config.role:
        conn_params["role"] = config.role

    conn = snowflake.connector.connect(**conn_params)

    try:
        cursor = conn.cursor()

        # Create test database (PUBLIC schema is created automatically)
        cursor.execute(f"CREATE DATABASE {test_database}")
        cursor.execute(f"USE DATABASE {test_database}")
        cursor.execute("USE SCHEMA PUBLIC")  # PUBLIC schema exists by default
        # Explicitly set warehouse again after database switch (Snowflake deactivates it)
        cursor.execute(f"USE WAREHOUSE {config.warehouse}")

        # Load schema and data
        schema_sql, data_sql = _load_sql_files(resources_path, "snowflake")

        # Split SQL into statements, filtering out empty ones and comments-only
        def clean_statements(sql: str) -> list[str]:
            statements = []
            for raw_stmt in sql.split(";"):
                # Remove leading/trailing whitespace
                stmt = raw_stmt.strip()
                # Remove lines that are only comments
                lines = [line for line in stmt.split("\n") if line.strip() and not line.strip().startswith("--")]
                cleaned = "\n".join(lines).strip()
                if cleaned:
                    statements.append(cleaned)
            return statements

        # Execute DDL (tables, then indexes separately)
        ddl_statements = clean_statements(schema_sql)

        # Separate table creates from other statements
        table_statements = [s for s in ddl_statements if "CREATE TABLE" in s.upper()]
        comment_statements = [s for s in ddl_statements if "COMMENT ON" in s.upper()]

        # Create tables
        for statement in table_statements:
            cursor.execute(statement)

        # Add comments (optional, failures are OK)
        for statement in comment_statements:
            try:
                cursor.execute(statement)
            except Exception:
                # Comments are nice-to-have but not critical
                pass

        # Execute DML (load data)
        dml_statements = clean_statements(data_sql)
        for statement in dml_statements:
            cursor.execute(statement)

        # Load edge cases if they exist
        edge_case_schema_file = resources_path / "snowflake" / "edge_cases_schema.sql"
        if edge_case_schema_file.exists():
            edge_case_schema_sql = edge_case_schema_file.read_text()
            for statement in edge_case_schema_sql.split(";"):
                if statement.strip():
                    cursor.execute(statement)

        edge_case_data_file = resources_path / "snowflake" / "edge_cases_data.sql"
        if edge_case_data_file.exists():
            edge_case_data_sql = edge_case_data_file.read_text()
            for statement in edge_case_data_sql.split(";"):
                if statement.strip():
                    cursor.execute(statement)

        yield test_database

    finally:
        # Cleanup
        try:
            cursor.execute(f"DROP DATABASE IF EXISTS {test_database}")
        except Exception as e:
            print(f"Warning: Failed to drop test database {test_database}: {e}")
        finally:
            cursor.close()
            conn.close()


@contextmanager
def _initialize_databricks_database(
    config: "DatabricksDataConnectionConfiguration",
    resources_path: Path,
) -> "Generator[str, Any, Any]":
    """
    Context manager that initializes a Databricks database for testing.

    Creates a unique schema, loads the DDL and DML, then cleans up on exit.

    Args:
        config: Databricks connection configuration
        resources_path: Path to semantic data model resources

    Yields:
        str: The test schema name that was created
    """
    from databricks import sql as databricks_sql

    # Generate unique schema name
    test_schema = f"test_sdm_{uuid.uuid4().hex[:8]}"

    # Connect to Databricks
    conn = databricks_sql.connect(
        server_hostname=config.server_hostname,
        http_path=config.http_path,
        access_token=config.access_token,
    )

    try:
        cursor = conn.cursor()

        # Create test schema in the configured catalog
        catalog = config.catalog or "hive_metastore"
        # For Unity Catalog, use separate USE CATALOG and USE SCHEMA commands
        cursor.execute(f"USE CATALOG {catalog}")
        cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {test_schema}")
        cursor.execute(f"USE SCHEMA {test_schema}")

        # Load schema and data
        schema_sql, data_sql = _load_sql_files(resources_path, "databricks")

        # Split SQL into statements, filtering out empty ones and comments-only
        def clean_statements(sql: str) -> list[str]:
            statements = []
            for raw_stmt in sql.split(";"):
                # Remove leading/trailing whitespace
                stmt = raw_stmt.strip()
                # Remove lines that are only comments
                lines = [line for line in stmt.split("\n") if line.strip() and not line.strip().startswith("--")]
                cleaned = "\n".join(lines).strip()
                if cleaned:
                    statements.append(cleaned)
            return statements

        # Execute DDL (tables)
        ddl_statements = clean_statements(schema_sql)

        for statement in ddl_statements:
            cursor.execute(statement)

        # Execute DML (load data)
        dml_statements = clean_statements(data_sql)
        for statement in dml_statements:
            cursor.execute(statement)

        # Load edge cases if they exist
        edge_case_schema_file = resources_path / "databricks" / "edge_cases_schema.sql"
        if edge_case_schema_file.exists():
            edge_case_schema_sql = edge_case_schema_file.read_text()
            for statement in clean_statements(edge_case_schema_sql):
                cursor.execute(statement)

        edge_case_data_file = resources_path / "databricks" / "edge_cases_data.sql"
        if edge_case_data_file.exists():
            edge_case_data_sql = edge_case_data_file.read_text()
            for statement in clean_statements(edge_case_data_sql):
                cursor.execute(statement)

        yield test_schema

    finally:
        # Cleanup
        try:
            cursor.execute(f"USE CATALOG {catalog}")
            cursor.execute(f"DROP SCHEMA IF EXISTS {test_schema} CASCADE")
        except Exception as e:
            print(f"Warning: Failed to drop test schema {catalog}.{test_schema}: {e}")
        finally:
            cursor.close()
            conn.close()


@contextmanager
def _initialize_redshift_database(
    config: "RedshiftDataConnectionConfiguration",
    resources_path: Path,
) -> "Generator[str, Any, Any]":
    """
    Context manager that initializes a Redshift database for testing.

    Creates a unique schema, loads the DDL and DML, then cleans up on exit.

    Args:
        config: Redshift connection configuration
        resources_path: Path to semantic data model resources

    Yields:
        str: The test schema name that was created
    """
    import redshift_connector

    # Generate a unique schema name for test isolation
    test_schema = f"test_sdm_{uuid.uuid4().hex[:8]}"

    # Connect to Redshift using redshift_connector
    # Note: We use redshift_connector instead of psycopg2/3 for better Redshift compatibility
    conn_params = {
        "host": config.host,
        "port": int(config.port),
        "database": config.database,
        "user": config.user,
        "password": config.password,
    }

    # Add SSL mode if specified
    if config.sslmode:
        conn_params["ssl"] = config.sslmode.value != "disable"

    conn = redshift_connector.connect(**conn_params)

    # Load SQL files
    schema_sql, data_sql = _load_sql_files(resources_path, "redshift")

    try:
        cursor = conn.cursor()

        # Create the test schema
        cursor.execute(f"CREATE SCHEMA {test_schema}")

        # Set the search path to our test schema so all tables get created there
        cursor.execute(f"SET search_path TO {test_schema}")

        # Split SQL into statements, filtering out empty ones and comments-only
        def clean_statements(sql: str) -> list[str]:
            statements = []
            for raw_stmt in sql.split(";"):
                # Remove leading/trailing whitespace
                stmt = raw_stmt.strip()
                # Remove lines that are only comments
                lines = [line for line in stmt.split("\n") if line.strip() and not line.strip().startswith("--")]
                cleaned = "\n".join(lines).strip()
                if cleaned:
                    statements.append(cleaned)
            return statements

        # Execute DDL (schema)
        ddl_statements = clean_statements(schema_sql)
        for statement in ddl_statements:
            cursor.execute(statement)

        # Execute DML (data)
        dml_statements = clean_statements(data_sql)
        for statement in dml_statements:
            cursor.execute(statement)

        # Load edge case schema and data if they exist
        edge_case_schema_file = resources_path / "redshift" / "edge_cases_schema.sql"
        if edge_case_schema_file.exists():
            edge_case_schema_sql = edge_case_schema_file.read_text()
            for statement in clean_statements(edge_case_schema_sql):
                cursor.execute(statement)

        edge_case_data_file = resources_path / "redshift" / "edge_cases_data.sql"
        if edge_case_data_file.exists():
            edge_case_data_sql = edge_case_data_file.read_text()
            for statement in clean_statements(edge_case_data_sql):
                cursor.execute(statement)

        conn.commit()
        yield test_schema

    finally:
        # Cleanup: drop the schema and everything in it
        # Create a fresh connection for cleanup to avoid connection closure issues
        try:
            cleanup_conn = redshift_connector.connect(**conn_params)
            cleanup_cursor = cleanup_conn.cursor()
            cleanup_cursor.execute(f"DROP SCHEMA IF EXISTS {test_schema} CASCADE")
            cleanup_conn.commit()
            cleanup_cursor.close()
            cleanup_conn.close()
        except Exception as e:
            print(f"Warning: Failed to drop test schema {test_schema}: {e}")
        finally:
            # Close the original connection if still open
            try:
                if cursor:
                    cursor.close()
            except Exception:
                pass
            try:
                if conn:
                    conn.close()
            except Exception:
                pass


@pytest.fixture(scope="module")
def initialize_data_base(
    engine: "DataConnectionEngine",
    semantic_data_model_resources_path: Path,
    sdm_seed_data_connection_configuration: "DataConnectionConfiguration",
) -> "Generator[str, Any, Any]":
    """
    Fixture that initializes a data base or data warehouse for the given engine so we
    can use it for testing Semantic Data Models.

    It uses the data connection configuration as the basis for it's own connection details.

    It loads:
    1. Schema file from {engine}/schema.sql (DDL - tables, indexes, constraints)
    2. Data file from shared/data.sql (DML - INSERT statements)

    It will clean up the data base or data warehouse after the test.

    Yields:
        str: The schema name (for Postgres) or database name (for other engines) that was created
    """
    from agent_platform.core.payloads.data_connection import (
        DatabricksDataConnectionConfiguration,
        MySQLDataConnectionConfiguration,
        PostgresDataConnectionConfiguration,
        RedshiftDataConnectionConfiguration,
        SnowflakeDataConnectionConfiguration,
    )

    # Select the appropriate context manager based on the engine
    match engine:
        case "postgres":
            assert isinstance(sdm_seed_data_connection_configuration, PostgresDataConnectionConfiguration)
            ctx = _initialize_postgres_database(
                sdm_seed_data_connection_configuration,
                semantic_data_model_resources_path,
            )
        case "snowflake":
            assert isinstance(sdm_seed_data_connection_configuration, SnowflakeDataConnectionConfiguration)
            ctx = _initialize_snowflake_database(
                sdm_seed_data_connection_configuration,
                semantic_data_model_resources_path,
            )
        case "databricks":
            assert isinstance(sdm_seed_data_connection_configuration, DatabricksDataConnectionConfiguration)
            ctx = _initialize_databricks_database(
                sdm_seed_data_connection_configuration,
                semantic_data_model_resources_path,
            )
        case "redshift":
            assert isinstance(sdm_seed_data_connection_configuration, RedshiftDataConnectionConfiguration)
            ctx = _initialize_redshift_database(
                sdm_seed_data_connection_configuration,
                semantic_data_model_resources_path,
            )
        case "mysql":
            assert isinstance(sdm_seed_data_connection_configuration, MySQLDataConnectionConfiguration)
            ctx = _initialize_mysql_database(
                sdm_seed_data_connection_configuration,
                semantic_data_model_resources_path,
            )
        case _:
            pytest.skip(f"Engine {engine} not yet supported for database initialization")

    # Use the selected context manager
    with ctx as db_identifier:
        yield db_identifier


@pytest.fixture(scope="module")
def sdm_data_connection_configuration(
    engine: "DataConnectionEngine", initialize_data_base: str
) -> "DataConnectionConfiguration":
    """
    Fixture that provides a DataConnectionConfiguration for semantic data model tests.

    This configuration is used to configure the data connection used by the agent server
    when running semantic data model tests against a database. It includes the test schema
    from the initialize_data_base fixture.

    Can be overridden via environment variables with the
    following pattern (excluding the database identifier):

        SDM_DATA_CONNECTION_{ENGINE}_{ATTRIBUTE} where {ENGINE} is the engine to test against
        and {ATTRIBUTE} is the attribute to override. Attirbute name needs to match the
        expected attribute for the given engine based on the DataConnectionConfiguration class.

    The most common example is to override the host because you are running the agent server
    outide of the docker compose stack network. In that case, you would run tests like this:

    ```bash
    SPAR_DATA_SERVER_HOST=localhost SDM_DATA_CONNECTION_POSTGRES_HOST=localhost uv run pytest -v -m semantic_data_models
    ```
    """
    from dataclasses import fields

    from agent_platform.core.payloads.data_connection import (
        DatabricksDataConnectionConfiguration,
        MySQLDataConnectionConfiguration,
        PostgresDataConnectionConfiguration,
        RedshiftDataConnectionConfiguration,
        SnowflakeDataConnectionConfiguration,
    )

    attributes_to_collect: list[str] = []
    attributes_to_apply: dict[str, Any] = {}

    match engine:
        case "postgres":
            fields_to_collect = fields(PostgresDataConnectionConfiguration)
        case "snowflake":
            fields_to_collect = fields(SnowflakeDataConnectionConfiguration)
        case "databricks":
            fields_to_collect = fields(DatabricksDataConnectionConfiguration)
        case "redshift":
            fields_to_collect = fields(RedshiftDataConnectionConfiguration)
        case "mysql":
            fields_to_collect = fields(MySQLDataConnectionConfiguration)
        case _:
            raise ValueError(f"Unsupported engine: {engine}")

    attributes_to_collect = [f.name for f in fields_to_collect]
    for attribute in attributes_to_collect:
        attribute_value = os.getenv(f"SDM_DATA_CONNECTION_{engine.upper()}_{attribute.upper()}", None)
        if attribute_value is not None:
            attributes_to_apply[attribute] = attribute_value

    # Now we create the needed config and apply overrides or return defaults
    match engine:
        case "postgres":
            defaults = {
                "host": "postgres",
                "port": 5432,
                "database": "agents",
                "user": "agents",
                "password": "agents",
                "schema": initialize_data_base,
            }
            attributes_to_apply.pop("schema", None)
            config = {**defaults, **attributes_to_apply}
            return PostgresDataConnectionConfiguration(**config)
        case "snowflake":
            defaults = {
                "credential_type": "user_password",
                "account": os.getenv("SNOWFLAKE_ACCOUNT"),
                "user": os.getenv("SNOWFLAKE_USERNAME"),
                "password": os.getenv("SNOWFLAKE_PASSWORD"),
                "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH"),
                "database": initialize_data_base,  # Uses test database from fixture
                "schema": "PUBLIC",
            }
            if os.getenv("SNOWFLAKE_ROLE"):
                defaults["role"] = os.getenv("SNOWFLAKE_ROLE")
            attributes_to_apply.pop("database", None)  # Don't allow override
            config = {**defaults, **attributes_to_apply}
            return SnowflakeDataConnectionConfiguration(**config)
        case "databricks":
            defaults = {
                "server_hostname": os.getenv("DATABRICKS_SERVER_HOSTNAME", None),
                "http_path": os.getenv("DATABRICKS_HTTP_PATH", None),
                "access_token": os.getenv("DATABRICKS_ACCESS_TOKEN", None),
                "catalog": os.getenv("DATABRICKS_CATALOG", "hive_metastore"),
                "schema": initialize_data_base,  # Uses test schema from fixture
            }
            attributes_to_apply.pop("schema", None)  # Don't allow override of test schema
            config = {**defaults, **attributes_to_apply}
            return DatabricksDataConnectionConfiguration(**config)
        case "redshift":
            defaults = {
                "host": os.getenv("REDSHIFT_HOST"),
                "port": int(os.getenv("REDSHIFT_PORT", "5439")),
                "database": os.getenv("REDSHIFT_DATABASE"),
                "user": os.getenv("REDSHIFT_USER"),
                "password": os.getenv("REDSHIFT_PASSWORD"),
                "schema": initialize_data_base,  # Uses test schema from fixture
            }
            attributes_to_apply.pop("schema", None)  # Don't allow override of test schema
            config = {**defaults, **attributes_to_apply}
            return RedshiftDataConnectionConfiguration(**config)
        case "mysql":
            # For Docker: use host.docker.internal to reach host's MySQL
            # For local: can be overridden with SDM_DATA_CONNECTION_MYSQL_HOST=127.0.0.1
            defaults = {
                "host": "host.docker.internal",  # Docker needs this to reach host
                "port": 3306,
                "database": initialize_data_base,  # Uses test database from fixture
                "user": "root",
                "password": "mymysql",
            }
            attributes_to_apply.pop("database", None)  # Don't allow override
            config = {**defaults, **attributes_to_apply}
            return MySQLDataConnectionConfiguration(**config)


@pytest.fixture(scope="module")
def sdm_data_connection(
    engine: "DataConnectionEngine",
    sdm_data_connection_configuration: "DataConnectionConfiguration",
) -> "DataConnection":
    """
    Fixture that provides a DataConnection for semantic data model tests.

    It uses the sdm_data_connection_configuration fixture to create the data connection.
    """
    from agent_platform.core.data_connections import DataConnection

    return DataConnection(
        id="sdm-test-connection",
        name="SemanticDataModelTest",
        description="Test data connection for semantic data models",
        engine=engine,
        configuration=sdm_data_connection_configuration,
    )


@pytest.fixture(scope="module")
def agent_server_client_with_data_connection(
    agent_server_client: "AgentServerClient",
    sdm_data_connection: "DataConnection",
) -> "Generator[tuple[AgentServerClient, DataConnection], Any, Any]":
    """
    Provides an AgentServerClient with a data connection already created for testing.

    This fixture creates a data connection on the agent server using the
    sdm_data_connection (which includes the test schema from initialize_data_base).

    Returns:
        tuple[AgentServerClient, DataConnection]: A tuple of (client, data_connection)
            where data_connection is a properly typed DataConnection object
    """
    from dataclasses import asdict

    from agent_platform.core.data_connections import DataConnection

    result = agent_server_client.create_data_connection(
        name=sdm_data_connection.name,
        description=sdm_data_connection.description,
        engine=sdm_data_connection.engine,
        configuration=asdict(sdm_data_connection.configuration),
    )

    data_connection = DataConnection.model_validate(result)

    try:
        yield agent_server_client, data_connection
    finally:
        # Cleanup: delete the data connection
        if data_connection.id:
            try:
                agent_server_client.delete_data_connection(data_connection.id)
            except Exception as e:
                print(f"Warning: Failed to delete data connection {data_connection.id}: {e}")
