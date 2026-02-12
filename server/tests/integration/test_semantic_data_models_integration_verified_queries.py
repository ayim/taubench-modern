"""Integration tests for parameterized verified queries.

Configuration Architecture
--------------------------

These tests use dedicated server fixtures with different configurations:

1. `agent_server_with_enhancement`: Server with ENHANCE_VERIFIED_QUERIES_WITH_LLM=true
   → Used for testing LLM enhancement feature

2. `agent_server_without_enhancement`: Server with ENHANCE_VERIFIED_QUERIES_WITH_LLM=false
   → Used for testing basic verified query functionality

Each fixture starts its own agent server instance with the appropriate configuration,
allowing tests to explicitly control enhancement behavior without relying on external
environment variables.
"""

import os
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from agent_platform.orchestrator.agent_server_client import AgentServerClient
from structlog import get_logger

from agent_platform.core.semantic_data_model.types import SemanticDataModel
from server.tests.integration.integration_fixtures import start_agent_server

logger = get_logger(__name__)


@pytest.fixture
def verified_queries_resources_dir() -> Path:
    """Resources directory path for verified queries tests."""
    test_file = Path(__file__)
    return test_file.parent / "resources"


# ============================================================================
# Helper Functions
# ============================================================================


def create_semantic_data_model(
    agent_client: AgentServerClient,
    resources_dir: Path,
    connection_name: str,
    model_name: str,
) -> dict:
    """Helper to create a data connection and build semantic data model definition.

    Args:
        agent_client: The AgentServerClient instance
        resources_dir: Path to test resources
        connection_name: Name for the data connection
        model_name: Name for the semantic data model

    Returns:
        Dictionary with semantic model definition that can be used in tests
    """
    db_file = resources_dir / "data_frames" / "combined_data.sqlite"
    data_connection = agent_client.create_data_connection(
        name=connection_name,
        description=f"Test connection for {model_name}",
        engine="sqlite",
        configuration={"db_file": str(db_file)},
    )

    # Build semantic model definition
    semantic_model = {
        "name": model_name,
        "description": f"Test model for {model_name}",
        "tables": [
            {
                "name": "hardware_and_energy_cost_to_train_notable_ai_systems",
                "base_table": {
                    "data_connection_id": data_connection["id"],
                    "table": "hardware_and_energy_cost_to_train_notable_ai_systems",
                },
                "description": "AI systems training data",
                "dimensions": [
                    {
                        "name": "id",
                        "expr": "id",
                        "data_type": "INTEGER",
                        "description": "Record ID",
                    },
                    {
                        "name": "Entity",
                        "expr": "Entity",
                        "data_type": "TEXT",
                        "description": "AI system name",
                    },
                    {
                        "name": "year",
                        "expr": "year",
                        "data_type": "INTEGER",
                        "description": "Year",
                    },
                    {
                        "name": "Domain",
                        "expr": "Domain",
                        "data_type": "TEXT",
                        "description": "Domain (Language, Games, Vision, etc.)",
                    },
                ],
            }
        ],
    }

    return semantic_model


# ============================================================================
# Fixtures for Server WITHOUT Enhancement
# ============================================================================


@pytest.fixture
def agent_server_without_enhancement(tmpdir, logs_dir) -> Iterator[str]:
    """Start agent server with verified query enhancement DISABLED."""
    env_vars = {"ENHANCE_VERIFIED_QUERIES_WITH_LLM": "false"}
    with start_agent_server(tmpdir, logs_dir, env=env_vars) as url:
        yield url


@pytest.fixture
def agent_client_without_enhancement(agent_server_without_enhancement) -> Iterator[AgentServerClient]:
    """Agent client connected to server with enhancement DISABLED."""
    with AgentServerClient(agent_server_without_enhancement) as client:
        yield client


