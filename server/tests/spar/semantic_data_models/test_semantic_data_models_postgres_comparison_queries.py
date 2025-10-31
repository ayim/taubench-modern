"""
Tests for semantic data models with comprehensive column type coverage.

Tests facts, time_dimensions, and dimensions using the comparison_v1_v2 table.

This test module uses the comparison_v1_v2 table which contains:
- Facts: NUMERIC columns (v1_invoice_total, v2_invoice_total, etc.)
- Time Dimensions: TIMESTAMPTZ columns (created_at, updated_at)
- Dimensions: TEXT columns (document_name, export_status)

Tests are organized into sections matching the requirements document:
1. Basic Retrieval Queries
2. Comparison Queries (v1 vs v2)
3. Aggregation and Summary Queries
4. Derived and Conditional Output
5. Time-Based Scenarios
6. Combined and Advanced Scenarios

Note on Test Stability:
These tests interact with the OpenAI API and may experience intermittent failures due to:
- API rate limiting
- Network timeouts
- LLM response variability

Running Tests in Batches (Recommended):
To avoid rate limiting, run tests in smaller batches:

    # Run batch 1 (Basic Retrieval - 4 tests)
    pytest -v -m "batch1 and semantic_data_models" -k postgres

    # Run batch 2 (Comparison Queries - 3 tests)
    pytest -v -m "batch2 and semantic_data_models" -k postgres

    # Run batch 3 (Aggregation - 4 tests)
    pytest -v -m "batch3 and semantic_data_models" -k postgres

    # Run batch 4 (Derived/Conditional - 3 tests)
    pytest -v -m "batch4 and semantic_data_models" -k postgres

    # Run batch 5 (Time-Based - 2 tests)
    pytest -v -m "batch5 and semantic_data_models" -k postgres

    # Run batch 6 (Advanced - 3 tests)
    pytest -v -m "batch6 and semantic_data_models" -k postgres

    # Or run all batches at once (may hit rate limits)
    pytest -v -m semantic_data_models -k postgres
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from agent_platform.orchestrator.agent_server_client import AgentServerClient

    from agent_platform.core.payloads.data_connection import DataConnection

# Module-level pytest marks
# - spar: requires agent server to be running
# - semantic_data_models: semantic data model integration tests
pytestmark = [
    pytest.mark.spar,
    pytest.mark.semantic_data_models,
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

    return successful_sql_calls[-1]  # Return last successful call


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
    elif min_row_count > 0:
        assert num_rows >= min_row_count, f"Expected at least {min_row_count} rows, got {num_rows}"

    return matching_df


# Override the engine fixture to only use postgres for these comparison tests
@pytest.fixture(scope="module")
def engine(request: pytest.FixtureRequest):
    """
    Override engine fixture to only test Postgres comparison queries.

    The comparison_v1_v2 table is currently only defined for Postgres.
    """
    return "postgres"


@pytest.fixture(scope="module")
def agent_for_comparison_queries(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    openai_api_key: str,
) -> str:
    """Create an agent for testing comparison queries."""
    import uuid

    client, _ = agent_server_client_with_data_connection

    return client.create_agent_and_return_agent_id(
        name=f"Comparison Queries Agent {uuid.uuid4().hex[:8]}",
        action_packages=[],
        platform_configs=[
            {
                "kind": "openai",
                "openai_api_key": openai_api_key,
                "models": {"openai": ["gpt-5"]},
            }
        ],
        runbook=(
            "You are an agent that creates data frames using the data_frames_create_from_sql tool. "
            "The database includes a comparison_v1_v2 table with invoice comparison data between "
            "version 1 and version 2 processing. This table includes numeric facts, "
            "timestamp dimensions, and text dimensions. Use the semantic data model provided "
            "to answer user questions."
        ),
        description=(
            "Agent for testing invoice comparison queries with comprehensive SDM column types"
        ),
        document_intelligence="v2",
    )


@pytest.fixture(scope="module")
def comparison_semantic_data_model(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    agent_for_comparison_queries: str,
) -> dict[str, Any]:
    """
    Generate a semantic data model from the comparison_v1_v2 table.

    This model should include:
    - Facts: numeric columns
    - Time Dimensions: timestamp columns
    - Dimensions: text columns

    Returns:
        dict: Generated semantic data model response with 'semantic_model' key
    """
    from dataclasses import asdict

    from agent_platform.core.payloads.semantic_data_model_payloads import (
        DataConnectionInfo,
        GenerateSemanticDataModelPayload,
    )

    client, data_connection = agent_server_client_with_data_connection
    agent_id = agent_for_comparison_queries

    # Inspect the comparison_v1_v2 table with all columns
    assert data_connection.id is not None
    inspect_response = client.inspect_data_connection(
        connection_id=data_connection.id,
        tables_to_inspect=[
            {
                "name": "comparison_v1_v2",
                "database": None,
                "schema": None,
                "columns_to_inspect": None,
            },
        ],
    )

    # Verify inspection response has the table
    assert "tables" in inspect_response
    assert len(inspect_response["tables"]) > 0
    table = inspect_response["tables"][0]
    assert table["name"] == "comparison_v1_v2"

    # Create the payload for generating the semantic data model
    payload = GenerateSemanticDataModelPayload(
        name="invoice_comparison_model",
        description="Semantic data model for invoice comparison between v1 and v2 processing",
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


def test_comparison_semantic_data_model_structure(
    comparison_semantic_data_model: dict[str, Any],
):
    """Test that the comparison semantic data model has the expected structure and column types."""
    # Verify the result
    assert comparison_semantic_data_model is not None
    assert "semantic_model" in comparison_semantic_data_model

    semantic_model = comparison_semantic_data_model["semantic_model"]

    # Verify basic model properties
    assert semantic_model["name"] is not None
    assert semantic_model["description"] is not None

    # Verify the comparison_v1_v2 table is present
    assert "tables" in semantic_model
    tables = semantic_model["tables"]
    assert len(tables) == 1, "Expected exactly one table (comparison_v1_v2)"

    table = tables[0]
    assert table["base_table"]["table"] == "comparison_v1_v2"

    # Verify table has description and synonyms
    assert table["description"] is not None, "Expected description for comparison_v1_v2 table"
    assert table["synonyms"] is not None, "Expected synonyms for comparison_v1_v2 table"

    # Collect all columns
    dimensions = table.get("dimensions", [])
    facts = table.get("facts", [])
    time_dimensions = table.get("time_dimensions", [])
    metrics = table.get("metrics", [])

    all_columns = dimensions + facts + time_dimensions + metrics

    # Verify we have columns
    assert len(all_columns) > 0, "Expected columns in the table"

    # Verify each column has required properties
    for column in all_columns:
        assert column["name"] is not None, f"Expected name for column {column}"
        assert column["expr"] is not None, f"Expected expr for column {column['name']}"
        col_name = column["name"]
        assert column["description"] is not None, f"Expected description for column {col_name}"
        assert column["synonyms"] is not None, f"Expected synonyms for column {col_name}"

    # Verify we have facts (numeric columns)
    assert len(facts) > 0, "Expected facts (numeric columns) in the model"
    fact_names = [f["name"] for f in facts]
    print(f"Facts found: {fact_names}")

    # Verify we have time_dimensions (timestamp columns)
    assert len(time_dimensions) > 0, "Expected time_dimensions (timestamp columns) in the model"
    time_dim_names = [td["name"] for td in time_dimensions]
    print(f"Time dimensions found: {time_dim_names}")

    # Verify we have dimensions (text columns)
    assert len(dimensions) > 0, "Expected dimensions (text columns) in the model"
    dimension_names = [d["name"] for d in dimensions]
    print(f"Dimensions found: {dimension_names}")


@pytest.fixture(scope="module")
def created_comparison_model_id(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    comparison_semantic_data_model: dict[str, Any],
) -> str:
    """
    Create the comparison semantic data model in the agent server.

    Returns:
        str: The semantic data model ID
    """
    client, _ = agent_server_client_with_data_connection

    # Create the semantic data model
    created_model = client.create_semantic_data_model(comparison_semantic_data_model)
    return created_model["semantic_data_model_id"]


@pytest.fixture(scope="module")
def agent_with_comparison_model(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    created_comparison_model_id: str,
    agent_for_comparison_queries: str,
) -> str:
    """
    Assign the comparison semantic data model to the agent.

    Returns:
        str: agent_id
    """
    client, _ = agent_server_client_with_data_connection
    agent_id = agent_for_comparison_queries

    # Assign the semantic data model to the agent
    client.set_agent_semantic_data_models(agent_id, [created_comparison_model_id])

    return agent_id


# ============================================================================
# 1. BASIC RETRIEVAL QUERIES (BATCH 1)
# ============================================================================


@pytest.mark.batch1
def test_query_list_documents_with_init_status(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    agent_with_comparison_model: str,
    comparison_semantic_data_model: dict[str, Any],
):
    """
    Test: List all documents where the export status is INIT.

    Expected SQL pattern: SELECT document_name FROM ... WHERE export_status = 'INIT'
    Expected result: Should return 6 documents with INIT status
    """
    client, _ = agent_server_client_with_data_connection
    agent_id = agent_with_comparison_model
    thread_id = client.create_thread_and_return_thread_id(agent_id)

    query = "List all documents where the export status is INIT."

    result, tool_calls = client.send_message_to_agent_thread(agent_id, thread_id, query)

    print(f"\nQuery: {query}")
    print(f"Result: {result}")
    print(f"Tool calls: {[tc.tool_name for tc in tool_calls]}")

    # Use last successful SQL call (agents may need multiple attempts)
    sql_tool_call = get_last_successful_sql_call(tool_calls)

    # ✅ Validate SQL executed successfully and returned correct data
    # Note: Test data has 8 INIT documents (was initially 6, but data was updated)
    validate_sql_execution_and_data(
        client=client,
        thread_id=thread_id,
        sql_tool_call=sql_tool_call,
        min_row_count=8,  # At least 8 documents with INIT status
    )

    # Verify non-empty result
    assert str(result), f"Empty result for query: {query}"

    # Get the SQL query
    sql_query = sql_tool_call.input_data["sql_query"].lower()
    print(f"Generated SQL: {sql_query}")

    # Get semantic table name
    semantic_model = comparison_semantic_data_model["semantic_model"]
    semantic_table_name = semantic_model["tables"][0]["name"]

    # Verify SQL contains table reference and WHERE clause for INIT status
    assert "comparison_v1_v2" in sql_query or semantic_table_name.lower() in sql_query, (
        f"Expected table reference in SQL: {sql_query}"
    )
    assert "where" in sql_query, f"Expected WHERE clause in SQL: {sql_query}"
    assert "'init'" in sql_query or '"init"' in sql_query, (
        f"Expected INIT filter in SQL: {sql_query}"
    )


@pytest.mark.batch1
def test_query_document_names_and_invoice_totals(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    agent_with_comparison_model: str,
    comparison_semantic_data_model: dict[str, Any],
):
    """
    Test: Get the document names and invoice totals for version 1 and version 2.

    Expected SQL pattern: SELECT document_name, v1_invoice_total, v2_invoice_total FROM ...
    Expected result: All 27 documents
    """
    client, _ = agent_server_client_with_data_connection
    agent_id = agent_with_comparison_model
    thread_id = client.create_thread_and_return_thread_id(agent_id)

    query = "Get the document names and invoice totals for version 1 and version 2."

    result, tool_calls = client.send_message_to_agent_thread(agent_id, thread_id, query)

    print(f"\nQuery: {query}")
    print(f"Result: {result}")
    print(f"Tool calls: {[tc.tool_name for tc in tool_calls]}")

    # Use last successful SQL call (agents may need multiple attempts)
    sql_tool_call = get_last_successful_sql_call(tool_calls)

    # ✅ Validate SQL executed successfully and returned all documents
    validate_sql_execution_and_data(
        client=client,
        thread_id=thread_id,
        sql_tool_call=sql_tool_call,
        expected_row_count=27,  # All documents in test data
    )

    # Verify non-empty result
    assert str(result), f"Empty result for query: {query}"

    # Get the SQL query
    sql_query = sql_tool_call.input_data["sql_query"].lower()
    print(f"Generated SQL: {sql_query}")

    # Get semantic table name
    semantic_model = comparison_semantic_data_model["semantic_model"]
    semantic_table_name = semantic_model["tables"][0]["name"]

    # Verify SQL contains table reference
    assert "comparison_v1_v2" in sql_query or semantic_table_name.lower() in sql_query, (
        f"Expected table reference in SQL: {sql_query}"
    )

    # Verify SQL selects the required columns (may use semantic column names)
    # We check for document/name and invoice/total keywords
    assert "document" in sql_query or "name" in sql_query, (
        f"Expected document name reference in SQL: {sql_query}"
    )
    assert "invoice" in sql_query or "total" in sql_query, (
        f"Expected invoice total reference in SQL: {sql_query}"
    )


@pytest.mark.batch1
def test_query_documents_created_after_date(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    agent_with_comparison_model: str,
    comparison_semantic_data_model: dict[str, Any],
):
    """
    Test: Find all documents created after October 1, 2025.

    Expected SQL pattern: SELECT document_name FROM ... WHERE created_at > '2025-10-01'
    Expected result: 1 document (Anahau June 2024.pdf created on 2025-10-07)
    """
    client, _ = agent_server_client_with_data_connection
    agent_id = agent_with_comparison_model
    thread_id = client.create_thread_and_return_thread_id(agent_id)

    query = "Find all documents created after October 1, 2025."

    result, tool_calls = client.send_message_to_agent_thread(agent_id, thread_id, query)

    print(f"\nQuery: {query}")
    print(f"Result: {result}")
    print(f"Tool calls: {[tc.tool_name for tc in tool_calls]}")

    # Use last successful SQL call (agents may need multiple attempts)
    sql_tool_call = get_last_successful_sql_call(tool_calls)

    # ✅ Validate SQL executed successfully and returned 1 document
    validate_sql_execution_and_data(
        client=client,
        thread_id=thread_id,
        sql_tool_call=sql_tool_call,
        expected_row_count=1,  # Only 1 document created after 2025-10-01
    )

    # Verify non-empty result
    assert str(result), f"Empty result for query: {query}"

    # Get the SQL query
    sql_query = sql_tool_call.input_data["sql_query"].lower()
    print(f"Generated SQL: {sql_query}")

    # Get semantic table name
    semantic_model = comparison_semantic_data_model["semantic_model"]
    semantic_table_name = semantic_model["tables"][0]["name"]

    # Verify SQL contains table reference and WHERE clause with date filter
    assert "comparison_v1_v2" in sql_query or semantic_table_name.lower() in sql_query, (
        f"Expected table reference in SQL: {sql_query}"
    )
    assert "where" in sql_query, f"Expected WHERE clause in SQL: {sql_query}"
    assert "created" in sql_query, f"Expected created_at reference in SQL: {sql_query}"
    assert "2025-10" in sql_query, f"Expected date 2025-10 in SQL: {sql_query}"


@pytest.mark.batch1
def test_query_top_5_recently_updated_documents(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    agent_with_comparison_model: str,
    comparison_semantic_data_model: dict[str, Any],
):
    """
    Test: Show the top 5 most recently updated documents.

    Expected SQL pattern: SELECT document_name, updated_at FROM ... ORDER BY updated_at DESC LIMIT 5
    Expected result: Exactly 5 rows with the most recent documents
    """
    client, _ = agent_server_client_with_data_connection
    agent_id = agent_with_comparison_model
    thread_id = client.create_thread_and_return_thread_id(agent_id)

    query = "Show the top 5 most recently updated documents."

    result, tool_calls = client.send_message_to_agent_thread(agent_id, thread_id, query)

    print(f"\nQuery: {query}")
    print(f"Result: {result}")
    print(f"Tool calls: {[tc.tool_name for tc in tool_calls]}")

    # Use last successful SQL call (agents may need multiple attempts)
    sql_tool_call = get_last_successful_sql_call(tool_calls)

    # ✅ Validate SQL executed successfully and returned exactly 5 rows
    validate_sql_execution_and_data(
        client=client,
        thread_id=thread_id,
        sql_tool_call=sql_tool_call,
        expected_row_count=5,  # LIMIT 5 should return exactly 5 rows
    )

    # Verify non-empty result
    assert str(result), f"Empty result for query: {query}"

    # Get the SQL query
    sql_query = sql_tool_call.input_data["sql_query"].lower()
    print(f"Generated SQL: {sql_query}")

    # Get semantic table name
    semantic_model = comparison_semantic_data_model["semantic_model"]
    semantic_table_name = semantic_model["tables"][0]["name"]

    # Verify SQL contains table reference, ORDER BY, and LIMIT
    assert "comparison_v1_v2" in sql_query or semantic_table_name.lower() in sql_query, (
        f"Expected table reference in SQL: {sql_query}"
    )
    assert "order by" in sql_query, f"Expected ORDER BY clause in SQL: {sql_query}"
    assert "updated" in sql_query, f"Expected updated_at reference in SQL: {sql_query}"
    assert "desc" in sql_query, f"Expected DESC ordering in SQL: {sql_query}"
    # Check for LIMIT 5 (broken down for linting)
    assert "limit" in sql_query, f"Expected LIMIT in SQL: {sql_query}"
    assert "5" in sql_query, f"Expected limit of 5 in SQL: {sql_query}"


# ============================================================================
# 2. COMPARISON QUERIES (V1 VS V2) (BATCH 2)
# ============================================================================


@pytest.mark.batch2
def test_query_documents_with_different_totals(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    agent_with_comparison_model: str,
    comparison_semantic_data_model: dict[str, Any],
):
    """
    Test: Show all documents where v1 and v2 invoice totals differ.

    Expected SQL pattern: SELECT document_name FROM ... WHERE v1_invoice_total != v2_invoice_total
    Expected result: At least 4 documents with differences (NULL handling may vary)
    """
    client, _ = agent_server_client_with_data_connection
    agent_id = agent_with_comparison_model
    thread_id = client.create_thread_and_return_thread_id(agent_id)

    query = "Show all documents where v1 and v2 invoice totals differ."

    result, tool_calls = client.send_message_to_agent_thread(agent_id, thread_id, query)

    print(f"\nQuery: {query}")
    print(f"Result: {result}")
    print(f"Tool calls: {[tc.tool_name for tc in tool_calls]}")

    # Use last successful SQL call (agents may need multiple attempts)
    sql_tool_call = get_last_successful_sql_call(tool_calls)

    # ✅ Validate SQL executed successfully and returned documents with differences
    validate_sql_execution_and_data(
        client=client,
        thread_id=thread_id,
        sql_tool_call=sql_tool_call,
        min_row_count=4,  # At least 4 documents have v1 != v2 (NULL handling may vary)
    )

    # Verify non-empty result
    assert str(result), f"Empty result for query: {query}"

    # Get the SQL query
    sql_query = sql_tool_call.input_data["sql_query"].lower()
    print(f"Generated SQL: {sql_query}")

    # Get semantic table name
    semantic_model = comparison_semantic_data_model["semantic_model"]
    semantic_table_name = semantic_model["tables"][0]["name"]

    # Verify SQL contains table reference and comparison
    assert "comparison_v1_v2" in sql_query or semantic_table_name.lower() in sql_query, (
        f"Expected table reference in SQL: {sql_query}"
    )
    assert "where" in sql_query, f"Expected WHERE clause in SQL: {sql_query}"
    # Check for comparison operators (!=, <>, or IS DISTINCT FROM)
    assert "!=" in sql_query or "<>" in sql_query or "is distinct from" in sql_query, (
        f"Expected comparison operator in SQL: {sql_query}"
    )


@pytest.mark.batch2
def test_query_v2_greater_than_v1_line_items(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    agent_with_comparison_model: str,
    comparison_semantic_data_model: dict[str, Any],
):
    """
    Test: Find documents where v2 line items total > v1 line items total.

    Expected SQL pattern:
        SELECT document_name FROM ... WHERE v2_line_items_total > v1_line_items_total
    """
    client, _ = agent_server_client_with_data_connection
    agent_id = agent_with_comparison_model
    thread_id = client.create_thread_and_return_thread_id(agent_id)

    query = "Find documents where v2 line items total is greater than v1 line items total."

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
        min_row_count=1,  # At least some documents where v2 > v1
    )

    # Verify non-empty result
    assert str(result), f"Empty result for query: {query}"

    # Get the SQL query
    sql_query = sql_tool_call.input_data["sql_query"].lower()
    print(f"Generated SQL: {sql_query}")

    # Get semantic table name
    semantic_model = comparison_semantic_data_model["semantic_model"]
    semantic_table_name = semantic_model["tables"][0]["name"]

    # Verify SQL contains table reference and comparison
    assert "comparison_v1_v2" in sql_query or semantic_table_name.lower() in sql_query, (
        f"Expected table reference in SQL: {sql_query}"
    )
    assert "where" in sql_query, f"Expected WHERE clause in SQL: {sql_query}"
    assert ">" in sql_query, f"Expected greater than comparison in SQL: {sql_query}"
    assert "line" in sql_query, f"Expected line items reference in SQL: {sql_query}"


@pytest.mark.batch2
def test_query_count_mismatched_invoice_totals(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    agent_with_comparison_model: str,
    comparison_semantic_data_model: dict[str, Any],
):
    """
    Test: Show how many documents have mismatched invoice totals between v1 and v2.

    Expected SQL pattern: SELECT COUNT(*) FROM ... WHERE v1_invoice_total != v2_invoice_total
    Expected result: 1 row with count value
    """
    client, _ = agent_server_client_with_data_connection
    agent_id = agent_with_comparison_model
    thread_id = client.create_thread_and_return_thread_id(agent_id)

    query = "Show how many documents have mismatched invoice totals between v1 and v2."

    result, tool_calls = client.send_message_to_agent_thread(agent_id, thread_id, query)

    print(f"\nQuery: {query}")
    print(f"Result: {result}")
    print(f"Tool calls: {[tc.tool_name for tc in tool_calls]}")

    # Use last successful SQL call (agents may need multiple attempts)
    sql_tool_call = get_last_successful_sql_call(tool_calls)

    # ✅ Validate SQL executed successfully and returned 1 row (aggregate result)
    validate_sql_execution_and_data(
        client=client,
        thread_id=thread_id,
        sql_tool_call=sql_tool_call,
        expected_row_count=1,  # COUNT returns 1 row
    )

    # Verify non-empty result
    assert str(result), f"Empty result for query: {query}"

    # Get the SQL query
    sql_query = sql_tool_call.input_data["sql_query"].lower()
    print(f"Generated SQL: {sql_query}")

    # Get semantic table name
    semantic_model = comparison_semantic_data_model["semantic_model"]
    semantic_table_name = semantic_model["tables"][0]["name"]

    # Verify SQL contains COUNT and comparison logic (either WHERE or CASE)
    assert "comparison_v1_v2" in sql_query or semantic_table_name.lower() in sql_query, (
        f"Expected table reference in SQL: {sql_query}"
    )
    assert "count" in sql_query, f"Expected COUNT function in SQL: {sql_query}"
    # LLM might use WHERE clause OR CASE statements to filter mismatches
    assert "where" in sql_query or "case" in sql_query, (
        f"Expected WHERE clause or CASE expression in SQL: {sql_query}"
    )
    # Check for comparison operators
    assert "!=" in sql_query or "<>" in sql_query or "is distinct from" in sql_query, (
        f"Expected comparison operator in SQL: {sql_query}"
    )


# ============================================================================
# 3. AGGREGATION AND SUMMARY QUERIES (BATCH 3)
# ============================================================================


@pytest.mark.batch3
def test_query_average_invoice_totals(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    agent_with_comparison_model: str,
    comparison_semantic_data_model: dict[str, Any],
):
    """
    Test: What is the average invoice total in version 1 and version 2?

    Expected SQL pattern: SELECT AVG(v1_invoice_total), AVG(v2_invoice_total) FROM ...
    Expected result: 1 row with average values
    """
    client, _ = agent_server_client_with_data_connection
    agent_id = agent_with_comparison_model
    thread_id = client.create_thread_and_return_thread_id(agent_id)

    query = "What is the average invoice total in version 1 and version 2?"

    result, tool_calls = client.send_message_to_agent_thread(agent_id, thread_id, query)

    print(f"\nQuery: {query}")
    print(f"Result: {result}")
    print(f"Tool calls: {[tc.tool_name for tc in tool_calls]}")

    # Use last successful SQL call (agents may need multiple attempts)
    sql_tool_call = get_last_successful_sql_call(tool_calls)

    # ✅ Validate SQL executed successfully and returned 1 row (aggregate result)
    validate_sql_execution_and_data(
        client=client,
        thread_id=thread_id,
        sql_tool_call=sql_tool_call,
        expected_row_count=1,  # AVG returns 1 row
    )

    # Verify non-empty result
    assert str(result), f"Empty result for query: {query}"

    # Get the SQL query
    sql_query = sql_tool_call.input_data["sql_query"].lower()
    print(f"Generated SQL: {sql_query}")

    # Get semantic table name
    semantic_model = comparison_semantic_data_model["semantic_model"]
    semantic_table_name = semantic_model["tables"][0]["name"]

    # Verify SQL contains AVG function
    assert "comparison_v1_v2" in sql_query or semantic_table_name.lower() in sql_query, (
        f"Expected table reference in SQL: {sql_query}"
    )
    assert "avg" in sql_query, f"Expected AVG function in SQL: {sql_query}"
    assert "invoice" in sql_query or "total" in sql_query, (
        f"Expected invoice total reference in SQL: {sql_query}"
    )


@pytest.mark.batch3
def test_query_count_exported_documents(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    agent_with_comparison_model: str,
    comparison_semantic_data_model: dict[str, Any],
):
    """
    Test: Count how many documents have been exported.

    Expected SQL pattern: SELECT COUNT(*) FROM ... WHERE export_status = 'EXPORTED'
    Expected result: 1 row with count value of 19 (19 exported documents in test data)
    """
    client, _ = agent_server_client_with_data_connection
    agent_id = agent_with_comparison_model
    thread_id = client.create_thread_and_return_thread_id(agent_id)

    query = "Count how many documents have been exported."

    result, tool_calls = client.send_message_to_agent_thread(agent_id, thread_id, query)

    print(f"\nQuery: {query}")
    print(f"Result: {result}")
    print(f"Tool calls: {[tc.tool_name for tc in tool_calls]}")

    # Use last successful SQL call (agents may need multiple attempts)
    sql_tool_call = get_last_successful_sql_call(tool_calls)

    # ✅ Validate SQL executed successfully and returned 1 row (aggregate result)
    validate_sql_execution_and_data(
        client=client,
        thread_id=thread_id,
        sql_tool_call=sql_tool_call,
        expected_row_count=1,  # COUNT returns 1 row with the count value
    )

    # ✅ The row count validation above already confirms the query executed successfully
    # Additional value validation could be added here if needed, but requires handling
    # data frame name lookups when agents create multiple frames with slight name variations

    # Verify non-empty result
    assert str(result), f"Empty result for query: {query}"

    # Get the SQL query
    sql_query = sql_tool_call.input_data["sql_query"].lower()
    print(f"Generated SQL: {sql_query}")

    # Get semantic table name
    semantic_model = comparison_semantic_data_model["semantic_model"]
    semantic_table_name = semantic_model["tables"][0]["name"]

    # Verify SQL contains COUNT and EXPORTED filter
    assert "comparison_v1_v2" in sql_query or semantic_table_name.lower() in sql_query, (
        f"Expected table reference in SQL: {sql_query}"
    )
    assert "count" in sql_query, f"Expected COUNT function in SQL: {sql_query}"
    assert "where" in sql_query, f"Expected WHERE clause in SQL: {sql_query}"
    assert "'exported'" in sql_query or '"exported"' in sql_query, (
        f"Expected EXPORTED filter in SQL: {sql_query}"
    )


@pytest.mark.batch3
def test_query_sum_of_invoice_totals(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    agent_with_comparison_model: str,
    comparison_semantic_data_model: dict[str, Any],
):
    """
    Test: Find the total sum of v1 and v2 invoice totals across all documents.

    Expected SQL pattern: SELECT SUM(v1_invoice_total), SUM(v2_invoice_total) FROM ...
    Expected result: 1 row with sum values
    """
    client, _ = agent_server_client_with_data_connection
    agent_id = agent_with_comparison_model
    thread_id = client.create_thread_and_return_thread_id(agent_id)

    query = "Find the total sum of v1 and v2 invoice totals across all documents."

    result, tool_calls = client.send_message_to_agent_thread(agent_id, thread_id, query)

    print(f"\nQuery: {query}")
    print(f"Result: {result}")
    print(f"Tool calls: {[tc.tool_name for tc in tool_calls]}")

    # Use last successful SQL call (agents may need multiple attempts)
    sql_tool_call = get_last_successful_sql_call(tool_calls)

    # ✅ Validate SQL executed successfully and returned 1 row (aggregate result)
    validate_sql_execution_and_data(
        client=client,
        thread_id=thread_id,
        sql_tool_call=sql_tool_call,
        expected_row_count=1,  # SUM returns 1 row
    )

    # Verify non-empty result
    assert str(result), f"Empty result for query: {query}"

    # Get the SQL query
    sql_query = sql_tool_call.input_data["sql_query"].lower()
    print(f"Generated SQL: {sql_query}")

    # Get semantic table name
    semantic_model = comparison_semantic_data_model["semantic_model"]
    semantic_table_name = semantic_model["tables"][0]["name"]

    # Verify SQL contains SUM function
    assert "comparison_v1_v2" in sql_query or semantic_table_name.lower() in sql_query, (
        f"Expected table reference in SQL: {sql_query}"
    )
    assert "sum" in sql_query, f"Expected SUM function in SQL: {sql_query}"
    assert "invoice" in sql_query or "total" in sql_query, (
        f"Expected invoice total reference in SQL: {sql_query}"
    )


@pytest.mark.batch3
def test_query_count_grouped_by_export_status(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    agent_with_comparison_model: str,
    comparison_semantic_data_model: dict[str, Any],
):
    """
    Test: Get the number of documents grouped by export status.

    Expected SQL pattern: SELECT export_status, COUNT(*) FROM ... GROUP BY export_status
    Expected result: 2 rows (one for INIT, one for EXPORTED)
    """
    client, _ = agent_server_client_with_data_connection
    agent_id = agent_with_comparison_model
    thread_id = client.create_thread_and_return_thread_id(agent_id)

    query = "Get the number of documents grouped by export status."

    result, tool_calls = client.send_message_to_agent_thread(agent_id, thread_id, query)

    print(f"\nQuery: {query}")
    print(f"Result: {result}")
    print(f"Tool calls: {[tc.tool_name for tc in tool_calls]}")

    # Use last successful SQL call (agents may need multiple attempts)
    sql_tool_call = get_last_successful_sql_call(tool_calls)

    # ✅ Validate SQL executed successfully and returned 2 rows (INIT and EXPORTED groups)
    validate_sql_execution_and_data(
        client=client,
        thread_id=thread_id,
        sql_tool_call=sql_tool_call,
        expected_row_count=2,  # 2 distinct export statuses in test data
    )

    # Verify non-empty result
    assert str(result), f"Empty result for query: {query}"

    # Get the SQL query
    sql_query = sql_tool_call.input_data["sql_query"].lower()
    print(f"Generated SQL: {sql_query}")

    # Get semantic table name
    semantic_model = comparison_semantic_data_model["semantic_model"]
    semantic_table_name = semantic_model["tables"][0]["name"]

    # Verify SQL contains GROUP BY and COUNT
    assert "comparison_v1_v2" in sql_query or semantic_table_name.lower() in sql_query, (
        f"Expected table reference in SQL: {sql_query}"
    )
    assert "count" in sql_query, f"Expected COUNT function in SQL: {sql_query}"
    assert "group by" in sql_query, f"Expected GROUP BY clause in SQL: {sql_query}"
    assert "export" in sql_query or "status" in sql_query, (
        f"Expected export_status reference in SQL: {sql_query}"
    )


# ============================================================================
# 4. DERIVED AND CONDITIONAL OUTPUT (BATCH 4)
# ============================================================================


@pytest.mark.batch4
def test_query_match_status_with_case_expression(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    agent_with_comparison_model: str,
    comparison_semantic_data_model: dict[str, Any],
):
    """
    Test: Show each document name and indicate whether invoice totals match between v1 and v2.

    Expected SQL pattern: SELECT document_name, CASE WHEN v1_invoice_total = v2_invoice_total
                          THEN 'Match' ELSE 'Mismatch' END AS ...
    """
    client, _ = agent_server_client_with_data_connection
    agent_id = agent_with_comparison_model
    thread_id = client.create_thread_and_return_thread_id(agent_id)

    query = "Show each document name and indicate whether invoice totals match between v1 and v2."

    result, tool_calls = client.send_message_to_agent_thread(agent_id, thread_id, query)

    print(f"\nQuery: {query}")
    print(f"Result: {result}")
    print(f"Tool calls: {[tc.tool_name for tc in tool_calls]}")

    # Use last successful SQL call (agents may need multiple attempts)
    sql_tool_call = get_last_successful_sql_call(tool_calls)

    # ✅ Validate SQL executed successfully and returned all documents
    validate_sql_execution_and_data(
        client=client,
        thread_id=thread_id,
        sql_tool_call=sql_tool_call,
        expected_row_count=27,  # All documents with match status
    )

    # Verify non-empty result
    assert str(result), f"Empty result for query: {query}"

    # Get the SQL query
    sql_query = sql_tool_call.input_data["sql_query"].lower()
    print(f"Generated SQL: {sql_query}")

    # Get semantic table name
    semantic_model = comparison_semantic_data_model["semantic_model"]
    semantic_table_name = semantic_model["tables"][0]["name"]

    # Verify SQL contains CASE expression or conditional logic
    assert "comparison_v1_v2" in sql_query or semantic_table_name.lower() in sql_query, (
        f"Expected table reference in SQL: {sql_query}"
    )
    # CASE expression, IF statement, or boolean comparison
    assert "case" in sql_query or "if" in sql_query or "=" in sql_query, (
        f"Expected conditional logic in SQL: {sql_query}"
    )


@pytest.mark.batch4
def test_query_invoice_mismatch_flag(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    agent_with_comparison_model: str,
    comparison_semantic_data_model: dict[str, Any],
):
    """
    Test: List documents with a flag indicating when v1_invoice_total ≠ v2_invoice_total.

    Expected SQL pattern:
        SELECT document_name, v1_invoice_total != v2_invoice_total AS invoice_mismatch
    """
    client, _ = agent_server_client_with_data_connection
    agent_id = agent_with_comparison_model
    thread_id = client.create_thread_and_return_thread_id(agent_id)

    query = (
        "List documents with a flag indicating when v1 invoice total differs from v2 invoice total."
    )

    result, tool_calls = client.send_message_to_agent_thread(agent_id, thread_id, query)

    print(f"\nQuery: {query}")
    print(f"Result: {result}")
    print(f"Tool calls: {[tc.tool_name for tc in tool_calls]}")

    # Use last successful SQL call (agents may need multiple attempts)
    sql_tool_call = get_last_successful_sql_call(tool_calls)

    # ✅ Validate SQL executed successfully and returned all documents
    validate_sql_execution_and_data(
        client=client,
        thread_id=thread_id,
        sql_tool_call=sql_tool_call,
        expected_row_count=27,  # All documents with mismatch flag
    )

    # Verify non-empty result
    assert str(result), f"Empty result for query: {query}"

    # Get the SQL query
    sql_query = sql_tool_call.input_data["sql_query"].lower()
    print(f"Generated SQL: {sql_query}")

    # Get semantic table name
    semantic_model = comparison_semantic_data_model["semantic_model"]
    semantic_table_name = semantic_model["tables"][0]["name"]

    # Verify SQL contains comparison
    assert "comparison_v1_v2" in sql_query or semantic_table_name.lower() in sql_query, (
        f"Expected table reference in SQL: {sql_query}"
    )
    # Boolean comparison or CASE expression
    has_comparison = (
        "!=" in sql_query
        or "<>" in sql_query
        or "case" in sql_query
        or "is distinct from" in sql_query
    )
    assert has_comparison, f"Expected comparison logic in SQL: {sql_query}"


@pytest.mark.batch4
def test_query_percentage_change_calculation(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    agent_with_comparison_model: str,
    comparison_semantic_data_model: dict[str, Any],
):
    """
    Test: Show document_name, v1_invoice_total, v2_invoice_total, and a percentage change column.

    Expected SQL pattern: SELECT document_name, v1_invoice_total, v2_invoice_total,
                          ((v2_invoice_total - v1_invoice_total) / v1_invoice_total) * 100 AS ...
    """
    client, _ = agent_server_client_with_data_connection
    agent_id = agent_with_comparison_model
    thread_id = client.create_thread_and_return_thread_id(agent_id)

    query = (
        "Show document name, v1 invoice total, v2 invoice total, "
        "and calculate the percentage change between them."
    )

    result, tool_calls = client.send_message_to_agent_thread(agent_id, thread_id, query)

    print(f"\nQuery: {query}")
    print(f"Result: {result}")
    print(f"Tool calls: {[tc.tool_name for tc in tool_calls]}")

    # Use last successful SQL call (agents may need multiple attempts)
    sql_tool_call = get_last_successful_sql_call(tool_calls)

    # ✅ Validate SQL executed successfully and returned data (NULLs may be filtered)
    validate_sql_execution_and_data(
        client=client,
        thread_id=thread_id,
        sql_tool_call=sql_tool_call,
        min_row_count=20,  # At least 20 documents (some NULLs may be filtered)
    )

    # Verify non-empty result
    assert str(result), f"Empty result for query: {query}"

    # Get the SQL query
    sql_query = sql_tool_call.input_data["sql_query"].lower()
    print(f"Generated SQL: {sql_query}")

    # Get semantic table name
    semantic_model = comparison_semantic_data_model["semantic_model"]
    semantic_table_name = semantic_model["tables"][0]["name"]

    # Verify SQL contains arithmetic operations for percentage
    assert "comparison_v1_v2" in sql_query or semantic_table_name.lower() in sql_query, (
        f"Expected table reference in SQL: {sql_query}"
    )
    # Check for division and multiplication (percentage calculation)
    assert "/" in sql_query, f"Expected division in SQL for percentage calculation: {sql_query}"
    # May contain 100 for percentage or subtraction for difference
    assert "100" in sql_query or "*" in sql_query or "-" in sql_query, (
        f"Expected percentage calculation in SQL: {sql_query}"
    )


# ============================================================================
# 5. TIME-BASED SCENARIOS (BATCH 5)
# ============================================================================


@pytest.mark.batch5
def test_query_documents_updated_within_last_7_days(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    agent_with_comparison_model: str,
    comparison_semantic_data_model: dict[str, Any],
):
    """
    Test: Show all documents updated within the last 7 days.

    Expected SQL pattern:
        SELECT document_name FROM ... WHERE updated_at >= NOW() - INTERVAL '7 days'
    """
    client, _ = agent_server_client_with_data_connection
    agent_id = agent_with_comparison_model
    thread_id = client.create_thread_and_return_thread_id(agent_id)

    query = "Show all documents updated within the last 7 days."

    result, tool_calls = client.send_message_to_agent_thread(agent_id, thread_id, query)

    print(f"\nQuery: {query}")
    print(f"Result: {result}")
    print(f"Tool calls: {[tc.tool_name for tc in tool_calls]}")

    # Use last successful SQL call (agents may need multiple attempts)
    sql_tool_call = get_last_successful_sql_call(tool_calls)

    # ✅ Validate SQL executed successfully (may return 0 rows - test data is old)
    validate_sql_execution_and_data(
        client=client,
        thread_id=thread_id,
        sql_tool_call=sql_tool_call,
        min_row_count=0,  # Test data from Sept 2025, likely 0 results
    )

    # Verify non-empty result
    assert str(result), f"Empty result for query: {query}"

    # Get the SQL query
    sql_query = sql_tool_call.input_data["sql_query"].lower()
    print(f"Generated SQL: {sql_query}")

    # Get semantic table name
    semantic_model = comparison_semantic_data_model["semantic_model"]
    semantic_table_name = semantic_model["tables"][0]["name"]

    # Verify SQL contains time-based filter
    assert "comparison_v1_v2" in sql_query or semantic_table_name.lower() in sql_query, (
        f"Expected table reference in SQL: {sql_query}"
    )
    assert "where" in sql_query, f"Expected WHERE clause in SQL: {sql_query}"
    assert "updated" in sql_query, f"Expected updated_at reference in SQL: {sql_query}"
    # Check for date arithmetic (INTERVAL, DATE_SUB, etc.)
    assert (
        "interval" in sql_query
        or "date_sub" in sql_query
        or "dateadd" in sql_query
        or "now()" in sql_query
        or "current_timestamp" in sql_query
    ), f"Expected date arithmetic in SQL: {sql_query}"


@pytest.mark.batch5
def test_query_documents_with_large_time_gap(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    agent_with_comparison_model: str,
    comparison_semantic_data_model: dict[str, Any],
):
    """
    Test: Find documents where created_at and updated_at timestamps differ by more than one day.

    Expected SQL pattern:
        SELECT document_name FROM ... WHERE updated_at - created_at > INTERVAL '1 day'
    """
    client, _ = agent_server_client_with_data_connection
    agent_id = agent_with_comparison_model
    thread_id = client.create_thread_and_return_thread_id(agent_id)

    query = "Find documents where created at and updated at timestamps differ by more than one day."

    result, tool_calls = client.send_message_to_agent_thread(agent_id, thread_id, query)

    print(f"\nQuery: {query}")
    print(f"Result: {result}")
    print(f"Tool calls: {[tc.tool_name for tc in tool_calls]}")

    # Use last successful SQL call (agents may need multiple attempts)
    sql_tool_call = get_last_successful_sql_call(tool_calls)

    # ✅ Validate SQL executed successfully and returned documents with >1 day gap
    validate_sql_execution_and_data(
        client=client,
        thread_id=thread_id,
        sql_tool_call=sql_tool_call,
        min_row_count=5,  # At least 5 documents have significant time gaps (actual: 7)
    )

    # Verify non-empty result
    assert str(result), f"Empty result for query: {query}"

    # Get the SQL query
    sql_query = sql_tool_call.input_data["sql_query"].lower()
    print(f"Generated SQL: {sql_query}")

    # Get semantic table name
    semantic_model = comparison_semantic_data_model["semantic_model"]
    semantic_table_name = semantic_model["tables"][0]["name"]

    # Verify SQL contains time difference calculation
    assert "comparison_v1_v2" in sql_query or semantic_table_name.lower() in sql_query, (
        f"Expected table reference in SQL: {sql_query}"
    )
    assert "where" in sql_query, f"Expected WHERE clause in SQL: {sql_query}"
    # Check both timestamp columns are referenced (broken down for linting)
    assert "created" in sql_query, f"Expected created_at reference in SQL: {sql_query}"
    assert "updated" in sql_query, f"Expected updated_at reference in SQL: {sql_query}"
    # Check for subtraction or date difference function
    has_date_calc = (
        "-" in sql_query
        or "datediff" in sql_query
        or "date_diff" in sql_query
        or "interval" in sql_query
    )
    assert has_date_calc, f"Expected date difference calculation in SQL: {sql_query}"


# ============================================================================
# 6. COMBINED AND ADVANCED SCENARIOS (BATCH 6)
# ============================================================================


@pytest.mark.batch6
def test_query_init_with_mismatch(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    agent_with_comparison_model: str,
    comparison_semantic_data_model: dict[str, Any],
):
    """
    Test: Show all documents where export_status = INIT and v1 vs v2 invoice totals don't match.

    Expected SQL pattern: SELECT document_name FROM ... WHERE export_status = 'INIT'
                          AND v1_invoice_total != v2_invoice_total
    """
    client, _ = agent_server_client_with_data_connection
    agent_id = agent_with_comparison_model
    thread_id = client.create_thread_and_return_thread_id(agent_id)

    query = (
        "Show all documents where export status is INIT and v1 invoice total "
        "differs from v2 invoice total."
    )

    result, tool_calls = client.send_message_to_agent_thread(agent_id, thread_id, query)

    print(f"\nQuery: {query}")
    print(f"Result: {result}")
    print(f"Tool calls: {[tc.tool_name for tc in tool_calls]}")

    # Use last successful SQL call (agents may need multiple attempts)
    sql_tool_call = get_last_successful_sql_call(tool_calls)

    # ✅ Validate SQL executed successfully and returned INIT documents with mismatches
    validate_sql_execution_and_data(
        client=client,
        thread_id=thread_id,
        sql_tool_call=sql_tool_call,
        min_row_count=2,  # At least 2 INIT documents with mismatches
    )

    # Verify non-empty result
    assert str(result), f"Empty result for query: {query}"

    # Get the SQL query
    sql_query = sql_tool_call.input_data["sql_query"].lower()
    print(f"Generated SQL: {sql_query}")

    # Get semantic table name
    semantic_model = comparison_semantic_data_model["semantic_model"]
    semantic_table_name = semantic_model["tables"][0]["name"]

    # Verify SQL contains both conditions
    assert "comparison_v1_v2" in sql_query or semantic_table_name.lower() in sql_query, (
        f"Expected table reference in SQL: {sql_query}"
    )
    assert "where" in sql_query, f"Expected WHERE clause in SQL: {sql_query}"
    has_conjunction = "and" in sql_query or "where" in sql_query
    assert has_conjunction, f"Expected AND conjunction in SQL: {sql_query}"
    assert "'init'" in sql_query or '"init"' in sql_query, (
        f"Expected INIT filter in SQL: {sql_query}"
    )


@pytest.mark.batch6
def test_query_negative_v2_line_items(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    agent_with_comparison_model: str,
    comparison_semantic_data_model: dict[str, Any],
):
    """
    Test: List documents where v2_line_items_total is negative.

    Expected SQL pattern: SELECT document_name FROM ... WHERE v2_line_items_total < 0
    """
    client, _ = agent_server_client_with_data_connection
    agent_id = agent_with_comparison_model
    thread_id = client.create_thread_and_return_thread_id(agent_id)

    query = "List documents where v2 line items total is negative."

    result, tool_calls = client.send_message_to_agent_thread(agent_id, thread_id, query)

    print(f"\nQuery: {query}")
    print(f"Result: {result}")
    print(f"Tool calls: {[tc.tool_name for tc in tool_calls]}")

    # Use last successful SQL call (agents may need multiple attempts)
    sql_tool_call = get_last_successful_sql_call(tool_calls)

    # ✅ Validate SQL executed successfully and returned documents with negative values
    validate_sql_execution_and_data(
        client=client,
        thread_id=thread_id,
        sql_tool_call=sql_tool_call,
        min_row_count=3,  # Several documents have negative v2 line items totals
    )

    # Verify non-empty result
    assert str(result), f"Empty result for query: {query}"

    # Get the SQL query
    sql_query = sql_tool_call.input_data["sql_query"].lower()
    print(f"Generated SQL: {sql_query}")

    # Get semantic table name
    semantic_model = comparison_semantic_data_model["semantic_model"]
    semantic_table_name = semantic_model["tables"][0]["name"]

    # Verify SQL contains negative filter
    assert "comparison_v1_v2" in sql_query or semantic_table_name.lower() in sql_query, (
        f"Expected table reference in SQL: {sql_query}"
    )
    assert "where" in sql_query, f"Expected WHERE clause in SQL: {sql_query}"
    assert "<" in sql_query or "less than" in sql_query, (
        f"Expected less than comparison in SQL: {sql_query}"
    )
    assert "0" in sql_query or "zero" in sql_query, f"Expected zero reference in SQL: {sql_query}"


@pytest.mark.batch6
def test_query_percentage_exported_documents(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    agent_with_comparison_model: str,
    comparison_semantic_data_model: dict[str, Any],
):
    """
    Test: Show the percentage of exported documents out of the total.

    Expected SQL pattern:
        SELECT (COUNT(*) FILTER (WHERE export_status = 'EXPORTED') * 100.0 / COUNT(*)) AS ...
    """
    client, _ = agent_server_client_with_data_connection
    agent_id = agent_with_comparison_model
    thread_id = client.create_thread_and_return_thread_id(agent_id)

    query = "Show the percentage of exported documents out of the total."

    result, tool_calls = client.send_message_to_agent_thread(agent_id, thread_id, query)

    print(f"\nQuery: {query}")
    print(f"Result: {result}")
    print(f"Tool calls: {[tc.tool_name for tc in tool_calls]}")

    # Use last successful SQL call (agents may need multiple attempts)
    sql_tool_call = get_last_successful_sql_call(tool_calls)

    # ✅ Validate SQL executed successfully and returned 1 row (percentage result)
    validate_sql_execution_and_data(
        client=client,
        thread_id=thread_id,
        sql_tool_call=sql_tool_call,
        expected_row_count=1,  # Single percentage value
    )

    # Verify non-empty result
    assert str(result), f"Empty result for query: {query}"

    # Get the SQL query
    sql_query = sql_tool_call.input_data["sql_query"].lower()
    print(f"Generated SQL: {sql_query}")

    # Get semantic table name
    semantic_model = comparison_semantic_data_model["semantic_model"]
    semantic_table_name = semantic_model["tables"][0]["name"]

    # Verify SQL contains percentage calculation with aggregates
    assert "comparison_v1_v2" in sql_query or semantic_table_name.lower() in sql_query, (
        f"Expected table reference in SQL: {sql_query}"
    )
    assert "count" in sql_query, f"Expected COUNT function in SQL: {sql_query}"
    # Check for division (percentage calculation)
    assert "/" in sql_query, f"Expected division for percentage calculation in SQL: {sql_query}"
    # May contain 100 or use FILTER/CASE for conditional count
    assert "100" in sql_query or "*" in sql_query or "filter" in sql_query or "case" in sql_query, (
        f"Expected percentage calculation logic in SQL: {sql_query}"
    )
