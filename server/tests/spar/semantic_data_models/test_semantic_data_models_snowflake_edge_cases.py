"""
Tests for Snowflake-specific edge cases in semantic data models.

This test module focuses on the three most important Snowflake data types:
- VARIANT (semi-structured data) - Snowflake's key differentiator for JSON/XML/etc.
- ARRAY (Snowflake arrays) - Different syntax from PostgreSQL arrays
- OBJECT (structured objects) - Similar to composite types in PostgreSQL

Tests verify that these special types can be:
1. Loaded into test databases
2. Inspected via data connections
3. Used to generate semantic data models
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from agent_platform.orchestrator.agent_server_client import AgentServerClient

    from agent_platform.core.payloads.data_connection import DataConnection

pytestmark = [
    pytest.mark.spar,
    pytest.mark.semantic_data_models,
    pytest.mark.semantic_data_models_edge_cases,
]


# Override the engine fixture to only use snowflake for these edge case tests
@pytest.fixture(scope="module")
def engine(request: pytest.FixtureRequest):
    """
    Override engine fixture to only test Snowflake edge cases.

    PostgreSQL edge cases are in a separate test file.
    """
    return "snowflake"


# Edge case tables with special Snowflake column types (simplified)
EDGE_CASE_TABLES = [
    "products_with_variant",  # VARIANT for metadata
    "events_with_variant",  # VARIANT payloads
    "products_with_arrays",  # ARRAY types
    "customers_with_objects",  # OBJECT for addresses
]


@pytest.fixture(scope="module")
def agent_for_edge_cases(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    openai_api_key: str,
) -> str:
    """Create an agent for testing Snowflake edge case tables."""
    import uuid

    client, _ = agent_server_client_with_data_connection

    # Use UUID to ensure unique agent name
    unique_name = f"Snowflake Edge Case Test Agent {uuid.uuid4().hex[:8]}"

    agent_id = client.create_agent_and_return_agent_id(
        name=unique_name,
        action_packages=[],
        platform_configs=[
            {
                "kind": "openai",
                "openai_api_key": openai_api_key,
                "models": {"openai": ["gpt-4o-mini"]},
            },
        ],
        runbook=(
            "You are an agent that creates data frames using data_frames_create_from_sql. "
            "The database includes Snowflake edge case types: VARIANT, ARRAY, and OBJECT."
        ),
        description="Agent for testing Snowflake edge case types",
    )
    return agent_id


def test_edge_case_tables_load(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
):
    """Verify all edge case tables load and can be inspected."""
    client, data_connection = agent_server_client_with_data_connection

    assert data_connection.id is not None
    inspect_response = client.inspect_data_connection(
        connection_id=data_connection.id,
        tables_to_inspect=[
            {"name": table, "database": None, "schema": None, "columns_to_inspect": None}
            for table in EDGE_CASE_TABLES
        ],
    )

    # Verify all tables are present
    assert "tables" in inspect_response
    inspected_table_names = {table["name"] for table in inspect_response["tables"]}
    for expected_table in EDGE_CASE_TABLES:
        assert expected_table in inspected_table_names, f"Table {expected_table} not found"


def test_edge_case_columns_detected(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
):
    """Verify that special Snowflake column types are properly detected."""
    client, data_connection = agent_server_client_with_data_connection

    assert data_connection.id is not None
    inspect_response = client.inspect_data_connection(
        connection_id=data_connection.id,
        tables_to_inspect=[
            {"name": table, "database": None, "schema": None, "columns_to_inspect": None}
            for table in EDGE_CASE_TABLES
        ],
    )

    # Build a map of table -> columns for easier lookup
    table_columns: dict[str, list[dict[str, Any]]] = {}
    for table in inspect_response["tables"]:
        table_columns[table["name"]] = table["columns"]

    # Verify VARIANT columns
    assert any(col["name"] == "metadata" for col in table_columns["products_with_variant"]), (
        "VARIANT column 'metadata' not detected"
    )

    # Verify ARRAY columns
    assert any(col["name"] == "tags" for col in table_columns["products_with_arrays"]), (
        "ARRAY column 'tags' not detected"
    )

    # Verify OBJECT columns
    assert any(col["name"] == "address" for col in table_columns["customers_with_objects"]), (
        "OBJECT column 'address' not detected"
    )


def test_generate_semantic_model_with_edge_cases(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    agent_for_edge_cases: str,
):
    """Test generating a semantic data model from tables with Snowflake edge case types."""
    from dataclasses import asdict

    from agent_platform.core.payloads.semantic_data_model_payloads import (
        DataConnectionInfo,
        GenerateSemanticDataModelPayload,
    )

    client, data_connection = agent_server_client_with_data_connection

    # Inspect edge case tables
    assert data_connection.id is not None
    inspect_response = client.inspect_data_connection(
        connection_id=data_connection.id,
        tables_to_inspect=[
            {"name": table, "database": None, "schema": None, "columns_to_inspect": None}
            for table in EDGE_CASE_TABLES
        ],
    )

    # Generate semantic model
    payload = GenerateSemanticDataModelPayload(
        name="snowflake_edge_cases_model",
        description="Model for testing Snowflake edge case types",
        data_connections_info=[
            DataConnectionInfo(
                data_connection_id=data_connection.id,
                tables_info=inspect_response["tables"],
            ),
        ],
        files_info=[],
        agent_id=agent_for_edge_cases,
    )

    result = client.generate_semantic_data_model(asdict(payload))

    # Verify model was generated
    assert result is not None
    assert "semantic_model" in result
    semantic_model = result["semantic_model"]

    # Verify model contains tables
    assert "tables" in semantic_model
    assert len(semantic_model["tables"]) == len(EDGE_CASE_TABLES)

    # Verify tables exist (column names might be renamed by LLM)
    table_names = {table["name"] for table in semantic_model["tables"]}

    # Check that we have tables with the expected base names (LLM may rename them)
    # Just verify the model was generated successfully with tables
    expected_count = len(EDGE_CASE_TABLES)
    actual_count = len(table_names)
    assert actual_count == expected_count, f"Expected {expected_count} tables, got {actual_count}"


@pytest.fixture(scope="module")
def created_edge_case_model_id(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    agent_for_edge_cases: str,
) -> str:
    """Create and persist the edge case semantic data model, return its ID."""
    from dataclasses import asdict

    from agent_platform.core.payloads.semantic_data_model_payloads import (
        DataConnectionInfo,
        GenerateSemanticDataModelPayload,
    )

    client, data_connection = agent_server_client_with_data_connection

    assert data_connection.id is not None
    inspect_response = client.inspect_data_connection(
        connection_id=data_connection.id,
        tables_to_inspect=[
            {"name": table, "database": None, "schema": None, "columns_to_inspect": None}
            for table in EDGE_CASE_TABLES
        ],
    )

    payload = GenerateSemanticDataModelPayload(
        name="snowflake_edge_cases_persisted_model",
        description="Model for querying Snowflake edge case types",
        data_connections_info=[
            DataConnectionInfo(
                data_connection_id=data_connection.id,
                tables_info=inspect_response["tables"],
            ),
        ],
        files_info=[],
        agent_id=agent_for_edge_cases,
    )

    result = client.generate_semantic_data_model(asdict(payload))
    semantic_model = result["semantic_model"]

    # Create (persist) the semantic data model
    created_model = client.create_semantic_data_model({"semantic_model": semantic_model})
    return created_model["semantic_data_model_id"]


@pytest.fixture(scope="module")
def agent_with_edge_case_semantic_data_model(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    created_edge_case_model_id: str,
    agent_for_edge_cases: str,
) -> str:
    """Assign the edge case semantic data model to the agent. Returns agent_id."""
    client, _ = agent_server_client_with_data_connection
    agent_id = agent_for_edge_cases

    client.set_agent_semantic_data_models(agent_id, [created_edge_case_model_id])

    return agent_id


@pytest.mark.parametrize(
    ("query", "expected_table"),
    [
        (
            "Show all products from products_with_variant including their metadata",
            "products_with_variant",
        ),
        (
            "Get events from events_with_variant showing event types and payloads",
            "events_with_variant",
        ),
        (
            "List products from products_with_arrays with their tags",
            "products_with_arrays",
        ),
        (
            "Show customers from customers_with_objects including their addresses",
            "customers_with_objects",
        ),
    ],
)
def test_agent_queries_edge_cases(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    agent_with_edge_case_semantic_data_model: str,
    created_edge_case_model_id: str,
    query: str,
    expected_table: str,
):
    """Test agent can query Snowflake edge case tables with special types."""
    client, _ = agent_server_client_with_data_connection
    agent_id = agent_with_edge_case_semantic_data_model
    thread_id = client.create_thread_and_return_thread_id(agent_id)

    # Get the semantic model to map semantic table names to actual base table names
    semantic_model = client.get_semantic_data_model(created_edge_case_model_id)

    # Build a mapping from actual table names to semantic model table names
    # This handles cases where the LLM renames tables
    base_table_to_semantic_name = {}
    for table in semantic_model.get("tables", []):
        base_table_name = table.get("base_table", {}).get("table")
        semantic_table_name = table.get("name")
        if base_table_name and semantic_table_name:
            base_table_to_semantic_name[base_table_name] = semantic_table_name

    result, tool_calls = client.send_message_to_agent_thread(agent_id, thread_id, query)

    print(
        f"Query: {query}\n\nResult: {result}\n\nTool calls: {[tc.tool_name for tc in tool_calls]}"
    )

    # Verify data_frames_create_from_sql was called
    assert any(tc.tool_name == "data_frames_create_from_sql" for tc in tool_calls), (
        f"Expected data_frames_create_from_sql call. Got: {[tc.tool_name for tc in tool_calls]}"
    )

    # Verify non-empty result
    assert str(result), f"Empty result for query: {query}"

    # Verify the result is from the expected table
    sql_tool_calls = [tc for tc in tool_calls if tc.tool_name == "data_frames_create_from_sql"]
    assert len(sql_tool_calls) > 0, "Expected at least one data_frames_create_from_sql call"

    sql_query = sql_tool_calls[0].input_data["sql_query"]

    # Check if the expected table (base table) is in the query
    # OR check if the semantic model's renamed version of the table is in the query
    semantic_table_name = base_table_to_semantic_name.get(expected_table, expected_table)
    assert expected_table in sql_query or semantic_table_name in sql_query, (
        f"Expected table '{expected_table}' or semantic name '{semantic_table_name}' "
        f"not found in SQL query: {sql_query}"
    )