@pytest.fixture
def sdm_without_enhancement(
    agent_client_without_enhancement, verified_queries_resources_dir
) -> tuple[str, SemanticDataModel]:
    """Semantic data model on server without enhancement.

    Returns:
        Tuple of (semantic_data_model_id, SemanticDataModel Pydantic model)
    """
    # Use unique name to avoid conflicts with other test runs
    unique_suffix = str(uuid4())[:8]
    semantic_model_dict = create_semantic_data_model(
        agent_client_without_enhancement,
        verified_queries_resources_dir,
        connection_name=f"test-connection-no-enhancement-{unique_suffix}",
        model_name=f"test_verified_queries_integration_model_no_enhancement_{unique_suffix}",
    )

    # Create agent and thread to create the semantic data model
    agent_id = agent_client_without_enhancement.create_agent_and_return_agent_id(
        action_packages=[],
        platform_configs=[
            {
                "kind": "openai",
                "openai_api_key": "unused",
                "models": {"openai": ["gpt-5-low"]},
            }
        ],
    )
    thread_id = agent_client_without_enhancement.create_thread_and_return_thread_id(agent_id)

    # Create the semantic data model
    created_model = agent_client_without_enhancement.create_semantic_data_model(
        dict(semantic_model=semantic_model_dict, thread_id=thread_id)
    )

    semantic_data_model_id = created_model["semantic_data_model_id"]

    # Fetch and return as Pydantic model
    semantic_model = agent_client_without_enhancement.get_semantic_data_model(semantic_data_model_id)

    return semantic_data_model_id, semantic_model


# ============================================================================
# Fixtures for Server WITH Enhancement
# ============================================================================


@pytest.fixture
def agent_server_with_enhancement(tmpdir, logs_dir) -> Iterator[str]:
    """Start agent server with verified query enhancement ENABLED."""
    env_vars = {"ENHANCE_VERIFIED_QUERIES_WITH_LLM": "true"}
    with start_agent_server(tmpdir, logs_dir, env=env_vars) as url:
        yield url


@pytest.fixture
def agent_client_with_enhancement(agent_server_with_enhancement) -> Iterator[AgentServerClient]:
    """Agent client connected to server with enhancement ENABLED."""
    with AgentServerClient(agent_server_with_enhancement) as client:
        yield client


@pytest.fixture
def sdm_with_enhancement(
    agent_client_with_enhancement, verified_queries_resources_dir
) -> tuple[str, SemanticDataModel]:
    """Semantic data model on server with enhancement.

    Returns:
        Tuple of (semantic_data_model_id, SemanticDataModel Pydantic model)
    """
    # Use unique name to avoid conflicts with other test runs
    unique_suffix = str(uuid4())[:8]
    semantic_model_dict = create_semantic_data_model(
        agent_client_with_enhancement,
        verified_queries_resources_dir,
        connection_name=f"test-connection-with-enhancement-{unique_suffix}",
        model_name=f"test_verified_queries_integration_model_with_enhancement_{unique_suffix}",
    )

    # Create agent and thread to create the semantic data model
    agent_id = agent_client_with_enhancement.create_agent_and_return_agent_id(
        action_packages=[],
        platform_configs=[
            {
                "kind": "openai",
                "openai_api_key": "unused",
                "models": {"openai": ["gpt-5-low"]},
            }
        ],
    )
    thread_id = agent_client_with_enhancement.create_thread_and_return_thread_id(agent_id)

    # Create the semantic data model
    created_model = agent_client_with_enhancement.create_semantic_data_model(
        dict(semantic_model=semantic_model_dict, thread_id=thread_id)
    )

    semantic_data_model_id = created_model["semantic_data_model_id"]

    # Fetch and return as Pydantic model
    semantic_model = agent_client_with_enhancement.get_semantic_data_model(semantic_data_model_id)

    return semantic_data_model_id, semantic_model


# Helper functions for creating agents
def create_agent_with_llm_config(
    agent_client: AgentServerClient,
    semantic_data_model_id: str,
    openai_api_key: str,
) -> tuple[str, str]:
    """Helper to create an agent with specific LLM configuration.

    Args:
        agent_client: The AgentServerClient instance
        semantic_data_model_id: ID of the semantic data model to attach
        openai_api_key: OpenAI API key (can be "unused" for testing failures)

    Returns:
        Tuple of (agent_id, thread_id)
    """
    agent_id = agent_client.create_agent_and_return_agent_id(
        action_packages=[],
        platform_configs=[
            {
                "kind": "openai",
                "openai_api_key": openai_api_key,
                "models": {"openai": ["gpt-4o"]},
            },
        ],
    )
    thread_id = agent_client.create_thread_and_return_thread_id(agent_id)
    agent_client.set_agent_semantic_data_models(agent_id, [semantic_data_model_id])

    return agent_id, thread_id


