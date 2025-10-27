from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

    from agent_platform.orchestrator.agent_server_client import AgentServerClient

    from agent_platform.core.payloads.data_connection import DataConnection

pytestmark = [pytest.mark.spar, pytest.mark.semantic_data_models]


def test_generate_semantic_data_model_basic(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    agent_factory: Callable[[], str],
    openai_api_key: str,
):
    """Test generating a semantic data model from the e-commerce schema."""
    from dataclasses import asdict

    from agent_platform.core.payloads.semantic_data_model_payloads import (
        DataConnectionInfo,
        GenerateSemanticDataModelPayload,
    )

    client, data_connection = agent_server_client_with_data_connection
    agent_factory_with_params: Callable[..., str] = agent_factory
    agent_id = agent_factory_with_params(
        platform_configs=[
            {
                "kind": "openai",
                "openai_api_key": openai_api_key,
                "models": {"openai": ["gpt-5"]},
            }
        ]
    )

    # Inspect the data connection with selected tables before generating the model
    assert data_connection.id is not None
    inspect_response = client.inspect_data_connection(
        connection_id=data_connection.id,
        # Assume defaults
        tables_to_inspect=[
            {"name": "customers", "database": None, "schema": None, "columns_to_inspect": None},
            {"name": "orders", "database": None, "schema": None, "columns_to_inspect": None},
        ],
    )

    # Verify inspection response has expected structure
    assert "tables" in inspect_response
    assert len(inspect_response["tables"]) > 0

    # Create the payload for generating the semantic data model
    payload = GenerateSemanticDataModelPayload(
        name="test_model",  # Enhance should improve this
        description=None,  # Enhance should improve this
        data_connections_info=[
            DataConnectionInfo(
                data_connection_id=data_connection.id or "",
                tables_info=inspect_response["tables"],
            ),
        ],
        files_info=[],
        agent_id=agent_id,
    )

    # Generate the semantic data model
    result = client.generate_semantic_data_model(asdict(payload))

    # Verify the result
    assert result is not None
    assert "semantic_model" in result

    # Verify the semantic model has expected structure
    semantic_model = result["semantic_model"]
    assert semantic_model["name"]
    # Enhancement should have changed the name
    assert semantic_model["name"] != "test_model"
    assert semantic_model["description"]  # Enhancement should have added one

    # Verify tables are in the model
    assert "tables" in semantic_model
    tables = semantic_model["tables"]
    table_names = [table["base_table"]["table"] for table in tables]
    assert "customers" in table_names, "Expected 'customers' table to be in the model"
    assert "orders" in table_names, "Expected 'orders' table to be in the model"

    # Verify table enhancements (these may be flaky)
    for table in tables:
        assert table["description"] is not None, f"Expected description for table {table['name']}"
        assert table["synonyms"] is not None, f"Expected synonyms for table {table['name']}"

        # Verify columns are in the table
        columns = (
            table.get("dimensions", [])
            + table.get("facts", [])
            + table.get("metrics", [])
            + table.get("time_dimensions", [])
        )
        assert len(columns) > 0, f"Expected columns for table {table['name']}"
        for column in columns:
            assert column["name"] is not None, f"Expected name for column {column['name']}"
            assert column["expr"] is not None, f"Expected expr for column {column['name']}"
            assert column["description"] is not None, (
                f"Expected description for column {column['name']}"
            )
            assert column["synonyms"] is not None, f"Expected synonyms for column {column['name']}"


@pytest.fixture(scope="module")
def agent_for_full_model(
    agent_factory: Callable[..., str],
    openai_api_key: str,
) -> str:
    """Create an agent for the full model."""
    return agent_factory(
        action_packages=[],
        platform_configs=[
            {
                "kind": "openai",
                "openai_api_key": openai_api_key,
                "models": {"openai": ["gpt-5"]},
            }
        ],
        runbook=(
            "You are an agent which should create data frames using the "
            "data_frames_create_from_sql tool, referencing the semantic data model "
            "that has been provided to answer user's questions."
        ),
        description="Agent for testing the full semantic data model",
    )


@pytest.fixture(scope="module")
def generated_semantic_data_model(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    agent_for_full_model: str,
) -> dict[str, Any]:
    """
    Fixture that generates a semantic data model from all e-commerce tables.

    Returns:
        dict: Generated semantic data model response with 'semantic_model' key
    """
    from dataclasses import asdict

    from agent_platform.core.payloads.data_connection import PostgresDataConnectionConfiguration
    from agent_platform.core.payloads.semantic_data_model_payloads import (
        DataConnectionInfo,
        GenerateSemanticDataModelPayload,
    )

    client, data_connection = agent_server_client_with_data_connection
    agent_id = agent_for_full_model

    # Inspect the data connection with all tables
    assert data_connection.id is not None
    assert data_connection.configuration is not None
    assert isinstance(data_connection.configuration, PostgresDataConnectionConfiguration)
    inspect_response = client.inspect_data_connection(
        connection_id=data_connection.id,
        # Assume defaults
        tables_to_inspect=[
            {
                "name": "customers",
                "database": None,
                "schema": None,
                "columns_to_inspect": None,
            },
            {
                "name": "products",
                "database": None,
                "schema": None,
                "columns_to_inspect": None,
            },
            {
                "name": "orders",
                "database": None,
                "schema": None,
                "columns_to_inspect": None,
            },
            {
                "name": "order_items",
                "database": None,
                "schema": None,
                "columns_to_inspect": None,
            },
        ],
    )

    # Create the payload for generating the semantic data model
    payload = GenerateSemanticDataModelPayload(
        name="test_full_model",
        description=None,
        data_connections_info=[
            DataConnectionInfo(
                data_connection_id=data_connection.id or "",
                tables_info=inspect_response["tables"],
            ),
        ],
        files_info=[],
        agent_id=agent_id,
    )

    # Generate the semantic data model
    return client.generate_semantic_data_model(asdict(payload))


