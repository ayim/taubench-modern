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


def get_last_successful_sql_call(tool_calls: list) -> Any:
    """
    Get the last successful SQL tool call from a list of tool calls.

    Agents may make multiple attempts and self-correct after errors,
    so we want to validate the final successful attempt.

    Args:
        tool_calls: List of all tool calls

    Returns:
        The last successful data_frames_create_from_sql tool call

    Raises:
        AssertionError: If no successful SQL calls found
    """
    sql_tool_calls = [tc for tc in tool_calls if tc.tool_name == "data_frames_create_from_sql"]
    assert len(sql_tool_calls) > 0, (
        f"Expected data_frames_create_from_sql call. Got: {[tc.tool_name for tc in tool_calls]}"
    )

    # Filter for successful calls (no errors)
    successful_sql_calls = [tc for tc in sql_tool_calls if tc.error is None]
    assert len(successful_sql_calls) > 0, (
        f"No successful SQL queries. All {len(sql_tool_calls)} attempts failed. "
        f"Errors: {[tc.error for tc in sql_tool_calls]}"
    )

    # Return the last successful call
    return successful_sql_calls[-1]


def validate_sql_execution_and_data(
    client: AgentServerClient,
    thread_id: str,
    sql_tool_call: Any,
    expected_row_count: int | None = None,
    min_row_count: int = 0,
) -> dict:
    """
    Validate that SQL executed successfully and returned data.

    Args:
        client: Agent server client
        thread_id: Thread ID where tool was executed
        sql_tool_call: The tool call object from data_frames_create_from_sql
        expected_row_count: Expected exact number of rows (optional)
        min_row_count: Minimum expected rows (default: 0, means at least some data)

    Returns:
        dict: The data frame metadata

    Raises:
        AssertionError: If validation fails
    """
    # Verify tool executed without errors
    assert sql_tool_call.error is None, f"Tool execution failed with error: {sql_tool_call.error}"

    # Verify result contains data frame information
    assert sql_tool_call.result, f"Tool result is empty: {sql_tool_call.result}"

    # Get data frame name from tool input
    data_frame_name = sql_tool_call.input_data.get("new_data_frame_name")
    assert data_frame_name, f"Tool input missing new_data_frame_name: {sql_tool_call.input_data}"

    print(f"✅ Data frame created successfully: {data_frame_name}")

    # Verify the data frame actually contains data
    data_frames = client.get_data_frames(thread_id)
    matching_df = next((df for df in data_frames if df["name"] == data_frame_name), None)
    assert matching_df is not None, f"Data frame {data_frame_name} not found in thread"

    num_rows = matching_df["num_rows"]
    print(f"✅ Data frame contains {num_rows} rows")

    # Validate row counts
    if expected_row_count is not None:
        assert num_rows == expected_row_count, (
            f"Expected exactly {expected_row_count} rows, got {num_rows}"
        )
    else:
        assert num_rows >= min_row_count, f"Expected at least {min_row_count} rows, got {num_rows}"

    return matching_df


# Override the engine fixture to only use snowflake for these edge case tests
@pytest.fixture(scope="module")
def engine(request: pytest.FixtureRequest):
    """
    Override engine fixture to only test Snowflake edge cases.

    PostgreSQL edge cases are in a separate test file.
    """
    return "snowflake"