@pytest.mark.integration
def test_save_and_retrieve_parameterized_verified_query(
    agent_server_without_enhancement,
    agent_client_without_enhancement,
    sdm_without_enhancement,
):
    """Test saving and retrieving parameterized verified queries.

    Uses server WITHOUT enhancement to test basic verified query functionality.
    """
    from urllib.parse import urljoin

    import requests

    semantic_data_model_id, semantic_model = sdm_without_enhancement

    # Create agent
    agent_id, thread_id = create_agent_with_llm_config(
        agent_client_without_enhancement,
        semantic_data_model_id,
        openai_api_key="unused",  # Not needed for this test
    )

    verify_url = urljoin(
        agent_server_without_enhancement,
        "/api/v2/semantic-data-models/verify-verified-query",
    )
    save_url = urljoin(
        agent_server_without_enhancement,
        f"/api/v2/threads/{thread_id}/data-frames/save-as-validated-query",
    )

    # Create and validate query
    valid_query = {
        "semantic_data_model": semantic_model.model_dump(mode="json"),
        "verified_query": {
            "name": "ai systems by domain and year",
            "nlq": "Get AI systems filtered by domain and year",
            "sql": (
                "SELECT * FROM hardware_and_energy_cost_to_train_notable_ai_systems "
                "WHERE Domain = :domain AND year = :year"
            ),
            "parameters": [
                {
                    "name": "domain",
                    "data_type": "string",
                    "example_value": "Language",
                    "description": "Domain to filter by",
                },
                {
                    "name": "year",
                    "data_type": "integer",
                    "example_value": 2022,
                    "description": "Year to filter by",
                },
            ],
        },
        "accept_initial_name": "ai systems by domain and year",
    }

    response = requests.post(verify_url, json=valid_query)
    assert response.status_code == requests.codes.ok, f"Error verifying query: {response.status_code} {response.text}"
    validated_query_dict = response.json()["verified_query"]

    # Verify the query dict can be converted to Pydantic model
    from agent_platform.core.semantic_data_model.types import VerifiedQuery

    validated_query = VerifiedQuery.model_validate(validated_query_dict)

    # Verify the query structure before saving
    assert validated_query.name == "ai systems by domain and year"
    assert validated_query.nlq == "Get AI systems filtered by domain and year"
    assert validated_query.sql == (
        "SELECT * FROM hardware_and_energy_cost_to_train_notable_ai_systems WHERE Domain = :domain AND year = :year"
    )
    assert validated_query.parameters is not None
    assert len(validated_query.parameters) == 2

    # Save the query (convert back to dict for API)
    payload = {
        "verified_query": validated_query_dict,
        "semantic_data_model_id": semantic_data_model_id,
    }
    response = requests.post(save_url, json=payload)
    assert response.status_code == requests.codes.ok, (
        f"Error saving parameterized query: {response.status_code} {response.text}"
    )

    save_response_data = response.json()
    assert "message" in save_response_data
    assert "ai systems by domain and year" in save_response_data["message"]

    logger.info("[OK] Parameterized verified query saved successfully")

    # Retrieve and verify
    # get_semantic_data_model returns a SemanticDataModel Pydantic object, use attribute access
    retrieved_model = agent_client_without_enhancement.get_semantic_data_model(semantic_data_model_id)
    assert retrieved_model.verified_queries is not None
    assert len(retrieved_model.verified_queries) == 1

    saved_query = retrieved_model.verified_queries[0]
    assert saved_query.name == "ai systems by domain and year"
    assert saved_query.parameters is not None
    assert len(saved_query.parameters) == 2

    param_names = {p.name for p in saved_query.parameters}
    assert param_names == {"domain", "year"}

    domain_param = next(p for p in saved_query.parameters if p.name == "domain")
    assert domain_param.data_type == "string"
    assert domain_param.example_value == "Language"
    assert domain_param.description == "Domain to filter by"

    year_param = next(p for p in saved_query.parameters if p.name == "year")
    assert year_param.data_type == "integer"
    assert year_param.example_value == 2022
    assert year_param.description == "Year to filter by"

    # Verify metadata fields
    assert hasattr(saved_query, "verified_at")
    assert saved_query.verified_at is not None
    assert hasattr(saved_query, "verified_by")
    assert saved_query.verified_by is not None

    logger.info("[OK] Parameterized verified query retrieved correctly with all metadata preserved")


