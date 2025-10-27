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
        DataConnectionConfiguration,
        DataConnectionEngine,
        PostgresDataConnectionConfiguration,
    )


@pytest.fixture(scope="session")
def semantic_data_model_resources_path(spar_resources_path: Path) -> Path:
    return spar_resources_path / "semantic_data_models"


@pytest.fixture(scope="module", params=["postgres"])
def engine(request: pytest.FixtureRequest) -> "DataConnectionEngine":
    """
    Parametrized fixture that provides the database engine to test against.

    When you add more engines, just add them to the params list:
    @pytest.fixture(params=["postgres", "snowflake", "bigquery"])

    All tests that use this fixture (or fixtures that depend on it) will run
    once for each engine in the params list.
    """
    return request.param


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

    from agent_platform.core.payloads.data_connection import PostgresDataConnectionConfiguration

    attributes_to_collect: list[str] = []
    attributes_to_apply: dict[str, Any] = {}

    match engine:
        case "postgres":
            fields_to_collect = fields(PostgresDataConnectionConfiguration)
        case _:
            raise ValueError(f"Unsupported engine: {engine}")

    attributes_to_collect = [f.name for f in fields_to_collect]
    for attribute in attributes_to_collect:
        attribute_value = os.getenv(
            f"SDM_SEED_DATA_CONNECTION_{engine.upper()}_{attribute.upper()}", None
        )
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
    data_file = resources_path / "shared" / "data.sql"

    if not schema_file.exists():
        raise FileNotFoundError(
            f"Schema file not found: {schema_file}\nExpected schema file for {engine} engine."
        )

    if not data_file.exists():
        raise FileNotFoundError(
            f"Data file not found: {data_file}\nExpected data file for {engine} engine."
        )

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
    from agent_platform.core.payloads.data_connection import PostgresDataConnectionConfiguration

    # Select the appropriate context manager based on the engine
    match engine:
        case "postgres":
            assert isinstance(
                sdm_seed_data_connection_configuration, PostgresDataConnectionConfiguration
            )
            ctx = _initialize_postgres_database(
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
    """  # noqa: E501
    from dataclasses import fields

    from agent_platform.core.payloads.data_connection import PostgresDataConnectionConfiguration

    attributes_to_collect: list[str] = []
    attributes_to_apply: dict[str, Any] = {}

    match engine:
        case "postgres":
            fields_to_collect = fields(PostgresDataConnectionConfiguration)
        case _:
            raise ValueError(f"Unsupported engine: {engine}")

    attributes_to_collect = [f.name for f in fields_to_collect]
    for attribute in attributes_to_collect:
        attribute_value = os.getenv(
            f"SDM_DATA_CONNECTION_{engine.upper()}_{attribute.upper()}", None
        )
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
) -> tuple["AgentServerClient", "DataConnection"]:
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

    return agent_server_client, data_connection
