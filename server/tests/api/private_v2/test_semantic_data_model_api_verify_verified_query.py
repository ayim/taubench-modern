"""API tests for verified query validation endpoints."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from agent_platform.orchestrator.agent_server_client import AgentServerClient


@pytest.fixture(scope="module")
def api_test_resources_dir() -> Path:
    """Module-scoped resources directory path for API tests."""
    # Get the resources_dir path (go up from tests/api/private_v2 to tests/integration/resources)
    test_file = Path(__file__)
    return test_file.parent.parent.parent / "integration" / "resources"


@pytest.fixture(scope="module")
def api_test_agent_client(
    base_url_agent_server_session,
) -> Iterator[AgentServerClient]:
    """Module-scoped agent client for API tests."""
    with AgentServerClient(base_url_agent_server_session) as agent_client:
        yield agent_client


@pytest.fixture(scope="module")
def api_test_data_connection(api_test_agent_client, api_test_resources_dir) -> dict:
    """Module-scoped data connection for API tests."""
    db_file = api_test_resources_dir / "data_frames" / "combined_data.sqlite"
    data_connection = api_test_agent_client.create_data_connection(
        name="test-connection-api-params",
        description="Test connection for API parameter validation",
        engine="sqlite",
        configuration={"db_file": str(db_file)},
    )
    return data_connection


@pytest.fixture(scope="module")
def api_test_semantic_model(api_test_agent_client, api_test_data_connection) -> tuple[str, dict]:
    """Module-scoped semantic data model for API tests."""
    semantic_model = {
        "name": "test_api_parameterized_query_model",
        "description": "Test model for API parameter validation",
        "tables": [
            {
                "name": "ai_systems",
                "base_table": {
                    "data_connection_id": api_test_data_connection["id"],
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
    created_model = api_test_agent_client.create_semantic_data_model(dict(semantic_model=semantic_model))
    return created_model["semantic_data_model_id"], semantic_model


def test_verify_parameterized_query_validation(
    base_url_agent_server_session,
    api_test_agent_client,
    api_test_semantic_model,
):
    """Test that valid parameterized queries are validated correctly."""
    from urllib.parse import urljoin

    import requests

    _, semantic_model = api_test_semantic_model

    verify_url = urljoin(
        base_url_agent_server_session,
        "/api/v2/semantic-data-models/verify-verified-query",
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
    assert response.status_code == requests.codes.ok, (
        f"Valid query validation failed: {response.status_code} {response.text}"
    )
    validated = response.json()["verified_query"]
    assert "sql_errors" not in validated or not validated["sql_errors"]
    assert "parameters" in validated
    assert len(validated["parameters"]) == 2


def test_verify_query_validation_missing_parameter(
    base_url_agent_server_session,
    api_test_semantic_model,
):
    """Test that missing parameter definitions are auto-generated."""
    from urllib.parse import urljoin

    import requests

    _, semantic_model = api_test_semantic_model

    verify_url = urljoin(
        base_url_agent_server_session,
        "/api/v2/semantic-data-models/verify-verified-query",
    )

    missing_param_query = {
        "semantic_data_model": semantic_model,
        "verified_query": {
            "name": "test missing param",
            "nlq": "Test missing parameter",
            "sql": "SELECT * FROM ai_systems WHERE Domain = :domain AND year = :year",
            "parameters": [
                {
                    "name": "domain",
                    "data_type": "string",
                    "example_value": "Language",
                    "description": "Domain filter",
                }
                # Missing 'year' parameter definition - should be auto-generated
            ],
        },
        "accept_initial_name": "test_missing_param",
    }

    response = requests.post(verify_url, json=missing_param_query)
    assert response.status_code == requests.codes.ok
    validated = response.json()["verified_query"]

    # Verify that both parameters are returned (user-provided + auto-generated)
    assert "parameters" in validated
    assert len(validated["parameters"]) == 2, "Should have 2 parameters (1 provided + 1 auto-generated)"

    # Find the user-provided domain parameter
    domain_param = next(
        (p for p in validated["parameters"] if p["name"] == "domain"),
        None,
    )
    assert domain_param is not None, "Should have 'domain' parameter"
    assert domain_param["data_type"] == "string"
    assert domain_param["example_value"] == "Language"
    assert domain_param["description"] == "Domain filter"

    # Find the auto-generated year parameter
    year_param = next(
        (p for p in validated["parameters"] if p["name"] == "year"),
        None,
    )
    assert year_param is not None, "Should have auto-generated 'year' parameter"
    assert year_param["data_type"] == "string", "Auto-generated params should default to string"
    assert year_param["example_value"] is None, "Auto-generated params should have null example_value"
    assert "provide description" in year_param["description"].lower(), (
        "Auto-generated params should have placeholder description"
    )


def test_verify_query_validation_extra_parameter(
    base_url_agent_server_session,
    api_test_semantic_model,
):
    """Test that extra/unused parameter definitions are detected."""
    from urllib.parse import urljoin

    import requests

    _, semantic_model = api_test_semantic_model

    verify_url = urljoin(
        base_url_agent_server_session,
        "/api/v2/semantic-data-models/verify-verified-query",
    )

    extra_param_query = {
        "semantic_data_model": semantic_model,
        "verified_query": {
            "name": "test extra param",
            "nlq": "Test extra parameter",
            "sql": "SELECT * FROM ai_systems WHERE Domain = :domain",
            "parameters": [
                {
                    "name": "domain",
                    "data_type": "string",
                    "example_value": "Language",
                    "description": "Domain filter",
                },
                {
                    "name": "year",
                    "data_type": "integer",
                    "example_value": 2022,
                    "description": "Year filter",
                },
                # 'year' is defined but not used in SQL
            ],
        },
        "accept_initial_name": "test_extra_param",
    }

    response = requests.post(verify_url, json=extra_param_query)
    assert response.status_code == requests.codes.ok
    validated = response.json()["verified_query"]
    assert validated.get("parameter_errors")

    # Verify we have an individual error message for the 'year' parameter
    parameter_errors = validated["parameter_errors"]
    year_error = next(
        (err for err in parameter_errors if "year" in err["message"].lower()),
        None,
    )
    assert year_error is not None, "Should have error message for 'year' parameter"
    assert "not used" in year_error["message"].lower()
    assert "'year'" in year_error["message"] or '"year"' in year_error["message"]
    # Verify it uses the parameter validation kind (warnings also use this kind)
    assert year_error["kind"] == "verified_query_parameters_validation_failed"


def test_verify_query_validation_missing_example_value(
    base_url_agent_server_session,
    api_test_semantic_model,
):
    """Test that missing example_value (None) is allowed and validates successfully."""
    from urllib.parse import urljoin

    import requests

    _, semantic_model = api_test_semantic_model

    verify_url = urljoin(
        base_url_agent_server_session,
        "/api/v2/semantic-data-models/verify-verified-query",
    )

    missing_example_query = {
        "semantic_data_model": semantic_model,
        "verified_query": {
            "name": "test missing example",
            "nlq": "Test missing example value",
            "sql": "SELECT * FROM ai_systems WHERE Domain = :domain",
            "parameters": [
                {
                    "name": "domain",
                    "data_type": "string",
                    "example_value": None,  # Missing example value is allowed
                    "description": "Domain filter",
                }
            ],
        },
        "accept_initial_name": "test missing example",
    }

    response = requests.post(verify_url, json=missing_example_query)
    assert response.status_code == requests.codes.ok
    validated = response.json()["verified_query"]

    # example_value=None is allowed, so there should be no errors
    assert not validated.get("sql_errors") or len(validated["sql_errors"]) == 0
    assert not validated.get("name_errors") or len(validated["name_errors"]) == 0
    assert not validated.get("nlq_errors") or len(validated["nlq_errors"]) == 0

    # Verify parameter was accepted with None example_value
    assert "parameters" in validated
    assert len(validated["parameters"]) == 1
    assert validated["parameters"][0]["name"] == "domain"
    assert validated["parameters"][0]["example_value"] is None


def test_verify_query_validation_invalid_parameter_data_type(
    base_url_agent_server_session,
    api_test_semantic_model,
):
    """Test that invalid data_type values are rejected."""
    from urllib.parse import urljoin

    import requests

    _, semantic_model = api_test_semantic_model

    verify_url = urljoin(
        base_url_agent_server_session,
        "/api/v2/semantic-data-models/verify-verified-query",
    )

    invalid_type_query = {
        "semantic_data_model": semantic_model,
        "verified_query": {
            "name": "test invalid data type",
            "nlq": "Test invalid parameter datatype",
            "sql": "SELECT * FROM ai_systems WHERE Domain = :domain",
            "parameters": [
                {
                    "name": "domain",
                    "data_type": "uuid",
                    "example_value": "Language",
                    "description": "Domain filter",
                }
            ],
        },
        "accept_initial_name": "test_invalid_data_type",
    }

    response = requests.post(verify_url, json=invalid_type_query)
    assert response.status_code == requests.codes.ok
    validated = response.json()["verified_query"]
    assert validated.get("parameter_errors")

    # Verify we have an individual error message for the 'domain' parameter
    parameter_errors = validated["parameter_errors"]
    domain_error = next(
        (err for err in parameter_errors if "domain" in err["message"].lower()),
        None,
    )
    assert domain_error is not None, "Should have error message for 'domain' parameter"
    # Pydantic error message format:
    # "Parameter 'domain', field 'data_type': Input should be 'integer', 'float', 'boolean', 'string' or 'datetime'"
    assert "'domain'" in domain_error["message"] or '"domain"' in domain_error["message"]
    assert "data_type" in domain_error["message"]
    assert "integer" in domain_error["message"]
    assert "string" in domain_error["message"]
    # Verify it uses the parameter validation kind
    assert domain_error["kind"] == "verified_query_parameters_validation_failed"


def test_verify_query_validation_example_value_mismatch(
    base_url_agent_server_session,
    api_test_semantic_model,
):
    """Test that example_value must match the declared data_type."""
    from urllib.parse import urljoin

    import requests

    _, semantic_model = api_test_semantic_model

    verify_url = urljoin(
        base_url_agent_server_session,
        "/api/v2/semantic-data-models/verify-verified-query",
    )

    mismatch_query = {
        "semantic_data_model": semantic_model,
        "verified_query": {
            "name": "test example value mismatch",
            "nlq": "Test example value mismatch",
            "sql": "SELECT * FROM ai_systems WHERE year = :year",
            "parameters": [
                {
                    "name": "year",
                    "data_type": "integer",
                    "example_value": "not-an-int",
                    "description": "Year filter",
                }
            ],
        },
        "accept_initial_name": "test_example_value_mismatch",
    }

    response = requests.post(verify_url, json=mismatch_query)
    assert response.status_code == requests.codes.ok
    validated = response.json()["verified_query"]
    assert validated.get("parameter_errors")

    # Verify we have an individual error message for the 'year' parameter
    parameter_errors = validated["parameter_errors"]
    year_error = next(
        (err for err in parameter_errors if "year" in err["message"].lower()),
        None,
    )
    assert year_error is not None, "Should have error message for 'year' parameter"
    assert "example_value" in year_error["message"].lower()
    assert "data_type" in year_error["message"].lower()
    assert "'year'" in year_error["message"] or '"year"' in year_error["message"]
    # Verify it uses the parameter validation kind
    assert year_error["kind"] == "verified_query_parameters_validation_failed"


def test_verify_query_validation_datetime_requires_iso_format(
    base_url_agent_server_session,
    api_test_semantic_model,
):
    """Test that datetime parameters require ISO-8601 formatted example_value."""
    from urllib.parse import urljoin

    import requests

    _, semantic_model = api_test_semantic_model

    verify_url = urljoin(
        base_url_agent_server_session,
        "/api/v2/semantic-data-models/verify-verified-query",
    )

    bad_datetime_query = {
        "semantic_data_model": semantic_model,
        "verified_query": {
            "name": "test datetime example invalid",
            "nlq": "Test datetime example invalid",
            "sql": "SELECT * FROM ai_systems WHERE created_at >= :start_time",
            "parameters": [
                {
                    "name": "start_time",
                    "data_type": "datetime",
                    "example_value": "yesterday",
                    "description": "Start time filter",
                }
            ],
        },
        "accept_initial_name": "test_datetime_example_invalid",
    }

    response = requests.post(verify_url, json=bad_datetime_query)
    assert response.status_code == requests.codes.ok
    validated = response.json()["verified_query"]
    assert validated.get("parameter_errors")

    # Verify we have an individual error message for the 'start_time' parameter
    parameter_errors = validated["parameter_errors"]
    start_time_error = next(
        (err for err in parameter_errors if "start_time" in err["message"].lower()),
        None,
    )
    assert start_time_error is not None, "Should have error message for 'start_time' parameter"
    assert "example_value" in start_time_error["message"].lower()
    assert "data_type" in start_time_error["message"].lower()
    assert "'start_time'" in start_time_error["message"] or '"start_time"' in start_time_error["message"]
    # Verify it uses the parameter validation kind
    assert start_time_error["kind"] == "verified_query_parameters_validation_failed"


def test_verify_query_auto_generates_all_parameters_when_none_provided(
    base_url_agent_server_session,
    api_test_semantic_model,
):
    """Test that all parameters are auto-generated when no definitions are provided."""
    from urllib.parse import urljoin

    import requests

    _, semantic_model = api_test_semantic_model

    verify_url = urljoin(
        base_url_agent_server_session,
        "/api/v2/semantic-data-models/verify-verified-query",
    )

    # Query with parameters but no parameter definitions
    no_params_query = {
        "semantic_data_model": semantic_model,
        "verified_query": {
            "name": "test auto generate all params",
            "nlq": "Get AI systems filtered by domain and year",
            "sql": "SELECT * FROM ai_systems WHERE Domain = :domain AND year = :year",
            # No parameters provided - should be auto-generated
        },
        "accept_initial_name": "test_auto_generate_all_params",
    }

    response = requests.post(verify_url, json=no_params_query)
    assert response.status_code == requests.codes.ok
    validated = response.json()["verified_query"]

    # Verify that both parameters are auto-generated
    assert "parameters" in validated
    assert len(validated["parameters"]) == 2, "Should have 2 auto-generated parameters"

    # Check domain parameter
    domain_param = next(
        (p for p in validated["parameters"] if p["name"] == "domain"),
        None,
    )
    assert domain_param is not None, "Should have auto-generated 'domain' parameter"
    assert domain_param["data_type"] == "string"
    assert domain_param["example_value"] is None
    assert "provide description" in domain_param["description"].lower()

    # Check year parameter
    year_param = next(
        (p for p in validated["parameters"] if p["name"] == "year"),
        None,
    )
    assert year_param is not None, "Should have auto-generated 'year' parameter"
    assert year_param["data_type"] == "string"
    assert year_param["example_value"] is None
    assert "provide description" in year_param["description"].lower()

    # Verify no errors (auto-generation is not an error)
    assert not validated.get("parameter_errors")