@pytest.mark.integration
def test_export_import_preserves_parameters(
    agent_server_without_enhancement,
    agent_client_without_enhancement,
    sdm_without_enhancement,
):
    """Test that verified query parameters are preserved during SDM export/import.

    Uses server WITHOUT enhancement to test basic export/import functionality.
    """
    from urllib.parse import urljoin

    import requests
    import yaml

    semantic_data_model_id, semantic_model = sdm_without_enhancement

    # Create agent
    agent_id, thread_id = create_agent_with_llm_config(
        agent_client_without_enhancement,
        semantic_data_model_id,
        openai_api_key="unused",
    )

    # Save a parameterized query
    verify_url = urljoin(
        agent_server_without_enhancement,
        "/api/v2/semantic-data-models/verify-verified-query",
    )
    save_url = urljoin(
        agent_server_without_enhancement,
        f"/api/v2/threads/{thread_id}/data-frames/save-as-validated-query",
    )

    valid_query = {
        "semantic_data_model": semantic_model.model_dump(mode="json"),
        "verified_query": {
            "name": "ai systems by domain and year",
            "nlq": "Get AI systems filtered by domain and year",
            "sql": (
                "SELECT * FROM hardware_and_energy_cost_to_train_notable_ai_systems "
                "WHERE Domain = :domain AND year = :year"
            ),
            "parameters": [
                {
                    "name": "domain",
                    "data_type": "string",
                    "example_value": "Language",
                    "description": "Domain to filter by",
                },
                {
                    "name": "year",
                    "data_type": "integer",
                    "example_value": 2022,
                    "description": "Year to filter by",
                },
            ],
        },
        "accept_initial_name": "ai systems by domain and year",
    }

    response = requests.post(verify_url, json=valid_query)
    validated_query = response.json()["verified_query"]
    payload = {
        "verified_query": validated_query,
        "semantic_data_model_id": semantic_data_model_id,
    }
    requests.post(save_url, json=payload)

    # Export
    export_url = urljoin(
        agent_server_without_enhancement,
        f"/api/v2/semantic-data-models/{semantic_data_model_id}/export",
    )
    export_response = requests.get(export_url)
    assert export_response.status_code == requests.codes.ok

    export_data = export_response.json()
    yaml_content = export_data["content"]

    exported_sdm = yaml.safe_load(yaml_content)
    assert "verified_queries" in exported_sdm
    assert len(exported_sdm["verified_queries"]) >= 1

    # Find the specific parameterized query we saved
    exported_param_query = next(
        (q for q in exported_sdm["verified_queries"] if q["name"] == "ai systems by domain and year"),
        None,
    )
    assert exported_param_query is not None, "Query 'ai systems by domain and year' not found in export"
    assert "parameters" in exported_param_query
    assert len(exported_param_query["parameters"]) == 2
    assert exported_param_query["parameters"][0]["name"] == "domain"
    assert exported_param_query["parameters"][0]["data_type"] == "string"
    assert exported_param_query["parameters"][0]["example_value"] == "Language"
    assert exported_param_query["parameters"][1]["name"] == "year"
    assert exported_param_query["parameters"][1]["data_type"] == "integer"
    assert exported_param_query["parameters"][1]["example_value"] == 2022

    # Remove SDM from agent and change the name for re-import to avoid conflict
    agent_client_without_enhancement.set_agent_semantic_data_models(agent_id, [])

    # Import with a different name to avoid conflict
    import_url = urljoin(
        agent_server_without_enhancement,
        "/api/v2/semantic-data-models/import",
    )

    # Change the SDM name to avoid conflict
    # Use unique name for the imported model as well
    unique_suffix_import = str(uuid4())[:8]
    exported_sdm["name"] = f"test_verified_queries_integration_model_imported_{unique_suffix_import}"
    # The exported SDM should already have the correct data_connection_name from export
    # We just need to ensure data_connection_id is removed so it can be resolved during import
    if "data_connection_id" in exported_sdm["tables"][0]["base_table"]:
        del exported_sdm["tables"][0]["base_table"]["data_connection_id"]

    import_payload = {
        "semantic_model": exported_sdm,
        "thread_id": thread_id,
    }

    import_response = requests.post(import_url, json=import_payload)
    assert import_response.status_code == requests.codes.ok

    import_data = import_response.json()
    imported_sdm_id = import_data["semantic_data_model_id"]

    # Verify imported SDM
    get_url = urljoin(
        agent_server_without_enhancement,
        f"/api/v2/semantic-data-models/{imported_sdm_id}",
    )
    get_response = requests.get(get_url)
    assert get_response.status_code == requests.codes.ok

    imported_sdm = get_response.json()
    assert "verified_queries" in imported_sdm
    assert len(imported_sdm["verified_queries"]) >= 1

    # Find the specific parameterized query in the imported SDM
    imported_param_query = next(
        (q for q in imported_sdm["verified_queries"] if q["name"] == "ai systems by domain and year"),
        None,
    )
    assert imported_param_query is not None, "Query 'ai systems by domain and year' not found in imported SDM"
    assert "parameters" in imported_param_query
    assert len(imported_param_query["parameters"]) == 2
    assert imported_param_query["parameters"][0]["name"] == "domain"
    assert imported_param_query["parameters"][0]["data_type"] == "string"
    assert imported_param_query["parameters"][0]["example_value"] == "Language"
    assert imported_param_query["parameters"][1]["name"] == "year"
    assert imported_param_query["parameters"][1]["data_type"] == "integer"
    assert imported_param_query["parameters"][1]["example_value"] == 2022

    logger.info("[OK] Verified query parameters are preserved after export/import")


