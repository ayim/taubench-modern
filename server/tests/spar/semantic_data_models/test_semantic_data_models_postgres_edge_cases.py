"""
Tests for Postgres-specific edge cases in semantic data models.

This test module focuses on special PostgreSQL data types that have been known
to cause issues, including:
- JSON/JSONB, ARRAY, UUID columns
- User-defined types: ENUM, composite types, domain types, range types
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

    from agent_platform.orchestrator.agent_server_client import AgentServerClient

    from agent_platform.core.payloads.data_connection import DataConnection

pytestmark = [
    pytest.mark.spar,
    pytest.mark.semantic_data_models,
    pytest.mark.semantic_data_models_edge_cases,
]

# Edge case tables with special column types
EDGE_CASE_TABLES = [
    "products_with_json",  # JSON, JSONB, TEXT[], UUID
    "user_preferences",  # JSONB with nested structures
    "event_logs",  # JSON payloads, INTEGER[]
    "locations",  # NUMERIC[], JSONB addresses
    "advanced_products",  # UUID, JSONB, TEXT[], INTEGER[]
    "orders_with_enums",  # ENUM types
    "customers_with_composite_types",  # Composite types, domain types
    "products_with_domain_types",  # Domain types, composite types, range types
    "support_tickets",  # Mixed: ENUMs, domains, composite types
]


@pytest.fixture(scope="module")
def agent_for_edge_cases(
    agent_factory: Callable[..., str],
    openai_api_key: str,
) -> str:
    """Create an agent for testing edge case tables."""
    agent_id = agent_factory(
        action_packages=[],
        platform_configs=[
            {
                "kind": "openai",
                "openai_api_key": openai_api_key,
                "models": {"openai": ["gpt-5-low"]},
            },
        ],
        runbook=(
            "You are an agent that creates data frames using data_frames_create_from_sql. "
            "The database includes PostgreSQL edge case types: JSON, JSONB, ARRAY, UUID, "
            "ENUM, composite types, domain types, and range types."
        ),
        description="Agent for testing PostgreSQL edge case types",
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


@pytest.fixture(scope="module")
def edge_case_semantic_model(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    agent_for_edge_cases: str,
) -> dict[str, Any]:
    """
    Generate a semantic model with all edge case tables.

    Returns:
        dict: Generated semantic data model response
    """
    from dataclasses import asdict

    from agent_platform.core.payloads.semantic_data_model_payloads import (
        DataConnectionInfo,
        GenerateSemanticDataModelPayload,
    )

    client, data_connection = agent_server_client_with_data_connection
    agent_id = agent_for_edge_cases

    assert data_connection.id is not None
    inspect_response = client.inspect_data_connection(
        connection_id=data_connection.id,
        tables_to_inspect=[
            {"name": table, "database": None, "schema": None, "columns_to_inspect": None}
            for table in EDGE_CASE_TABLES
        ],
    )

    payload = GenerateSemanticDataModelPayload(
        name="postgres_edge_cases_model",
        description=None,
        data_connections_info=[
            DataConnectionInfo(
                data_connection_id=data_connection.id,
                tables_info=inspect_response["tables"],
            ),
        ],
        files_info=[],
        agent_id=agent_id,
    )

    return client.generate_semantic_data_model(asdict(payload))


def test_edge_case_semantic_model_generation(
    edge_case_semantic_model: dict[str, Any],
):
    """Test that semantic model is generated with all edge case tables."""
    assert edge_case_semantic_model is not None
    assert "semantic_model" in edge_case_semantic_model

    semantic_model = edge_case_semantic_model["semantic_model"]
    assert semantic_model["name"] is not None

    # Verify all edge case tables are in the model
    tables = semantic_model["tables"]
    table_names = [table["base_table"]["table"] for table in tables]
    for expected_table in EDGE_CASE_TABLES:
        assert expected_table in table_names, f"Table {expected_table} not in semantic model"

    for table in tables:
        assert table["description"] is not None, f"Expected description for table {table['name']}"
        assert table["synonyms"] is not None, f"Expected synonyms for table {table['name']}"
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
def created_edge_case_model_id(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    edge_case_semantic_model: dict[str, Any],
) -> str:
    """Create the edge case semantic data model and return its ID."""
    client, _ = agent_server_client_with_data_connection
    created_model = client.create_semantic_data_model(edge_case_semantic_model)
    return created_model["semantic_data_model_id"]


@pytest.fixture(scope="module")
def agent_with_edge_case_semantic_data_model(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    created_edge_case_model_id: str,
    agent_for_edge_cases: str,
) -> str:
    """Create an agent with the edge case model assigned. Returns (agent_id, thread_id)."""
    client, _ = agent_server_client_with_data_connection
    agent_id = agent_for_edge_cases

    client.set_agent_semantic_data_models(agent_id, [created_edge_case_model_id])

    return agent_id


def test_edge_case_model_persistence(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    edge_case_semantic_model: dict[str, Any],
    created_edge_case_model_id: str,
):
    """Test that edge case model can be created and retrieved."""
    client, _ = agent_server_client_with_data_connection

    # Retrieve the model
    retrieved_model = client.get_semantic_data_model(created_edge_case_model_id)

    # Verify it matches the original
    assert retrieved_model == edge_case_semantic_model["semantic_model"]


@pytest.mark.parametrize(
    ("query", "expected_table"),
    [
        (
            "What are the specifications and tags for the Smart Watch Pro and "
            "Gaming Laptop products",
            "products_with_json",
        ),
        (
            "Show me preferences for user 1 including their theme setting and "
            "notification preferences from stored JSONB",
            "user_preferences",
        ),
        (
            "Get all events with their affected entities array and payloads, "
            "showing the order placed event and inventory updated event",
            "event_logs",
        ),
        (
            "List all locations with their coordinates arrays showing the warehouse "
            "and distribution center locations",
            "locations",
        ),
        (
            "Get all orders with their priority level and status, specifically looking "
            "for those marked as urgent or critical priority",
            "orders_with_enums",
        ),
        (
            "Show customers with email addresses alice.johnson@example.com and "
            "david.brown@company.org including their shipping addresses",
            "customers_with_composite_types",
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
    """Test agent can query various edge case tables."""
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
