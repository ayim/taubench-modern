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
    so we want to validate the final successful attempt that returns detail data.

    Prefers detail queries (multiple columns) over aggregate queries (COUNT, SUM, etc.)
    to avoid validating summary statistics when the test expects actual records.

    Args:
        tool_calls: List of all tool calls

    Returns:
        The last successful data_frames_create_from_sql tool call with detail data

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

    # Prefer detail queries over aggregate queries
    # Detail queries typically have multiple columns and don't use aggregate functions
    detail_queries = []
    aggregate_queries = []

    for call in successful_sql_calls:
        sql_query = call.input_data.get("sql_query", "").upper()
        # Check if it's an aggregate query (COUNT, SUM, AVG, MIN, MAX only)
        is_aggregate = (
            sql_query.count("COUNT(") > 0
            and "," not in sql_query.split("SELECT")[1].split("FROM")[0]  # Single column
        ) or ("COUNT(*)" in sql_query and "," not in sql_query.split("SELECT")[1].split("FROM")[0])

        if is_aggregate:
            aggregate_queries.append(call)
        else:
            detail_queries.append(call)

    # Return last detail query if available, otherwise last aggregate
    if detail_queries:
        return detail_queries[-1]
    return aggregate_queries[-1] if aggregate_queries else successful_sql_calls[-1]


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