def test_generated_semantic_data_model_structure(
    generated_semantic_data_model: dict[str, Any],
):
    """Test that the generated semantic data model has the expected structure."""
    # Verify the result
    assert generated_semantic_data_model is not None
    assert "semantic_model" in generated_semantic_data_model

    semantic_model = generated_semantic_data_model["semantic_model"]

    # Verify basic model properties
    assert semantic_model["name"] != "test_full_model"
    assert semantic_model["description"] is not None

    # Verify all tables are present
    assert "tables" in semantic_model
    tables = semantic_model["tables"]
    base_table_names = [table["base_table"]["table"] for table in tables]
    assert len(base_table_names) == 4, f"Expected 4 base tables, got {len(base_table_names)}"
    assert "customers" in base_table_names, "Expected 'customers' table to be in the model"
    assert "products" in base_table_names, "Expected 'products' table to be in the model"
    assert "orders" in base_table_names, "Expected 'orders' table to be in the model"
    assert "order_items" in base_table_names, "Expected 'order_items' table to be in the model"

    # Verify each table has expected structure
    for table in tables:
        assert "name" in table
        assert "base_table" in table
        assert table["description"] is not None, f"Expected description for table {table['name']}"
        assert table["synonyms"] is not None, f"Expected synonyms for table {table['name']}"

        # Verify columns are in the table
        columns = (
            table.get("dimensions", [])
            + table.get("facts", [])
            + table.get("metrics", [])
            + table.get("time_dimensions", [])
        )
        assert len(columns) > 0, f"Expected columns for table {table['name']}"
        for column in columns:
            assert column["name"] is not None, f"Expected name for column {column['name']}"
            assert column["expr"] is not None, f"Expected expr for column {column['name']}"
            assert column["description"] is not None, (
                f"Expected description for column {column['name']}"
            )
            assert column["synonyms"] is not None, f"Expected synonyms for column {column['name']}"


@pytest.fixture(scope="module")
def created_semantic_data_model_id(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    generated_semantic_data_model: dict[str, Any],
) -> str:
    """
    Fixture that creates a semantic data model in the agent server.

    Returns:
        str: The semantic data model ID
    """
    client, _ = agent_server_client_with_data_connection

    # Create the semantic data model
    created_model = client.create_semantic_data_model(generated_semantic_data_model)
    return created_model["semantic_data_model_id"]


def test_created_semantic_data_model_retrieval(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    generated_semantic_data_model: dict[str, Any],
    created_semantic_data_model_id: str,
):
    """Test that the created semantic data model can be retrieved correctly."""
    client, _ = agent_server_client_with_data_connection

    # Retrieve the model
    retrieved_model = client.get_semantic_data_model(created_semantic_data_model_id)

    # Verify the retrieved model matches the original
    assert retrieved_model == generated_semantic_data_model["semantic_model"]


@pytest.fixture(scope="module")
def agent_and_thread_with_semantic_data_model(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    created_semantic_data_model_id: str,
    agent_for_full_model: str,
) -> tuple[str, str]:
    """
    Fixture that creates an agent with the semantic data model assigned.

    Returns:
        tuple[str, str]: (agent_id, thread_id)
    """
    client, _ = agent_server_client_with_data_connection
    agent_id = agent_for_full_model

    # Create a thread for the agent
    thread_id = client.create_thread_and_return_thread_id(agent_id)

    # Assign the semantic data model to the agent
    client.set_agent_semantic_data_models(agent_id, [created_semantic_data_model_id])

    return agent_id, thread_id


def test_agent_queries_semantic_data_model(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    agent_and_thread_with_semantic_data_model: tuple[str, str],
    created_semantic_data_model_id: str,
):
    """
    Test that the agent can query the semantic data model.

    Uses data_frames_create_from_sql to query the e-commerce data.
    """
    client, _ = agent_server_client_with_data_connection
    agent_id, thread_id = agent_and_thread_with_semantic_data_model

    # Verify the model was assigned to the agent
    agent_models = client.get_agent_semantic_data_models(agent_id)
    assert len(agent_models) == 1
    assert created_semantic_data_model_id in agent_models[0]

    # Send a query to the agent about the e-commerce data
    result, tool_calls = client.send_message_to_agent_thread(
        agent_id,
        thread_id,
        "What are the names of all customers who have placed orders?",
    )

    # Verify that the data_frames_create_from_sql tool was called (may be flaky)
    data_frames_tool_call_found = False
    for tool_call in tool_calls:
        if tool_call.tool_name == "data_frames_create_from_sql":
            data_frames_tool_call_found = True
            break

    assert data_frames_tool_call_found, (
        "Expected data_frames_create_from_sql tool call not found. "
        f"Full LLM response: {result} \n"
        f"Tool calls: {[tc.tool_name for tc in tool_calls]}"
    )

    # Verify the result contains relevant information (as it's generated, we can't check data)
    result_str = str(result)
    assert len(result_str) > 0, f"Expected non-empty result from agent query, got: {result_str}"