@pytest.mark.integration
def test_verified_query_metadata_enhancement_with_llm(
    agent_server_with_enhancement,
    agent_client_with_enhancement,
    sdm_with_enhancement,
):
    """Test that verified query metadata is enhanced with LLM when enabled.

    This test uses a server fixture with ENHANCE_VERIFIED_QUERIES_WITH_LLM=true
    and creates an agent with valid OpenAI credentials.

    The server will attempt to enhance verified queries, and with valid credentials,
    the enhancement should succeed.

    Note: Set OPENAI_API_KEY environment variable for this test to actually perform
    enhancement. Without it, the test will use "unused" as the key and verify that
    enhancement was attempted (even if it fails due to invalid credentials).
    """
    from urllib.parse import urljoin

    import requests

    semantic_data_model_id, semantic_model = sdm_with_enhancement

    # Create agent with OpenAI credentials from env (or "unused" if not set)
    agent_id, thread_id = create_agent_with_llm_config(
        agent_client_with_enhancement,
        semantic_data_model_id,
        openai_api_key=os.environ.get("OPENAI_API_KEY", "unused"),
    )

    # Create a data frame using SQL from the semantic model
    create_url = urljoin(
        agent_server_with_enhancement,
        f"/api/v2/threads/{thread_id}/data-frames/from-computation",
    )

    sql_query = (
        "SELECT * FROM hardware_and_energy_cost_to_train_notable_ai_systems WHERE Domain = 'Language' AND year > 2020"
    )
    data_frame_payload = {
        "sql_query": sql_query,
        "new_data_frame_name": "test_llm_enhanced_query",
        "description": "AI systems in language domain",
        "semantic_data_model_name": semantic_model.name,
    }

    response = requests.post(create_url, json=data_frame_payload)
    assert response.status_code == requests.codes.ok, (
        f"Error creating data frame: {response.status_code} {response.text}"
    )

    data_frame_name = response.json()["name"]

    # Now get it as a validated query (this triggers enhancement in as-validated-query endpoint)
    as_validated_query_url = urljoin(
        agent_server_with_enhancement,
        f"/api/v2/threads/{thread_id}/data-frames/as-validated-query",
    )

    as_validated_payload = {
        "data_frame_name": data_frame_name,
    }

    validated_response = requests.post(as_validated_query_url, json=as_validated_payload)
    assert validated_response.status_code == requests.codes.ok, (
        f"Error getting as validated query: {validated_response.status_code} {validated_response.text}"
    )

    validated_data = validated_response.json()
    enhanced_query_dict = validated_data["verified_query"]

    # Verify the query dict can be converted to Pydantic model
    from agent_platform.core.semantic_data_model.types import VerifiedQuery

    enhanced_query = VerifiedQuery.model_validate(enhanced_query_dict)

    # Log the full enhanced query structure for inspection
    logger.info(
        "Enhanced query details",
        name=enhanced_query.name,
        nlq=enhanced_query.nlq,
        sql=enhanced_query.sql,
        parameters=[p.name for p in enhanced_query.parameters] if enhanced_query.parameters else [],
    )

    # The data frame name is converted to title case for the query name
    # E.g., "test_llm_enhanced_query" becomes "Test Llm Enhanced Query"
    default_name = data_frame_name.replace("_", " ").title()

    # Verify that the query was actually enhanced by LLM
    # 1. Query name should be different from the default title-cased name (LLM should enhance it)
    assert enhanced_query.name != default_name, (
        f"Query name should be enhanced by LLM and different from default '{default_name}'"
    )
    assert len(enhanced_query.name) > 0
    # Should use letters, numbers, and spaces only (validation requirement)
    assert all(c.isalnum() or c.isspace() for c in enhanced_query.name)

    # 2. NLQ should be different from the data frame description (LLM should enhance it)
    assert enhanced_query.nlq != data_frame_payload["description"], (
        "NLQ should be enhanced by LLM and different from data frame description"
    )
    assert len(enhanced_query.nlq) >= 10
    # Should be a statement, not end with question mark
    assert not enhanced_query.nlq.strip().endswith("?")

    # 3. Parameters should have meaningful descriptions (not default placeholders)
    if enhanced_query.parameters:
        for param in enhanced_query.parameters:
            assert param.description != "Please provide description for this parameter", (
                f"Parameter '{param.name}' should have enhanced description, not default placeholder"
            )
            assert len(param.description) >= 10

    # 4. SQL structure should be preserved and parameterized correctly
    # Original: SELECT * FROM hardware_and_energy_cost_to_train_notable_ai_systems
    #           WHERE Domain = 'Language' AND year > 2020
    # Expected (normalized): SELECT * FROM hardware_and_energy_cost_to_train_notable_ai_systems
    #                        WHERE Domain = :domain AND year > :year
    # Note: sqlglot uses pretty=True which adds newlines, so we normalize for comparison

    def normalize_sql(sql: str) -> str:
        """Normalize SQL by collapsing whitespace for comparison."""
        return " ".join(sql.split())

    normalized_sql = normalize_sql(enhanced_query.sql)
    expected_sql_normalized = (
        "SELECT * FROM hardware_and_energy_cost_to_train_notable_ai_systems WHERE Domain = :domain AND year > :year"
    )

    assert normalized_sql == expected_sql_normalized, (
        f"SQL should be parameterized correctly.\n"
        f"Expected (normalized): {expected_sql_normalized}\n"
        f"Got (normalized): {normalized_sql}\n"
        f"Got (raw): {enhanced_query.sql}"
    )

    # 5. Verify parameters were extracted correctly
    assert enhanced_query.parameters, "Should have extracted parameters"
    assert len(enhanced_query.parameters) == 2, "Should have exactly two parameters (domain and year)"

    # Find the parameters by name
    params_by_name = {p.name: p for p in enhanced_query.parameters}

    # Verify domain parameter
    assert "domain" in params_by_name, "Should have 'domain' parameter"
    domain_param = params_by_name["domain"]
    assert domain_param.data_type == "string", f"Domain type should be 'string', got: {domain_param.data_type}"
    assert domain_param.example_value == "Language", (
        f"Domain example should be 'Language', got: {domain_param.example_value}"
    )
    assert len(domain_param.description) >= 10, "Domain parameter should have meaningful description"

    # Verify year parameter
    assert "year" in params_by_name, "Should have 'year' parameter"
    year_param = params_by_name["year"]
    assert year_param.data_type == "integer", f"Year type should be 'integer', got: {year_param.data_type}"
    assert year_param.example_value == 2020, f"Year example should be 2020, got: {year_param.example_value}"
    assert len(year_param.description) >= 10, "Year parameter should have meaningful description"

    # 6. Verify metadata fields exist
    assert enhanced_query.verified_at
    assert enhanced_query.verified_by

    logger.info(
        "[OK] Verified query metadata enhanced with LLM",
        enhanced_name=enhanced_query.name,
        enhanced_nlq=enhanced_query.nlq,
        sql=enhanced_query.sql,
        parameters=[p.name for p in enhanced_query.parameters],
    )


