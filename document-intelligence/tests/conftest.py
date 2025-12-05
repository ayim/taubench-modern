import json
import os
import sys
import time
import typing
from pathlib import Path
from urllib.parse import urlparse

import psycopg2
import pytest
import sema4ai_http
from dotenv import load_dotenv
from sema4ai.data import DataSource
from testcontainers.postgres import PostgresContainer

from sema4ai_docint.extraction import SyncExtractionClient
from sema4ai_docint.models.initialize import initialize_database
from sema4ai_docint.views.schema import BusinessSchema

# Add the sema4ai_docint directory to the Python path
sema4ai_docint_path = str(Path(__file__).parent.parent)
sys.path.insert(0, sema4ai_docint_path)

if typing.TYPE_CHECKING:
    from tests.data_server_cli_wrapper import DataServerCliWrapper

# Test constants
test_schema_name = "extraction_schema"

# Load test data from files
SAMPLE_SCHEMA: dict[str, typing.Any] = {}  # Will be populated with actual test data
SAMPLE_DOCUMENT: dict[str, typing.Any] = {}  # Will be populated with actual test data
VALIDATION_RULES: dict[str, typing.Any] = {}  # Will be populated with actual test data

# Add more fixtures from data_server_fixtures.py and agent_server_fixtures.py
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
pytest_plugins = [
    "tests.data_server_fixtures",
    "tests.agent_server_fixtures",
    "tests.services.fixture",
]

# Global reference to store agent server CLI wrapper for log dumping
_current_agent_server_cli = None


def pytest_runtest_makereport(item, call):
    """Hook to capture test results and store failure info for later log dumping."""
    # Store the test result on the item for later access
    if call.when == "call":
        item._test_failed = call.excinfo is not None
        item._test_nodeid = item.nodeid


def pytest_runtest_teardown(item, nextitem):
    """Hook to dump agent server logs after test teardown, closer to other captured logs."""

    # Check if test failed and dump logs if so
    if (
        hasattr(item, "_test_failed")
        and item._test_failed
        and _current_agent_server_cli is not None
    ):
        print(f"\n=== Agent server logs for failed test {item._test_nodeid} ===")
        try:
            _current_agent_server_cli.dump_logs_to_console()
        except Exception as e:
            print(f"Failed to dump agent server logs: {e}")


@pytest.fixture(scope="session")
def _track_agent_server_cli(agent_server_cli):
    """Track the agent server CLI wrapper for log dumping on test failures."""
    _current_agent_server_cli = agent_server_cli
    try:
        yield agent_server_cli
    finally:
        _current_agent_server_cli = None


def load_schema(schema_or_filename: str, filename: str | None = None):
    """Load a schema from the test-data directory.

    Args:
        schema_or_filename: If filename is None, this is the filename in models test-data.
                           Otherwise, this is the schema subdirectory name.
        filename: The filename within the schema subdirectory (for views tests).
    """
    if filename is None:
        # models style: load_schema(filename)
        schema_file = Path(__file__).parent / "models" / "test-data" / schema_or_filename
    else:
        # views style: load_schema(schema, filename)
        schema_file = Path(__file__).parent / "views" / "test-data" / schema_or_filename / filename

    with open(schema_file) as f:
        return json.load(f)