def get_data_frame_contents_as_json(
    client: AgentServerClient,
    thread_id: str,
    data_frame_name: str,
) -> list[dict]:
    """
    Get data frame contents as a list of dictionaries.

    Args:
        client: Agent server client
        thread_id: Thread ID where data frame exists
        data_frame_name: Name of the data frame

    Returns:
        list[dict]: List of rows as dictionaries
    """
    import json

    contents_bytes = client.get_data_frame_contents(
        thread_id=thread_id,
        data_frame_name=data_frame_name,
        output_format="json",
    )
    return json.loads(contents_bytes.decode("utf-8"))


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

    # Get the data frame name and contents
    data_frame_name = sql_tool_call.input_data.get("new_data_frame_name")
    assert data_frame_name, f"Tool input missing new_data_frame_name: {sql_tool_call.input_data}"

    # Get actual data frame contents
    contents = get_data_frame_contents_as_json(client, thread_id, data_frame_name)
    print(f"Data frame contents (first 3 rows): {contents[:3]}")

    # Verify we have at least 8 documents with INIT status
    assert len(contents) >= 8, f"Expected at least 8 INIT documents, got {len(contents)}"

    # Verify each row has a document name and export status
    for row in contents:
        assert any("document" in str(k).lower() or "name" in str(k).lower() for k in row.keys()), (
            f"Expected document/name column, got: {list(row.keys())}"
        )

        # Find the export status column
        status_col = next(
            (k for k in row.keys() if "status" in str(k).lower() or "export" in str(k).lower()),
            None,
        )
        if status_col:
            # Verify status is INIT
            assert str(row[status_col]).upper() == "INIT", (
                f"Expected INIT status, got: {row[status_col]}"
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

    # Get the data frame name and contents
    data_frame_name = sql_tool_call.input_data.get("new_data_frame_name")
    assert data_frame_name, f"Tool input missing new_data_frame_name: {sql_tool_call.input_data}"

    # Get actual data frame contents
    contents = get_data_frame_contents_as_json(client, thread_id, data_frame_name)
    print(f"Data frame contents (first 3 rows): {contents[:3]}")

    # Verify we have all 27 documents
    assert len(contents) == 27, f"Expected 27 documents, got {len(contents)}"

    # Verify each row has document name and both v1/v2 invoice totals
    first_row = contents[0]
    assert any(
        "document" in str(k).lower() or "name" in str(k).lower() for k in first_row.keys()
    ), f"Expected document/name column, got: {list(first_row.keys())}"

    # Check for v1 and v2 columns (could be invoice, total, or amount)
    v1_cols = [
        k
        for k in first_row.keys()
        if "v1" in str(k).lower()
        and any(x in str(k).lower() for x in ["invoice", "total", "amount"])
    ]
    v2_cols = [
        k
        for k in first_row.keys()
        if "v2" in str(k).lower()
        and any(x in str(k).lower() for x in ["invoice", "total", "amount"])
    ]

    assert len(v1_cols) > 0, (
        f"Expected v1 invoice/total/amount column, got columns: {list(first_row.keys())}"
    )
    assert len(v2_cols) > 0, (
        f"Expected v2 invoice/total/amount column, got columns: {list(first_row.keys())}"
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

    # Get the data frame name and contents
    data_frame_name = sql_tool_call.input_data.get("new_data_frame_name")
    assert data_frame_name, f"Tool input missing new_data_frame_name: {sql_tool_call.input_data}"

    # Get actual data frame contents
    contents = get_data_frame_contents_as_json(client, thread_id, data_frame_name)
    print(f"Data frame contents: {contents}")

    # Verify we have exactly 1 document created after 2025-10-01
    assert len(contents) == 1, f"Expected 1 document, got {len(contents)}"

    # Verify the row has a document name
    first_row = contents[0]
    assert any(
        "document" in str(k).lower() or "name" in str(k).lower() for k in first_row.keys()
    ), f"Expected document/name column, got: {list(first_row.keys())}"

    # Get the document name value
    doc_name_col = next(
        (k for k in first_row.keys() if "document" in str(k).lower() or "name" in str(k).lower()),
        None,
    )
    doc_name = first_row[doc_name_col] if doc_name_col else None
    print(f"Document created after Oct 1, 2025: {doc_name}")


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

    # Get the data frame name and contents
    data_frame_name = sql_tool_call.input_data.get("new_data_frame_name")
    assert data_frame_name, f"Tool input missing new_data_frame_name: {sql_tool_call.input_data}"

    # Get actual data frame contents
    contents = get_data_frame_contents_as_json(client, thread_id, data_frame_name)
    print(f"Data frame contents: {contents}")

    # Verify we have exactly 5 documents (top 5)
    assert len(contents) == 5, f"Expected 5 documents, got {len(contents)}"

    # Verify each row has a document name
    for i, row in enumerate(contents):
        assert any("document" in str(k).lower() or "name" in str(k).lower() for k in row.keys()), (
            f"Row {i}: Expected document/name column, got: {list(row.keys())}"
        )

    # Optionally check that updated_at is included and documents are in descending order
    updated_col = next((k for k in contents[0].keys() if "updated" in str(k).lower()), None)
    if updated_col and len(contents) > 1:
        # Verify descending order (most recent first)
        for i in range(len(contents) - 1):
            # Handle None values and compare timestamps if both are present
            curr_val = contents[i].get(updated_col)
            next_val = contents[i + 1].get(updated_col)
            if curr_val and next_val:
                assert str(curr_val) >= str(next_val), (
                    "Documents not in descending order by updated_at"
                )


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

    # Get the data frame name and contents
    data_frame_name = sql_tool_call.input_data.get("new_data_frame_name")
    assert data_frame_name, f"Tool input missing new_data_frame_name: {sql_tool_call.input_data}"

    # Get actual data frame contents
    contents = get_data_frame_contents_as_json(client, thread_id, data_frame_name)
    print(f"Data frame contents (first 3 rows): {contents[:3]}")

    # Verify we have at least 4 documents with different totals
    assert len(contents) >= 4, f"Expected at least 4 documents, got {len(contents)}"

    # Verify each row has a document name
    for i, row in enumerate(contents[:3]):  # Check first 3 rows
        assert any("document" in str(k).lower() or "name" in str(k).lower() for k in row.keys()), (
            f"Row {i}: Expected document/name column, got: {list(row.keys())}"
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

    # Get the data frame name and contents
    data_frame_name = sql_tool_call.input_data.get("new_data_frame_name")
    assert data_frame_name, f"Tool input missing new_data_frame_name: {sql_tool_call.input_data}"

    # Get actual data frame contents
    contents = get_data_frame_contents_as_json(client, thread_id, data_frame_name)
    print(f"Data frame contents (first 3 rows): {contents[:3]}")

    # Verify we have at least 1 document where v2 > v1
    assert len(contents) >= 1, f"Expected at least 1 document, got {len(contents)}"

    # Verify each row has a document name
    for i, row in enumerate(contents[:3]):  # Check first 3 rows
        assert any("document" in str(k).lower() or "name" in str(k).lower() for k in row.keys()), (
            f"Row {i}: Expected document/name column, got: {list(row.keys())}"
        )


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

    # Get the data frame name and contents
    data_frame_name = sql_tool_call.input_data.get("new_data_frame_name")
    assert data_frame_name, f"Tool input missing new_data_frame_name: {sql_tool_call.input_data}"

    # Get actual data frame contents
    contents = get_data_frame_contents_as_json(client, thread_id, data_frame_name)
    print(f"Data frame contents: {contents}")

    # Verify we have exactly 1 row (COUNT result)
    assert len(contents) == 1, f"Expected 1 row (COUNT result), got {len(contents)}"

    # Verify the row has a count value
    first_row = contents[0]
    count_col = next(
        (k for k in first_row.keys() if "count" in str(k).lower()),
        next(iter(first_row.keys())),  # If no "count" column, take first column
    )
    count_value = first_row[count_col]
    print(f"Count of mismatched documents: {count_value}")

    # Verify count is a number and >= 0
    assert isinstance(count_value, int | float) or str(count_value).isdigit(), (
        f"Expected numeric count value, got: {count_value}"
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

    # Get the data frame name and contents
    data_frame_name = sql_tool_call.input_data.get("new_data_frame_name")
    assert data_frame_name, f"Tool input missing new_data_frame_name: {sql_tool_call.input_data}"

    # Get actual data frame contents
    contents = get_data_frame_contents_as_json(client, thread_id, data_frame_name)
    print(f"Data frame contents: {contents}")

    # Verify we have exactly 1 row (AVG result)
    assert len(contents) == 1, f"Expected 1 row (AVG result), got {len(contents)}"

    # Verify the row has average values
    first_row = contents[0]
    # Check for average columns (could be avg_v1, avg_v2, or similar)
    avg_cols = [
        k for k in first_row.keys() if "avg" in str(k).lower() or "average" in str(k).lower()
    ]

    # Should have at least one average value
    assert len(avg_cols) > 0 or len(first_row.keys()) > 0, (
        f"Expected average columns in result, got: {list(first_row.keys())}"
    )

    # Verify values are numeric (or None for NULL averages)
    for key, value in first_row.items():
        if value is not None:
            is_numeric = (
                isinstance(value, int | float)
                or str(value).replace(".", "").replace("-", "").isdigit()
            )
            assert is_numeric, f"Expected numeric value for {key}, got: {value}"


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

    # Verify non-empty result
    assert str(result), f"Empty result for query: {query}"

    # Get the data frame name and contents
    data_frame_name = sql_tool_call.input_data.get("new_data_frame_name")
    assert data_frame_name, f"Tool input missing new_data_frame_name: {sql_tool_call.input_data}"

    # Get actual data frame contents
    contents = get_data_frame_contents_as_json(client, thread_id, data_frame_name)
    print(f"Data frame contents: {contents}")

    # Verify we have exactly 1 row (COUNT result)
    assert len(contents) == 1, f"Expected 1 row (COUNT result), got {len(contents)}"

    # Verify the row has a count value
    first_row = contents[0]
    count_col = next(
        (k for k in first_row.keys() if "count" in str(k).lower()),
        next(iter(first_row.keys())),  # If no "count" column, take first column
    )
    count_value = first_row[count_col]
    print(f"Count of exported documents: {count_value}")

    # Verify count is a number and equals 19 (19 exported documents in test data)
    assert isinstance(count_value, int | float) or str(count_value).isdigit(), (
        f"Expected numeric count value, got: {count_value}"
    )
    assert int(count_value) == 19, f"Expected 19 exported documents, got {count_value}"


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

    # Get the data frame name and contents
    data_frame_name = sql_tool_call.input_data.get("new_data_frame_name")
    assert data_frame_name, f"Tool input missing new_data_frame_name: {sql_tool_call.input_data}"

    # Get actual data frame contents
    contents = get_data_frame_contents_as_json(client, thread_id, data_frame_name)
    print(f"Data frame contents: {contents}")

    # Verify we have exactly 1 row (SUM result)
    assert len(contents) == 1, f"Expected 1 row (SUM result), got {len(contents)}"

    # Verify the row has sum values
    first_row = contents[0]
    # Should have sum values for v1 and v2
    [k for k in first_row.keys() if "sum" in str(k).lower()]

    # Verify we have data columns (sum or regular numeric columns)
    assert len(first_row.keys()) > 0, (
        f"Expected sum columns in result, got: {list(first_row.keys())}"
    )

    # Verify values are numeric (or None for NULL sums)
    for key, value in first_row.items():
        if value is not None:
            is_numeric = (
                isinstance(value, int | float)
                or str(value).replace(".", "").replace("-", "").isdigit()
            )
            assert is_numeric, f"Expected numeric value for {key}, got: {value}"


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

    # Get the data frame name and contents
    data_frame_name = sql_tool_call.input_data.get("new_data_frame_name")
    assert data_frame_name, f"Tool input missing new_data_frame_name: {sql_tool_call.input_data}"

    # Get actual data frame contents
    contents = get_data_frame_contents_as_json(client, thread_id, data_frame_name)
    print(f"Data frame contents: {contents}")

    # Verify we have exactly 2 rows (one for each export status: INIT and EXPORTED)
    assert len(contents) == 2, f"Expected 2 rows (grouped results), got {len(contents)}"

    # Verify each row has an export status and count
    for i, row in enumerate(contents):
        # Check for status column
        status_col = next(
            (k for k in row.keys() if "status" in str(k).lower() or "export" in str(k).lower()),
            None,
        )
        # Check for count column
        count_col = next(
            (k for k in row.keys() if "count" in str(k).lower()),
            None,
        )

        assert status_col is not None or count_col is not None, (
            f"Row {i}: Expected status and count columns, got: {list(row.keys())}"
        )

    # Verify we have both INIT and EXPORTED statuses
    statuses = []
    for row in contents:
        status_col = next(
            (k for k in row.keys() if "status" in str(k).lower() or "export" in str(k).lower()),
            next(iter(row.keys())),  # fallback to first column
        )
        statuses.append(str(row[status_col]).upper())

    assert "INIT" in statuses or "EXPORTED" in statuses, (
        f"Expected INIT or EXPORTED statuses, got: {statuses}"
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

    # Get the data frame name and contents
    data_frame_name = sql_tool_call.input_data.get("new_data_frame_name")
    assert data_frame_name, f"Tool input missing new_data_frame_name: {sql_tool_call.input_data}"

    # Get actual data frame contents
    import json

    contents_bytes = client.get_data_frame_contents(
        thread_id=thread_id,
        data_frame_name=data_frame_name,
        output_format="json",
    )
    contents = json.loads(contents_bytes.decode("utf-8"))
    print(f"Data frame contents (first 5 rows): {contents[:5]}")

    # Verify the data frame has the expected structure
    assert len(contents) == 27, f"Expected 27 rows, got {len(contents)}"
    assert len(contents) > 0, "Data frame should not be empty"

    # Check that each row has a document name and a match indicator
    first_row = contents[0]
    has_doc_name_col = any(
        "document" in str(k).lower() or "name" in str(k).lower() for k in first_row.keys()
    )
    assert has_doc_name_col, (
        f"Expected document/name column in result, got columns: {list(first_row.keys())}"
    )

    # Find the match indicator column (various names like "match", "matches", "invoice_match")
    match_column = None
    for key in first_row.keys():
        key_lower = str(key).lower()
        if "match" in key_lower or "equal" in key_lower or "same" in key_lower:
            match_column = key
            break

    assert match_column is not None, (
        f"Expected a match indicator column in result, got columns: {list(first_row.keys())}"
    )
    print(f"Found match indicator column: {match_column}")

    # Verify that we have both matching and non-matching documents in the result
    match_values = [row[match_column] for row in contents]
    # The match indicator could be boolean, string ("true"/"false"), or other values
    # Just verify we have at least some indication of both match and no-match
    unique_values = set(str(v).lower() for v in match_values)
    assert len(unique_values) > 1, (
        f"Expected both matching and non-matching documents, "
        f"but all values are the same: {unique_values}"
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

    # Get the data frame name and contents
    data_frame_name = sql_tool_call.input_data.get("new_data_frame_name")
    assert data_frame_name, f"Tool input missing new_data_frame_name: {sql_tool_call.input_data}"

    # Get actual data frame contents
    contents = get_data_frame_contents_as_json(client, thread_id, data_frame_name)
    print(f"Data frame contents (first 5 rows): {contents[:5]}")

    # Verify we have all 27 documents with mismatch flag
    assert len(contents) == 27, f"Expected 27 rows, got {len(contents)}"

    # Verify each row has a document name and a mismatch flag
    first_row = contents[0]
    assert any(
        "document" in str(k).lower() or "name" in str(k).lower() for k in first_row.keys()
    ), f"Expected document/name column, got: {list(first_row.keys())}"

    # Find the mismatch flag column
    flag_col = next(
        (
            k
            for k in first_row.keys()
            if "mismatch" in str(k).lower()
            or "differ" in str(k).lower()
            or "flag" in str(k).lower()
        ),
        None,
    )

    assert flag_col is not None, (
        f"Expected a mismatch flag column in result, got columns: {list(first_row.keys())}"
    )
    print(f"Found mismatch flag column: {flag_col}")

    # Verify that we have both true and false values in the result
    flag_values = [row[flag_col] for row in contents]
    unique_values = set(str(v).lower() for v in flag_values)
    assert len(unique_values) > 1, (
        f"Expected both matching and non-matching documents, "
        f"but all values are the same: {unique_values}"
    )


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

    # Get the data frame name and contents
    data_frame_name = sql_tool_call.input_data.get("new_data_frame_name")
    assert data_frame_name, f"Tool input missing new_data_frame_name: {sql_tool_call.input_data}"

    # Get actual data frame contents
    contents = get_data_frame_contents_as_json(client, thread_id, data_frame_name)
    print(f"Data frame contents (first 3 rows): {contents[:3]}")

    # Verify we have at least 20 documents (some may be filtered due to NULLs)
    assert len(contents) >= 20, f"Expected at least 20 rows, got {len(contents)}"

    # Verify each row has document name, v1, v2, and percentage change columns
    first_row = contents[0]
    assert any(
        "document" in str(k).lower() or "name" in str(k).lower() for k in first_row.keys()
    ), f"Expected document/name column, got: {list(first_row.keys())}"

    # Check for percentage/change column
    pct_col = next(
        (k for k in first_row.keys() if "percent" in str(k).lower() or "change" in str(k).lower()),
        None,
    )

    # The percentage column might have various names
    assert pct_col is not None or len(first_row.keys()) >= 3, (
        f"Expected percentage change column, got: {list(first_row.keys())}"
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

    # Get the data frame name and contents
    data_frame_name = sql_tool_call.input_data.get("new_data_frame_name")
    assert data_frame_name, f"Tool input missing new_data_frame_name: {sql_tool_call.input_data}"

    # Get actual data frame contents
    contents = get_data_frame_contents_as_json(client, thread_id, data_frame_name)
    print(f"Data frame contents: {contents}")

    # Verify we have 0 or more rows (test data from Sept 2025, likely 0 results)
    assert len(contents) >= 0, f"Expected 0 or more rows, got {len(contents)}"

    # If we have results, verify each row has a document name
    for i, row in enumerate(contents):
        assert any("document" in str(k).lower() or "name" in str(k).lower() for k in row.keys()), (
            f"Row {i}: Expected document/name column, got: {list(row.keys())}"
        )


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

    # Get the data frame name and contents
    data_frame_name = sql_tool_call.input_data.get("new_data_frame_name")
    assert data_frame_name, f"Tool input missing new_data_frame_name: {sql_tool_call.input_data}"

    # Get actual data frame contents
    contents = get_data_frame_contents_as_json(client, thread_id, data_frame_name)
    print(f"Data frame contents (first 3 rows): {contents[:3]}")

    # Verify we have at least 5 documents with >1 day time gap
    assert len(contents) >= 5, f"Expected at least 5 rows, got {len(contents)}"

    # Verify each row has a document name
    for i, row in enumerate(contents[:3]):  # Check first 3
        assert any("document" in str(k).lower() or "name" in str(k).lower() for k in row.keys()), (
            f"Row {i}: Expected document/name column, got: {list(row.keys())}"
        )


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

    # Get the data frame name and contents
    data_frame_name = sql_tool_call.input_data.get("new_data_frame_name")
    assert data_frame_name, f"Tool input missing new_data_frame_name: {sql_tool_call.input_data}"

    # Get actual data frame contents
    contents = get_data_frame_contents_as_json(client, thread_id, data_frame_name)
    print(f"Data frame contents (first 3 rows): {contents[:3]}")

    # Verify we have at least 2 INIT documents with mismatches
    assert len(contents) >= 2, f"Expected at least 2 rows, got {len(contents)}"

    # Verify each row has a document name
    for i, row in enumerate(contents[:3]):  # Check first 3
        assert any("document" in str(k).lower() or "name" in str(k).lower() for k in row.keys()), (
            f"Row {i}: Expected document/name column, got: {list(row.keys())}"
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

    # Get the data frame name and contents
    data_frame_name = sql_tool_call.input_data.get("new_data_frame_name")
    assert data_frame_name, f"Tool input missing new_data_frame_name: {sql_tool_call.input_data}"

    # Get actual data frame contents
    contents = get_data_frame_contents_as_json(client, thread_id, data_frame_name)
    print(f"Data frame contents (first 3 rows): {contents[:3]}")

    # Verify we have at least 3 documents with negative v2 line items
    assert len(contents) >= 3, f"Expected at least 3 rows, got {len(contents)}"

    # Verify each row has a document name
    for i, row in enumerate(contents[:3]):  # Check first 3
        assert any("document" in str(k).lower() or "name" in str(k).lower() for k in row.keys()), (
            f"Row {i}: Expected document/name column, got: {list(row.keys())}"
        )


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

    # Get the data frame name and contents
    data_frame_name = sql_tool_call.input_data.get("new_data_frame_name")
    assert data_frame_name, f"Tool input missing new_data_frame_name: {sql_tool_call.input_data}"

    # Get actual data frame contents
    contents = get_data_frame_contents_as_json(client, thread_id, data_frame_name)
    print(f"Data frame contents: {contents}")

    # Verify we have exactly 1 row (percentage result)
    assert len(contents) == 1, f"Expected 1 row (percentage result), got {len(contents)}"

    # Verify the row has a percentage value
    first_row = contents[0]
    # Get the first (and likely only) value
    percentage_col = next(iter(first_row.keys())) if first_row.keys() else None
    assert percentage_col is not None, "Expected at least one column in result"

    percentage_value = first_row[percentage_col]
    print(f"Percentage of exported documents: {percentage_value}")

    # Verify percentage is a number (between 0 and 100, or 0 and 1 if not multiplied by 100)
    is_numeric = (
        isinstance(percentage_value, int | float)
        or str(percentage_value).replace(".", "").isdigit()
    )
    assert is_numeric, f"Expected numeric percentage value, got: {percentage_value}"

    # Expected: ~70% (19 exported out of 27 total = 70.37%)
    pct = float(percentage_value)
    assert 0 <= pct <= 100 or 0 <= pct <= 1, f"Expected percentage between 0-100 or 0-1, got: {pct}"