# Edge case tables with special Snowflake column types (simplified)
# Note: Snowflake stores unquoted identifiers as uppercase
EDGE_CASE_TABLES = [
    "PRODUCTS_WITH_VARIANT",  # VARIANT for metadata
    "EVENTS_WITH_VARIANT",  # VARIANT payloads
    "PRODUCTS_WITH_ARRAYS",  # ARRAY types
    "CUSTOMERS_WITH_OBJECTS",  # OBJECT for addresses
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
                "models": {"openai": ["gpt-4o"]},  # Use gpt-4o for better SQL generation
            },
        ],
        runbook=(
            "You are an agent that creates data frames using data_frames_create_from_sql. "
            "Follow the Snowflake SQL syntax rules provided in the semantic data model."
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

    # Verify VARIANT columns (Snowflake stores unquoted identifiers as uppercase)
    assert any(col["name"] == "METADATA" for col in table_columns["PRODUCTS_WITH_VARIANT"]), (
        "VARIANT column 'METADATA' not detected"
    )

    # Verify ARRAY columns
    assert any(col["name"] == "TAGS" for col in table_columns["PRODUCTS_WITH_ARRAYS"]), (
        "ARRAY column 'TAGS' not detected"
    )

    # Verify OBJECT columns
    assert any(col["name"] == "ADDRESS" for col in table_columns["CUSTOMERS_WITH_OBJECTS"]), (
        "OBJECT column 'ADDRESS' not detected"
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


# ============================================================================
# 1. VARIANT COLUMN QUERIES
# ============================================================================


@pytest.mark.parametrize(
    ("query", "expected_row_count"),
    [
        # Filter by nested VARIANT field - brand
        (
            "Show all products where the brand in metadata is 'TechCorp'",
            1,  # Only Smart Watch
        ),
        # Filter by nested VARIANT field in specifications
        (
            "Find products where battery in specifications is '48h'",
            1,  # Only Smart Watch
        ),
        # Show all VARIANT data
        (
            "Show all products with their metadata and specifications",
            2,  # Both products
        ),
    ],
)
@pytest.mark.flaky(max_runs=3, min_passes=1)
def test_query_variant_columns(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    agent_with_edge_case_semantic_data_model: str,
    query: str,
    expected_row_count: int,
):
    """Test querying VARIANT columns with nested JSON access."""
    client, _ = agent_server_client_with_data_connection
    agent_id = agent_with_edge_case_semantic_data_model
    thread_id = client.create_thread_and_return_thread_id(agent_id)

    result, tool_calls = client.send_message_to_agent_thread(agent_id, thread_id, query)

    print(f"\nQuery: {query}")
    print(f"Result: {result}")
    print(f"Tool calls: {[tc.tool_name for tc in tool_calls]}")

    # Use last successful SQL call
    sql_tool_call = get_last_successful_sql_call(tool_calls)

    # ✅ Validate SQL executed successfully and returned correct number of rows
    validate_sql_execution_and_data(
        client=client,
        thread_id=thread_id,
        sql_tool_call=sql_tool_call,
        expected_row_count=expected_row_count,
    )

    # Verify non-empty result
    assert str(result), f"Empty result for query: {query}"

    # Get the SQL query for debugging
    sql_query = sql_tool_call.input_data["sql_query"]
    print(f"Generated SQL: {sql_query}")


@pytest.mark.parametrize(
    ("query", "expected_row_count"),
    [
        # Filter events by type
        (
            "Show all events where event_type is 'user_login'",
            1,  # Only user_login event
        ),
        # All events
        (
            "List all events with their payloads",
            2,  # Both events
        ),
    ],
)
@pytest.mark.flaky(max_runs=3, min_passes=1)
def test_query_variant_events(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    agent_with_edge_case_semantic_data_model: str,
    query: str,
    expected_row_count: int,
):
    """Test querying VARIANT event payloads."""
    client, _ = agent_server_client_with_data_connection
    agent_id = agent_with_edge_case_semantic_data_model
    thread_id = client.create_thread_and_return_thread_id(agent_id)

    result, tool_calls = client.send_message_to_agent_thread(agent_id, thread_id, query)

    print(f"\nQuery: {query}")
    print(f"Result: {result}")
    print(f"Tool calls: {[tc.tool_name for tc in tool_calls]}")

    # Use last successful SQL call
    sql_tool_call = get_last_successful_sql_call(tool_calls)

    # ✅ Validate SQL executed successfully
    validate_sql_execution_and_data(
        client=client,
        thread_id=thread_id,
        sql_tool_call=sql_tool_call,
        expected_row_count=expected_row_count,
    )

    # Verify non-empty result
    assert str(result), f"Empty result for query: {query}"

    sql_query = sql_tool_call.input_data["sql_query"]
    print(f"Generated SQL: {sql_query}")


# ============================================================================
# 2. ARRAY COLUMN QUERIES
# ============================================================================


@pytest.mark.parametrize(
    ("query", "expected_row_count"),
    [
        # Filter by array contains - gaming
        (
            "Find products where tags contains 'gaming'",
            1,  # Only Gaming Laptop
        ),
        # Show all products with arrays
        (
            "Show all products with their tags and category IDs",
            2,  # Both products
        ),
    ],
)
@pytest.mark.flaky(max_runs=3, min_passes=1)
def test_query_array_columns(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    agent_with_edge_case_semantic_data_model: str,
    query: str,
    expected_row_count: int,
):
    """Test querying ARRAY columns with contains operations."""
    client, _ = agent_server_client_with_data_connection
    agent_id = agent_with_edge_case_semantic_data_model
    thread_id = client.create_thread_and_return_thread_id(agent_id)

    result, tool_calls = client.send_message_to_agent_thread(agent_id, thread_id, query)

    print(f"\nQuery: {query}")
    print(f"Result: {result}")
    print(f"Tool calls: {[tc.tool_name for tc in tool_calls]}")

    # Use last successful SQL call
    sql_tool_call = get_last_successful_sql_call(tool_calls)

    # ✅ Validate SQL executed successfully
    validate_sql_execution_and_data(
        client=client,
        thread_id=thread_id,
        sql_tool_call=sql_tool_call,
        expected_row_count=expected_row_count,
    )

    # Verify non-empty result
    assert str(result), f"Empty result for query: {query}"

    sql_query = sql_tool_call.input_data["sql_query"]
    print(f"Generated SQL: {sql_query}")


# ============================================================================
# 3. OBJECT COLUMN QUERIES
# ============================================================================


@pytest.mark.parametrize(
    ("query", "expected_row_count"),
    [
        # Filter by nested OBJECT field - city
        (
            "Find customers where the city in address is 'San Francisco'",
            1,  # Only Alice Johnson
        ),
        # Filter by nested OBJECT field - state
        (
            "List customers where the state in address is 'CA'",
            1,  # Only Alice Johnson
        ),
        # Filter by contact preference
        (
            "Show customers where preferred contact method is 'email'",
            1,  # Only Alice Johnson
        ),
    ],
)
@pytest.mark.flaky(max_runs=3, min_passes=1)
def test_query_object_columns(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    agent_with_edge_case_semantic_data_model: str,
    query: str,
    expected_row_count: int,
):
    """Test querying OBJECT columns with nested field access."""
    client, _ = agent_server_client_with_data_connection
    agent_id = agent_with_edge_case_semantic_data_model
    thread_id = client.create_thread_and_return_thread_id(agent_id)

    result, tool_calls = client.send_message_to_agent_thread(agent_id, thread_id, query)

    print(f"\nQuery: {query}")
    print(f"Result: {result}")
    print(f"Tool calls: {[tc.tool_name for tc in tool_calls]}")

    # Use last successful SQL call
    sql_tool_call = get_last_successful_sql_call(tool_calls)

    # ✅ Validate SQL executed successfully
    validate_sql_execution_and_data(
        client=client,
        thread_id=thread_id,
        sql_tool_call=sql_tool_call,
        expected_row_count=expected_row_count,
    )

    # Verify non-empty result
    assert str(result), f"Empty result for query: {query}"

    sql_query = sql_tool_call.input_data["sql_query"]
    print(f"Generated SQL: {sql_query}")


# ============================================================================
# 4. BASIC TABLE QUERIES (Original tests kept for backward compatibility)
# ============================================================================


@pytest.mark.parametrize(
    ("query", "min_row_count"),
    [
        (
            "Show all products with VARIANT metadata and specifications",
            2,  # Both products with variant
        ),
        (
            "Get all events showing event types and payloads",
            2,  # Both events
        ),
        (
            "List all products with array tags",
            2,  # Both products with arrays
        ),
        (
            "Show all customers with their addresses",
            2,  # Both customers
        ),
    ],
)
@pytest.mark.flaky(max_runs=3, min_passes=1)
def test_agent_queries_edge_cases_basic(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    agent_with_edge_case_semantic_data_model: str,
    query: str,
    min_row_count: int,
):
    """Test agent can query Snowflake edge case tables with special types."""
    client, _ = agent_server_client_with_data_connection
    agent_id = agent_with_edge_case_semantic_data_model
    thread_id = client.create_thread_and_return_thread_id(agent_id)

    result, tool_calls = client.send_message_to_agent_thread(agent_id, thread_id, query)

    print(f"\nQuery: {query}")
    print(f"Result: {result}")
    print(f"Tool calls: {[tc.tool_name for tc in tool_calls]}")

    # Use last successful SQL call (agents may need multiple attempts)
    sql_tool_call = get_last_successful_sql_call(tool_calls)

    # ✅ Validate SQL executed successfully and returned data
    validate_sql_execution_and_data(
        client=client,
        thread_id=thread_id,
        sql_tool_call=sql_tool_call,
        min_row_count=min_row_count,
    )

    # Verify non-empty result
    assert str(result), f"Empty result for query: {query}"

    # Get the SQL query for debugging
    sql_query = sql_tool_call.input_data["sql_query"]
    print(f"Generated SQL: {sql_query}")

    # Note: We don't assert specific SQL patterns because the LLM may generate
    # different column/table names on each run. We validate the outcome instead.