@pytest.mark.integration
def test_verified_query_enhancement_fallback_on_llm_failure(
    agent_server_with_enhancement,
    agent_client_with_enhancement,
    sdm_with_enhancement,
):
    """Test that enhancement fails gracefully when LLM enhancement is enabled but fails.

    This test uses a server with ENHANCE_VERIFIED_QUERIES_WITH_LLM=true but provides
    an invalid API key to force LLM failure and verify fallback behavior.

    The server attempts enhancement, but since the API key is invalid, it should fall
    back to default behavior gracefully.
    """
    from urllib.parse import urljoin

    import requests

    semantic_data_model_id, semantic_model = sdm_with_enhancement

    # Create agent with INVALID API key to force LLM enhancement failure
    agent_id, thread_id = create_agent_with_llm_config(
        agent_client_with_enhancement,
        semantic_data_model_id,
        openai_api_key="invalid_key_for_testing",
    )

    # Create a data frame using SQL from the semantic model
    create_url = urljoin(
        agent_server_with_enhancement,
        f"/api/v2/threads/{thread_id}/data-frames/from-computation",
    )

    sql_query = "SELECT * FROM hardware_and_energy_cost_to_train_notable_ai_systems WHERE Domain = 'Language'"
    data_frame_payload = {
        "sql_query": sql_query,
        "new_data_frame_name": "test_fallback_query",
        "description": "Test fallback behavior",
        "semantic_data_model_name": semantic_model.name,
    }

    response = requests.post(create_url, json=data_frame_payload)
    assert response.status_code == requests.codes.ok

    data_frame_name = response.json()["name"]

    # Get as validated query - should succeed despite LLM failure
    as_validated_query_url = urljoin(
        agent_server_with_enhancement,
        f"/api/v2/threads/{thread_id}/data-frames/as-validated-query",
    )

    as_validated_payload = {
        "data_frame_name": data_frame_name,
    }

    validated_response = requests.post(as_validated_query_url, json=as_validated_payload)
    # Should still succeed - enhancement failure should not break the main flow
    assert validated_response.status_code == requests.codes.ok, (
        f"Endpoint should succeed even with LLM failure: {validated_response.status_code} {validated_response.text}"
    )

    validated_data = validated_response.json()
    fallback_query_dict = validated_data["verified_query"]

    # Verify the query dict can be converted to Pydantic model
    from agent_platform.core.semantic_data_model.types import VerifiedQuery

    fallback_query = VerifiedQuery.model_validate(fallback_query_dict)

    # Log the full fallback query structure for inspection
    logger.info(
        "Fallback query details",
        name=fallback_query.name,
        nlq=fallback_query.nlq,
        sql=fallback_query.sql,
        parameters=[p.name for p in fallback_query.parameters] if fallback_query.parameters else [],
    )

    # The data frame name is converted to title case for the query name
    # E.g., "test_fallback_query" becomes "Test Fallback Query"
    expected_fallback_name = data_frame_name.replace("_", " ").title()

    # Should have the original metadata (not enhanced, since LLM failed)
    # This verifies the fail-safe fallback mechanism works correctly
    assert fallback_query.name == expected_fallback_name, (
        f"Query name should be title-cased data frame name '{expected_fallback_name}' when LLM fails"
    )
    assert fallback_query.nlq == data_frame_payload["description"], (
        "NLQ should remain as data frame description when LLM fails"
    )

    # Verify the SQL has been parameterized (constant 'Language' extracted as :domain parameter)
    # Note: sqlglot uses pretty=True which adds newlines, so we normalize for comparison

    def normalize_sql(sql: str) -> str:
        """Normalize SQL by collapsing whitespace for comparison."""
        return " ".join(sql.split())

    normalized_sql = normalize_sql(fallback_query.sql)
    expected_sql_normalized = (
        "SELECT * FROM hardware_and_energy_cost_to_train_notable_ai_systems WHERE Domain = :domain"
    )

    assert normalized_sql == expected_sql_normalized, (
        f"SQL should be parameterized with :domain parameter.\n"
        f"Expected (normalized): {expected_sql_normalized}\n"
        f"Got (normalized): {normalized_sql}\n"
        f"Got (raw): {fallback_query.sql}"
    )

    # Verify the domain parameter was extracted
    assert fallback_query.parameters, "Should have extracted 'domain' parameter"
    assert len(fallback_query.parameters) == 1, "Should have exactly one parameter"

    domain_param = fallback_query.parameters[0]
    assert domain_param.name == "domain", f"Parameter name should be 'domain', got: {domain_param.name}"
    assert domain_param.data_type == "string", f"Parameter type should be 'string', got: {domain_param.data_type}"
    assert domain_param.example_value == "Language", (
        f"Example value should be 'Language', got: {domain_param.example_value}"
    )
    assert domain_param.description
    assert len(domain_param.description) > 0

    logger.info("[OK] Verified query enhancement falls back gracefully on LLM failure")
