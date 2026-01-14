"""Integration tests for parameterized verified queries."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from agent_platform.orchestrator.agent_server_client import AgentServerClient
from structlog import get_logger

logger = get_logger(__name__)


@pytest.fixture(scope="module")
def verified_queries_resources_dir() -> Path:
    """Module-scoped resources directory path for verified queries tests."""
    test_file = Path(__file__)
    return test_file.parent / "resources"


@pytest.fixture(scope="module")
def verified_queries_agent_client(
    base_url_agent_server_session,
) -> Iterator[AgentServerClient]:
    """Module-scoped agent client for verified queries tests."""
    with AgentServerClient(base_url_agent_server_session) as agent_client:
        yield agent_client


@pytest.fixture(scope="module")
def verified_queries_data_connection(verified_queries_agent_client, verified_queries_resources_dir) -> dict:
    """Module-scoped data connection for verified queries tests."""
    db_file = verified_queries_resources_dir / "data_frames" / "combined_data.sqlite"
    data_connection = verified_queries_agent_client.create_data_connection(
        name="test-connection-verified-queries",
        description="Test connection for verified queries integration",
        engine="sqlite",
        configuration={"db_file": str(db_file)},
    )
    return data_connection


@pytest.fixture(scope="module")
def verified_queries_semantic_model(
    verified_queries_agent_client, verified_queries_data_connection
) -> tuple[str, dict]:
    """Module-scoped semantic data model for verified queries tests."""
    semantic_model = {
        "name": "test_verified_queries_integration_model",
        "description": "Test model for verified queries integration",
        "tables": [
            {
                "name": "ai_systems",
                "base_table": {
                    "data_connection_id": verified_queries_data_connection["id"],
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
    created_model = verified_queries_agent_client.create_semantic_data_model(dict(semantic_model=semantic_model))
    return created_model["semantic_data_model_id"], semantic_model


@pytest.mark.integration
def test_save_and_retrieve_parameterized_verified_query(
    base_url_agent_server_session,
    verified_queries_agent_client,
    verified_queries_semantic_model,
):
    """Test saving and retrieving parameterized verified queries."""
    from urllib.parse import urljoin

    import requests

    semantic_data_model_id, semantic_model = verified_queries_semantic_model

    agent_id = verified_queries_agent_client.create_agent_and_return_agent_id(
        action_packages=[],
        platform_configs=[
            {
                "kind": "openai",
                "openai_api_key": "unused",
                "models": {"openai": ["gpt-5-low"]},
            },
        ],
    )
    thread_id = verified_queries_agent_client.create_thread_and_return_thread_id(agent_id)

    verify_url = urljoin(
        base_url_agent_server_session,
        "/api/v2/semantic-data-models/verify-verified-query",
    )
    save_url = urljoin(
        base_url_agent_server_session,
        f"/api/v2/threads/{thread_id}/data-frames/save-as-validated-query",
    )

    # Create and validate query
    valid_query = {
        "semantic_data_model": semantic_model,
        "verified_query": {
            "name": "ai systems by domain and year",
            "nlq": "Get AI systems filtered by domain and year",
            "sql": "SELECT * FROM ai_systems WHERE Domain = :domain AND year = :year",
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

    # Save the query
    payload = {
        "verified_query": validated_query,
        "semantic_data_model_id": semantic_data_model_id,
    }
    response = requests.post(save_url, json=payload)
    assert response.status_code == requests.codes.ok, (
        f"Error saving parameterized query: {response.status_code} {response.text}"
    )
    logger.info("[OK] Parameterized verified query saved successfully")

    # Retrieve and verify
    retrieved_model = verified_queries_agent_client.get_semantic_data_model(semantic_data_model_id)
    assert "verified_queries" in retrieved_model
    assert len(retrieved_model["verified_queries"]) == 1

    saved_query = retrieved_model["verified_queries"][0]
    assert saved_query["name"] == "ai systems by domain and year"
    assert "parameters" in saved_query
    assert len(saved_query["parameters"]) == 2

    param_names = {p["name"] for p in saved_query["parameters"]}
    assert param_names == {"domain", "year"}

    domain_param = next(p for p in saved_query["parameters"] if p["name"] == "domain")
    assert domain_param["data_type"] == "string"
    assert domain_param["example_value"] == "Language"
    assert domain_param["description"] == "Domain to filter by"

    year_param = next(p for p in saved_query["parameters"] if p["name"] == "year")
    assert year_param["data_type"] == "integer"
    assert year_param["example_value"] == 2022
    assert year_param["description"] == "Year to filter by"

    logger.info("[OK] Parameterized verified query retrieved correctly")


@pytest.mark.integration
def test_export_import_preserves_parameters(
    base_url_agent_server_session,
    verified_queries_agent_client,
    verified_queries_semantic_model,
):
    """Test that verified query parameters are preserved during SDM export/import."""
    from urllib.parse import urljoin

    import requests
    import yaml

    semantic_data_model_id, semantic_model = verified_queries_semantic_model

    agent_id = verified_queries_agent_client.create_agent_and_return_agent_id(
        action_packages=[],
        platform_configs=[
            {
                "kind": "openai",
                "openai_api_key": "unused",
                "models": {"openai": ["gpt-5-low"]},
            },
        ],
    )
    thread_id = verified_queries_agent_client.create_thread_and_return_thread_id(agent_id)

    # Save a parameterized query
    verify_url = urljoin(
        base_url_agent_server_session,
        "/api/v2/semantic-data-models/verify-verified-query",
    )
    save_url = urljoin(
        base_url_agent_server_session,
        f"/api/v2/threads/{thread_id}/data-frames/save-as-validated-query",
    )

    valid_query = {
        "semantic_data_model": semantic_model,
        "verified_query": {
            "name": "ai systems by domain and year",
            "nlq": "Get AI systems filtered by domain and year",
            "sql": "SELECT * FROM ai_systems WHERE Domain = :domain AND year = :year",
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
        base_url_agent_server_session,
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
    verified_queries_agent_client.set_agent_semantic_data_models(agent_id, [])

    # Import with a different name to avoid conflict with module-scoped fixture
    import_url = urljoin(
        base_url_agent_server_session,
        "/api/v2/semantic-data-models/import",
    )

    # Change the SDM name to avoid conflict with the module-scoped fixture
    exported_sdm["name"] = "test_verified_queries_integration_model_imported"
    exported_sdm["tables"][0]["base_table"]["data_connection_name"] = "test-connection-verified-queries"
    if "data_connection_id" in exported_sdm["tables"][0]["base_table"]:
        del exported_sdm["tables"][0]["base_table"]["data_connection_id"]

    import_payload = {
        "semantic_model": exported_sdm,
    }

    import_response = requests.post(import_url, json=import_payload)
    assert import_response.status_code == requests.codes.ok

    import_data = import_response.json()
    imported_sdm_id = import_data["semantic_data_model_id"]

    # Verify imported SDM
    get_url = urljoin(
        base_url_agent_server_session,
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