def load_document(schema_or_filename: str, filename: str | None = None):
    """Load a document from the test-data directory.

    Args:
        schema_or_filename: If filename is None, this is the filename in models test-data.
                           Otherwise, this is the schema subdirectory name.
        filename: The filename within the schema subdirectory (for views tests).
    """
    if filename is None:
        # models style: load_document(filename)
        document_file = Path(__file__).parent / "models" / "test-data" / schema_or_filename
    else:
        # views style: load_document(schema, filename)
        document_file = (
            Path(__file__).parent / "views" / "test-data" / schema_or_filename / filename
        )

    with open(document_file) as f:
        return json.load(f)


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Automatically skip eval tests unless explicitly requested via markers."""
    markexpr = getattr(config.option, "markexpr", None) or ""

    # Define eval markers to skip unless explicitly requested
    eval_markers = {
        "schema_eval": "Use -m schema_eval to run schema evaluation tests",
        "nl2sql_eval": "Use -m nl2sql_eval to run NL-to-SQL evaluation tests",
    }

    # Skip each eval marker type unless explicitly requested
    for marker_name, skip_reason in eval_markers.items():
        if marker_name not in markexpr:
            skip_marker = pytest.mark.skip(reason=skip_reason)
            for item in items:
                if marker_name in item.keywords:
                    item.add_marker(skip_marker)


@pytest.fixture(scope="session")
def postgres():
    """Create a database connection to the PostgreSQL container."""
    max_retries = 5
    retry_delay = 2

    with PostgresContainer("pgvector/pgvector:pg17") as postgres:
        url = urlparse(postgres.get_connection_url())

        # Add retry logic for connection
        for attempt in range(max_retries):
            try:
                props = {
                    "host": url.hostname,
                    "port": url.port,
                    "user": url.username,
                    "password": url.password,
                    "dbname": url.path.lstrip("/"),
                }
                conn = psycopg2.connect(**props)
                conn.autocommit = True

                # Test the connection and ensure pgvector extension is available
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1")
                break
            except psycopg2.OperationalError as e:
                if attempt == max_retries - 1:
                    raise Exception(
                        f"Failed to connect to PostgreSQL after {max_retries} attempts: {e!s}"
                    ) from e
                print(
                    f"Connection attempt {attempt + 1} failed, retrying in {retry_delay} seconds..."
                )
                time.sleep(retry_delay)

        yield conn, props

        if conn:
            conn.close()


@pytest.fixture(scope="session")
def existing_postgres():
    """Connect to existing PostgreSQL container."""
    # Load environment variables from .env file
    load_dotenv()

    # Get database connection details from environment variables
    props = {
        "host": os.getenv("POSTGRES_HOST", "localhost"),
        "port": int(os.getenv("POSTGRES_PORT", "5432")),
        "user": os.getenv("POSTGRES_USER", "postgres"),
        "password": os.getenv("POSTGRES_PASSWORD", ""),
        "dbname": os.getenv("POSTGRES_DB", "postgres"),
    }

    # Check if required environment variables are set
    if not props["password"]:
        pytest.skip("POSTGRES_PASSWORD environment variable not set")

    try:
        conn = psycopg2.connect(**props)
        conn.autocommit = True

        # Test the connection
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1")

        print("Successfully connected to existing PostgreSQL container")
        yield conn, props

    except Exception as e:
        pytest.skip(f"Could not connect to existing PostgreSQL: {e}")
    finally:
        if "conn" in locals():
            conn.close()


@pytest.fixture(scope="session")
def mindsdb_db_name():
    """Generate a unique database name to avoid MindsDB caching issues."""
    return "test_postgres_" + str(os.getpid())


@pytest.fixture(scope="session")
def postgres_datasource(postgres, data_server_cli: "DataServerCliWrapper", mindsdb_db_name):
    """Create a DataSource instance connected to MindsDB."""
    print("Starting mindsdb")
    http_port, mysql_port = data_server_cli.get_http_and_mysql_ports()

    # Set up a datasource to the mindsdb with postgres inside
    DataSource.setup_connection_from_input_json(
        {
            "http": {
                "url": f"http://localhost:{http_port}",
                "user": data_server_cli.get_username(),
                "password": data_server_cli.get_password(),
            },
            "mysql": {
                "host": "localhost",
                "port": mysql_port,
                "user": data_server_cli.get_username(),
                "password": data_server_cli.get_password(),
            },
        }
    )
    ds = DataSource.model_validate(datasource_name=mindsdb_db_name)
    ds.execute_sql("CREATE PROJECT IF NOT EXISTS di_tests")

    initialize_database("postgres", ds)

    yield ds

    try:
        ds.execute_sql("DROP VIEW IF EXISTS di_tests.ORDERS_PAYMENTS_ORDERS")
        ds.execute_sql("DROP VIEW IF EXISTS di_tests.ORDERS_PAYMENTS_PAYMENTS")

        ds.execute_sql("DROP PROJECT IF EXISTS di_tests")
        ds.execute_sql(f"DROP DATABASE IF EXISTS `{mindsdb_db_name}`")
    except Exception:
        pass


@pytest.fixture(autouse=True)
def clean_tables(postgres_datasource):
    """Clean tables before each test to avoid duplicate key conflicts."""
    # This runs before each test that uses postgres_datasource
    tables_to_clean = ["data_models", "document_layouts", "documents"]

    for table in tables_to_clean:
        try:
            postgres_datasource.native_query(f"TRUNCATE TABLE {table} CASCADE")
        except Exception:
            pass


@pytest.fixture(scope="session")
def setup_db(postgres):
    """Sets up tables in the postgres database for models tests."""
    conn, _ = postgres

    # Get SQL schema file path
    sql_dir = Path(__file__).parent.parent / "sema4ai_docint" / "models" / "sql"
    assert sql_dir.exists()
    assert sql_dir.is_dir()
    pg_fixture = sql_dir / "pg_schema.sql"
    assert pg_fixture.exists()
    with open(pg_fixture) as f:
        pg_schema = f.read()

    # Setup the test database with tables and data.
    with conn.cursor() as cursor:
        cursor.execute(pg_schema)

    return conn


@pytest.fixture(scope="session")
def cleanup_db(setup_db):
    """Cleanup the test database after each test (models tests)."""
    yield

    conn = setup_db
    for table in ["data_models", "document_layouts", "documents"]:
        with conn.cursor() as cursor:
            cursor.execute(f"TRUNCATE TABLE {table}")


@pytest.fixture(scope="session")
def openai_api_key():
    """Get OpenAI API key from environment variable."""
    # Load environment variables from .env file
    load_dotenv()
    return os.getenv("OPENAI_API_KEY", "")


@pytest.fixture(scope="session")
def agent_id(agent_server_cli, openai_api_key):
    """Create an agent and return its ID for testing."""

    if not openai_api_key:
        pytest.skip("OPENAI_API_KEY environment variable not set")

    agent_port = agent_server_cli.get_http_port()
    base_url = f"http://localhost:{agent_port}/api/v2"

    # Create agent payload
    agent_payload = {
        "mode": "conversational",
        "name": "test_agent",
        "version": "1.0.0",
        "description": "This is a test agent for integration tests.",
        "runbook": "# Objective\nYou are a helpful assistant.",
        "platform_configs": [{"kind": "openai", "openai_api_key": openai_api_key}],
        "action_packages": [],
        "mcp_servers": [],
        "agent_architecture": {
            "name": "agent_platform.architectures.default",
            "version": "1.0.0",
        },
        "observability_configs": [],
        "question_groups": [],
    }

    agent_id = None
    try:
        # Create the agent
        response = sema4ai_http.post(
            f"{base_url}/agents/",
            json=agent_payload,
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()

        agent_data = response.json()
        agent_id = agent_data.get("agent_id")

        if not agent_id:
            raise ValueError("No agent ID returned from agent creation")

        print(f"Created test agent with ID: {agent_id}")
        yield agent_id

    except Exception as e:
        pytest.fail(f"Failed to create test agent: {e!s}")
    finally:
        # Clean up: delete the agent
        if agent_id:
            try:
                delete_response = sema4ai_http.delete(f"{base_url}/agents/{agent_id}")
                if delete_response.status_code in [
                    200,
                    204,
                ]:  # Both 200 and 204 indicate success
                    print(f"Successfully deleted test agent: {agent_id}")
                else:
                    print(
                        f"Warning: Failed to delete test agent {agent_id}: "
                        f"{delete_response.status_code}"
                    )
            except Exception as e:
                print(f"Warning: Error during agent cleanup: {e!s}")


@pytest.fixture
def thread_id(agent_server_cli, agent_id):
    """Create a thread in the default agent."""

    agent_port = agent_server_cli.get_http_port()
    base_url = f"http://localhost:{agent_port}/api/v2"

    thread_id: str | None = None
    try:
        # Create a thread
        response = sema4ai_http.post(
            f"{base_url}/threads/",
            json={
                "agent_id": agent_id,
                "name": f"DocInt Test Thread {thread_id}",
            },
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()

        thread_data = response.json()
        thread_id = thread_data.get("thread_id")
        yield thread_id

    except Exception as e:
        pytest.fail(f"Failed to create test thread: {e!s}")
    finally:
        # Clean up: delete the thread
        if thread_id:
            delete_response = sema4ai_http.delete(f"{base_url}/threads/{thread_id}")
            delete_response.raise_for_status()


@pytest.fixture(scope="session")
def agent_client(agent_server_cli, agent_id):
    """Create an AgentServerClient instance for testing."""
    from sema4ai_docint.agent_server_client import AgentServerClient

    # Set the environment variable to point to our test agent server
    agent_port = agent_server_cli.get_http_port()
    os.environ["SEMA4AI_AGENTS_SERVICE_URL"] = f"http://localhost:{agent_port}"

    # Set the file management URL to point to the test data directory
    test_data_dir = Path(__file__).parent / "agent_server_client" / "test-data"
    if test_data_dir.exists():
        os.environ["SEMA4AI_FILE_MANAGEMENT_URL"] = f"file://{test_data_dir.absolute()}"

    # Create client with the test agent_id
    client = AgentServerClient(agent_id=agent_id)
    return client


# Extraction-related fixtures
@pytest.fixture(autouse=True)
def reducto_api_key():
    """Fixture to set the REDUCTO_API_KEY environment variable for testing."""
    # Load environment variables from .env file
    load_dotenv()
    return os.getenv("REDUCTO_API_KEY", "")


@pytest.fixture(autouse=True)
def sema4_reducto_apikey():
    """Fixture to set the REDUCTO_API_KEY environment variable for testing."""
    # Load environment variables from .env file
    load_dotenv()
    return os.getenv("SEMA4_REDUCTO_API_KEY", "")


@pytest.fixture(autouse=True)
def sema4_reducto_url():
    """Fixture to set the SEMA4_REDUCTO_URL environment variable for testing."""
    # Load environment variables from .env file
    load_dotenv()
    return os.getenv("SEMA4_REDUCTO_URL", "")


@pytest.fixture
def client(sema4_reducto_apikey: str, sema4_reducto_url: str) -> SyncExtractionClient:
    """Fixture to create a DocExtractionClient instance for testing."""
    if not sema4_reducto_apikey:
        pytest.skip("Skipping test because SEMA4_REDUCTO_API_KEY is not set")

    # Create a client with separate SQLite databases for schemas and documents
    client = SyncExtractionClient(
        sema4_reducto_apikey,
        base_url=sema4_reducto_url,
    )

    return client


# Views-specific test data initialization
SCHEMA_DATA: dict[str, typing.Any] = {}
VIEWS_SAMPLE_DOCUMENT: dict[str, typing.Any] = {}
VIEWS_SAMPLE_SCHEMA: BusinessSchema | None = None

try:
    # Load test data from views directory if it exists
    SCHEMA_DATA = load_schema("orders_payments", "business_schema.json")
    VIEWS_SAMPLE_DOCUMENT = load_document("orders_payments", "business_document.json")
    # Create BusinessSchema from the loaded JSON
    VIEWS_SAMPLE_SCHEMA = BusinessSchema.from_dict(SCHEMA_DATA)
except (FileNotFoundError, ImportError):
    # Fallback if files don't exist or imports fail
    pass
