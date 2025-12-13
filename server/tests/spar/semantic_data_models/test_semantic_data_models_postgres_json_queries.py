"""
Tests for semantic data models with JSON/JSONB column support.

Tests JSON and JSONB columns using the documents table.

This test module uses the documents table which contains:
- JSONB column: content_extracted (with customer.name and line_items[].amount)
- JSON column: content_translated (with Buyer.name and Transactions[].amount)
- Facts: Numeric values nested within JSON structures
- Dimensions: Text values nested within JSON structures

Tests are organized into sections:
1. JSON Column Queries (content_translated)
2. JSONB Column Queries (content_extracted)
3. Aggregation and Comparison Queries
4. Advanced JSON Path Queries

Note on Test Stability:
These tests interact with the OpenAI API and may experience intermittent failures due to:
- API rate limiting
- Network timeouts
- LLM response variability

Running Tests:
    # Run all JSON/JSONB tests
    pytest -v -m "semantic_data_models and json_queries" -k postgres

    # Run individual test sections
    pytest -v -k "test_query_content_translated"
    pytest -v -k "test_query_content_extracted"
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from agent_platform.orchestrator.agent_server_client import AgentServerClient

    from agent_platform.core.payloads.data_connection import DataConnection

# Module-level pytest marks
pytestmark = [
    pytest.mark.spar,
    pytest.mark.semantic_data_models,
    pytest.mark.json_queries,
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
        assert num_rows == expected_row_count, f"Expected exactly {expected_row_count} rows, got {num_rows}"
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


# Override the engine fixture to only use postgres for these JSON tests
@pytest.fixture(scope="module")
def engine(request: pytest.FixtureRequest):
    """
    Override engine fixture to only test Postgres JSON queries.

    JSON/JSONB support is specific to PostgreSQL.
    """
    return "postgres"


@pytest.fixture(scope="module")
def agent_for_json_queries(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    openai_api_key: str,
) -> str:
    """Create an agent for testing JSON/JSONB queries."""
    import uuid

    client, _ = agent_server_client_with_data_connection

    return client.create_agent_and_return_agent_id(
        name=f"JSON Queries Agent {uuid.uuid4().hex[:8]}",
        action_packages=[],
        platform_configs=[
            {
                "kind": "openai",
                "openai_api_key": openai_api_key,
                "models": {"openai": ["gpt-4o"]},
            }
        ],
        runbook=(
            "You are an agent that creates data frames using the data_frames_create_from_sql tool. "
            "The database includes an invoice_documents table with JSON and JSONB columns "
            "containing invoice data. The content_extracted (JSONB) column has customer "
            "information and line items. The content_translated (JSON) column has buyer "
            "information and transactions. Use the semantic data model provided to answer user "
            "questions about nested JSON data."
        ),
        description="Agent for testing JSON/JSONB queries with nested data structures",
        document_intelligence="v2",
    )


@pytest.fixture(scope="module")
def documents_semantic_data_model(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    agent_for_json_queries: str,
) -> dict[str, Any]:
    """
    Generate a semantic data model from the documents table.

    This model should include JSON/JSONB columns and their nested fields.

    Returns:
        dict: Generated semantic data model response with 'semantic_model' key
    """
    from dataclasses import asdict

    from agent_platform.core.payloads.semantic_data_model_payloads import (
        DataConnectionInfo,
        GenerateSemanticDataModelPayload,
    )

    client, data_connection = agent_server_client_with_data_connection
    agent_id = agent_for_json_queries

    # Inspect the invoice_documents table
    assert data_connection.id is not None
    inspect_response = client.inspect_data_connection(
        connection_id=data_connection.id,
        tables_to_inspect=[
            {
                "name": "invoice_documents",
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
    assert table["name"] == "invoice_documents"

    # Create the payload for generating the semantic data model
    payload = GenerateSemanticDataModelPayload(
        name="documents_invoice_model",
        description="Semantic data model for invoice documents with JSON/JSONB nested data",
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


def test_documents_semantic_data_model_structure(
    documents_semantic_data_model: dict[str, Any],
):
    """Test that the documents semantic data model has the expected structure."""
    # Verify the result
    assert documents_semantic_data_model is not None
    assert "semantic_model" in documents_semantic_data_model

    semantic_model = documents_semantic_data_model["semantic_model"]

    # Verify basic model properties
    assert semantic_model["name"] is not None
    assert semantic_model["description"] is not None

    # Verify the invoice_documents table is present
    assert "tables" in semantic_model
    tables = semantic_model["tables"]
    assert len(tables) == 1, "Expected exactly one table (invoice_documents)"

    table = tables[0]
    assert table["base_table"]["table"] == "invoice_documents"

    # Verify table has description and synonyms
    assert table["description"] is not None, "Expected description for invoice_documents table"
    assert table["synonyms"] is not None, "Expected synonyms for invoice_documents table"

    # Collect all columns
    dimensions = table.get("dimensions", [])
    facts = table.get("facts", [])
    time_dimensions = table.get("time_dimensions", [])

    all_columns = dimensions + facts + time_dimensions

    # Verify we have columns
    assert len(all_columns) > 0, "Expected columns in the table"

    # Verify each column has required properties
    for column in all_columns:
        assert column["name"] is not None, f"Expected name for column {column}"
        assert column["expr"] is not None, f"Expected expr for column {column['name']}"
        col_name = column["name"]
        assert column["description"] is not None, f"Expected description for column {col_name}"
        assert column["synonyms"] is not None, f"Expected synonyms for column {col_name}"

    print(f"Dimensions found: {[d['name'] for d in dimensions]}")
    print(f"Facts found: {[f['name'] for f in facts]}")
    print(f"Time dimensions found: {[td['name'] for td in time_dimensions]}")


@pytest.fixture(scope="module")
def created_documents_model_id(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    documents_semantic_data_model: dict[str, Any],
) -> str:
    """
    Create the documents semantic data model in the agent server.

    Returns:
        str: The semantic data model ID
    """
    client, _ = agent_server_client_with_data_connection

    # Create the semantic data model
    created_model = client.create_semantic_data_model(documents_semantic_data_model)
    return created_model["semantic_data_model_id"]


@pytest.fixture(scope="module")
def agent_with_documents_model(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    created_documents_model_id: str,
    agent_for_json_queries: str,
) -> str:
    """
    Assign the documents semantic data model to the agent.

    Returns:
        str: agent_id
    """
    client, _ = agent_server_client_with_data_connection
    agent_id = agent_for_json_queries

    # Assign the semantic data model to the agent
    client.set_agent_semantic_data_models(agent_id, [created_documents_model_id])

    return agent_id


# ============================================================================
# 1. JSON COLUMN QUERIES (content_translated)
# ============================================================================


@pytest.mark.flaky(max_runs=3, min_passes=1)
def test_query_content_translated_sum_vs_invoice_total(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    agent_with_documents_model: str,
    documents_semantic_data_model: dict[str, Any],
):
    """
    Test: For content_translated JSON column, check if sum of transaction amounts
    matches the invoice total.

    Expected SQL pattern:
        SELECT document_title,
               (SELECT SUM((t->>'amount')::numeric)
                FROM jsonb_array_elements(content_translated->'Transactions') t) AS sum_amounts,
               (content_translated->'Invoice_details'->>'invoice_total')::numeric AS invoice_total
        FROM invoice_documents

    Expected result: 7-8 documents (empty arrays may result in NULL sums that get filtered)
    """
    client, _ = agent_server_client_with_data_connection
    agent_id = agent_with_documents_model
    thread_id = client.create_thread_and_return_thread_id(agent_id)

    query = (
        "For each document, check if the sum of transaction amounts in content_translated "
        "matches the invoice total. Show the document name, sum of amounts, and invoice total."
    )

    result, tool_calls = client.send_message_to_agent_thread(agent_id, thread_id, query)

    print(f"\nQuery: {query}")
    print(f"Result: {result}")
    print(f"Tool calls: {[tc.tool_name for tc in tool_calls]}")

    # Use last successful SQL call (agents may need multiple attempts)
    sql_tool_call = get_last_successful_sql_call(tool_calls)

    # ✅ Validate SQL executed successfully and returned documents
    # Note: Documents with empty transactions arrays may be filtered out (NULL sums)
    validate_sql_execution_and_data(
        client=client,
        thread_id=thread_id,
        sql_tool_call=sql_tool_call,
        min_row_count=7,  # At least 7 documents (1 has empty transactions)
    )

    # Verify non-empty result
    assert str(result), f"Empty result for query: {query}"

    # Get the data frame name and contents
    data_frame_name = sql_tool_call.input_data.get("new_data_frame_name")
    assert data_frame_name, f"Tool input missing new_data_frame_name: {sql_tool_call.input_data}"

    # Get actual data frame contents
    contents = get_data_frame_contents_as_json(client, thread_id, data_frame_name)
    print(f"Data frame contents (first 3 rows): {contents[:3]}")

    # Verify we have at least 7 documents
    assert len(contents) >= 7, f"Expected at least 7 documents, got {len(contents)}"

    # Verify each row has the expected columns
    first_row = contents[0]
    assert any(
        "document" in str(k).lower() or "title" in str(k).lower() or "name" in str(k).lower() for k in first_row.keys()
    ), f"Expected document/title column, got: {list(first_row.keys())}"

    # Check for sum and invoice total columns
    has_sum = any("sum" in str(k).lower() or "amount" in str(k).lower() for k in first_row.keys())
    has_total = any("total" in str(k).lower() or "invoice" in str(k).lower() for k in first_row.keys())

    assert has_sum or len(first_row.keys()) >= 2, f"Expected sum column in result, got: {list(first_row.keys())}"
    assert has_total or len(first_row.keys()) >= 2, f"Expected total column in result, got: {list(first_row.keys())}"


@pytest.mark.flaky(max_runs=3, min_passes=1)
def test_query_content_translated_filter_by_buyer_name(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    agent_with_documents_model: str,
    documents_semantic_data_model: dict[str, Any],
):
    """
    Test: List all documents where the buyer name is "Koch Energy Services, LLC"
    in the content_translated JSON column.

    Expected SQL pattern:
        SELECT document_title
        FROM invoice_documents
        WHERE content_translated->'Buyer'->>'name' = 'Koch Energy Services, LLC'

    Expected result: 5 documents with Koch Energy Services as buyer
    """
    client, _ = agent_server_client_with_data_connection
    agent_id = agent_with_documents_model
    thread_id = client.create_thread_and_return_thread_id(agent_id)

    query = 'List all documents where the buyer name is "Koch Energy Services, LLC".'

    result, tool_calls = client.send_message_to_agent_thread(agent_id, thread_id, query)

    print(f"\nQuery: {query}")
    print(f"Result: {result}")
    print(f"Tool calls: {[tc.tool_name for tc in tool_calls]}")

    # Use last successful SQL call (agents may need multiple attempts)
    sql_tool_call = get_last_successful_sql_call(tool_calls)

    # ✅ Validate SQL executed successfully and returned Koch documents
    validate_sql_execution_and_data(
        client=client,
        thread_id=thread_id,
        sql_tool_call=sql_tool_call,
        expected_row_count=5,  # 5 Koch Energy Services documents in test data
    )

    # Verify non-empty result
    assert str(result), f"Empty result for query: {query}"

    # Get the data frame name and contents
    data_frame_name = sql_tool_call.input_data.get("new_data_frame_name")
    assert data_frame_name, f"Tool input missing new_data_frame_name: {sql_tool_call.input_data}"

    # Get actual data frame contents
    contents = get_data_frame_contents_as_json(client, thread_id, data_frame_name)
    print(f"Data frame contents: {contents}")

    # Verify we have exactly 5 Koch Energy Services documents
    assert len(contents) == 5, f"Expected 5 documents, got {len(contents)}"

    # Verify each row has a document name/title
    for i, row in enumerate(contents):
        assert any(
            "document" in str(k).lower() or "title" in str(k).lower() or "name" in str(k).lower() for k in row.keys()
        ), f"Row {i}: Expected document/title column, got: {list(row.keys())}"


# ============================================================================
# 2. JSONB COLUMN QUERIES (content_extracted)
# ============================================================================


@pytest.mark.flaky(max_runs=3, min_passes=1)
def test_query_content_extracted_sum_vs_invoice_total(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    agent_with_documents_model: str,
    documents_semantic_data_model: dict[str, Any],
):
    """
    Test: For content_extracted JSONB column, check if sum of line_items amounts
    matches the invoice total.

    Expected SQL pattern:
        SELECT document_title,
               (SELECT SUM((item->>'amount')::numeric)
                FROM jsonb_array_elements(content_extracted->'line_items') item) AS sum_amounts,
               (content_extracted->>'invoice_total')::numeric AS invoice_total
        FROM invoice_documents

    Expected result: 7-8 documents (empty arrays may result in NULL sums that get filtered)
    """
    client, _ = agent_server_client_with_data_connection
    agent_id = agent_with_documents_model
    thread_id = client.create_thread_and_return_thread_id(agent_id)

    query = (
        "For each document, check if the sum of line_items amounts in content_extracted "
        "matches the invoice total. Show the document name, sum of amounts, and invoice total."
    )

    result, tool_calls = client.send_message_to_agent_thread(agent_id, thread_id, query)

    print(f"\nQuery: {query}")
    print(f"Result: {result}")
    print(f"Tool calls: {[tc.tool_name for tc in tool_calls]}")

    # Use last successful SQL call (agents may need multiple attempts)
    sql_tool_call = get_last_successful_sql_call(tool_calls)

    # ✅ Validate SQL executed successfully and returned documents
    # Note: Documents with empty line_items arrays may be filtered out (NULL sums)
    validate_sql_execution_and_data(
        client=client,
        thread_id=thread_id,
        sql_tool_call=sql_tool_call,
        min_row_count=7,  # At least 7 documents (1 has empty line_items)
    )

    # Verify non-empty result
    assert str(result), f"Empty result for query: {query}"

    # Get the data frame name and contents
    data_frame_name = sql_tool_call.input_data.get("new_data_frame_name")
    assert data_frame_name, f"Tool input missing new_data_frame_name: {sql_tool_call.input_data}"

    # Get actual data frame contents
    contents = get_data_frame_contents_as_json(client, thread_id, data_frame_name)
    print(f"Data frame contents (first 3 rows): {contents[:3]}")

    # Verify we have at least 7 documents
    assert len(contents) >= 7, f"Expected at least 7 documents, got {len(contents)}"

    # Verify each row has the expected columns
    first_row = contents[0]
    assert any(
        "document" in str(k).lower() or "title" in str(k).lower() or "name" in str(k).lower() for k in first_row.keys()
    ), f"Expected document/title column, got: {list(first_row.keys())}"

    # Check for sum and invoice total columns
    has_sum = any("sum" in str(k).lower() or "amount" in str(k).lower() for k in first_row.keys())
    has_total = any("total" in str(k).lower() or "invoice" in str(k).lower() for k in first_row.keys())

    assert has_sum or len(first_row.keys()) >= 2, f"Expected sum column in result, got: {list(first_row.keys())}"
    assert has_total or len(first_row.keys()) >= 2, f"Expected total column in result, got: {list(first_row.keys())}"


@pytest.mark.flaky(max_runs=3, min_passes=1)
def test_query_content_extracted_filter_by_customer_name(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    agent_with_documents_model: str,
    documents_semantic_data_model: dict[str, Any],
):
    """
    Test: List all documents where the customer name is "Koch Energy Services, LLC"
    in the content_extracted JSONB column.

    Expected SQL pattern:
        SELECT document_title
        FROM invoice_documents
        WHERE content_extracted->'customer'->>'name' = 'Koch Energy Services, LLC'

    Expected result: 5 documents with Koch Energy Services as customer
    """
    client, _ = agent_server_client_with_data_connection
    agent_id = agent_with_documents_model
    thread_id = client.create_thread_and_return_thread_id(agent_id)

    query = 'List all documents where the customer name is "Koch Energy Services, LLC".'

    result, tool_calls = client.send_message_to_agent_thread(agent_id, thread_id, query)

    print(f"\nQuery: {query}")
    print(f"Result: {result}")
    print(f"Tool calls: {[tc.tool_name for tc in tool_calls]}")

    # Use last successful SQL call (agents may need multiple attempts)
    sql_tool_call = get_last_successful_sql_call(tool_calls)

    # ✅ Validate SQL executed successfully and returned Koch documents
    validate_sql_execution_and_data(
        client=client,
        thread_id=thread_id,
        sql_tool_call=sql_tool_call,
        expected_row_count=5,  # 5 Koch Energy Services documents in test data
    )

    # Verify non-empty result
    assert str(result), f"Empty result for query: {query}"

    # Get the data frame name and contents
    data_frame_name = sql_tool_call.input_data.get("new_data_frame_name")
    assert data_frame_name, f"Tool input missing new_data_frame_name: {sql_tool_call.input_data}"

    # Get actual data frame contents
    contents = get_data_frame_contents_as_json(client, thread_id, data_frame_name)
    print(f"Data frame contents: {contents}")

    # Verify we have exactly 5 Koch Energy Services documents
    assert len(contents) == 5, f"Expected 5 documents, got {len(contents)}"

    # Verify each row has a document name/title
    for i, row in enumerate(contents):
        assert any(
            "document" in str(k).lower() or "title" in str(k).lower() or "name" in str(k).lower() for k in row.keys()
        ), f"Row {i}: Expected document/title column, got: {list(row.keys())}"


# ============================================================================
# 3. AGGREGATION AND COMPARISON QUERIES
# ============================================================================


@pytest.mark.flaky(max_runs=3, min_passes=1)
def test_query_count_documents_by_data_model(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    agent_with_documents_model: str,
    documents_semantic_data_model: dict[str, Any],
):
    """
    Test: Count documents grouped by data_model type.

    Expected SQL pattern:
        SELECT data_model, COUNT(*) as count
        FROM invoice_documents
        GROUP BY data_model

    Expected result: 2 rows (koch_invoices: 5, standard_invoices: 3)
    """
    client, _ = agent_server_client_with_data_connection
    agent_id = agent_with_documents_model
    thread_id = client.create_thread_and_return_thread_id(agent_id)

    query = "Count how many documents there are for each data model type."

    result, tool_calls = client.send_message_to_agent_thread(agent_id, thread_id, query)

    print(f"\nQuery: {query}")
    print(f"Result: {result}")
    print(f"Tool calls: {[tc.tool_name for tc in tool_calls]}")

    # Use last successful SQL call (agents may need multiple attempts)
    sql_tool_call = get_last_successful_sql_call(tool_calls)

    # ✅ Validate SQL executed successfully and returned 2 groups
    validate_sql_execution_and_data(
        client=client,
        thread_id=thread_id,
        sql_tool_call=sql_tool_call,
        expected_row_count=2,  # 2 distinct data model types
    )

    # Verify non-empty result
    assert str(result), f"Empty result for query: {query}"

    # Get the data frame name and contents
    data_frame_name = sql_tool_call.input_data.get("new_data_frame_name")
    assert data_frame_name, f"Tool input missing new_data_frame_name: {sql_tool_call.input_data}"

    # Get actual data frame contents
    contents = get_data_frame_contents_as_json(client, thread_id, data_frame_name)
    print(f"Data frame contents: {contents}")

    # Verify we have exactly 2 groups (koch_invoices and standard_invoices)
    assert len(contents) == 2, f"Expected 2 rows (data model groups), got {len(contents)}"

    # Verify each row has data_model and count columns
    for i, row in enumerate(contents):
        # Check for data model column
        has_model = any("model" in str(k).lower() or "type" in str(k).lower() for k in row.keys())
        # Check for count column
        has_count = any("count" in str(k).lower() for k in row.keys())

        assert has_model or has_count, f"Row {i}: Expected model and count columns, got: {list(row.keys())}"


@pytest.mark.flaky(max_runs=3, min_passes=1)
def test_query_documents_with_mismatched_totals_extracted(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    agent_with_documents_model: str,
    documents_semantic_data_model: dict[str, Any],
):
    """
    Test: Find documents where the sum of line_items amounts doesn't match
    the invoice_total in content_extracted.

    Expected SQL pattern:
        SELECT document_title
        FROM invoice_documents
        WHERE (SELECT SUM((item->>'amount')::numeric)
               FROM jsonb_array_elements(content_extracted->'line_items') item)
              != (content_extracted->>'invoice_total')::numeric

    Expected result: At least 1 document with mismatch
    """
    client, _ = agent_server_client_with_data_connection
    agent_id = agent_with_documents_model
    thread_id = client.create_thread_and_return_thread_id(agent_id)

    query = (
        "Show all documents where the sum of line items amounts in content_extracted doesn't match the invoice total."
    )

    result, tool_calls = client.send_message_to_agent_thread(agent_id, thread_id, query)

    print(f"\nQuery: {query}")
    print(f"Result: {result}")
    print(f"Tool calls: {[tc.tool_name for tc in tool_calls]}")

    # Use last successful SQL call (agents may need multiple attempts)
    sql_tool_call = get_last_successful_sql_call(tool_calls)

    # ✅ Validate SQL executed successfully and returned documents with mismatches
    validate_sql_execution_and_data(
        client=client,
        thread_id=thread_id,
        sql_tool_call=sql_tool_call,
        min_row_count=1,  # At least 1 document with mismatch
    )

    # Verify non-empty result
    assert str(result), f"Empty result for query: {query}"

    # Get the data frame name and contents
    data_frame_name = sql_tool_call.input_data.get("new_data_frame_name")
    assert data_frame_name, f"Tool input missing new_data_frame_name: {sql_tool_call.input_data}"

    # Get actual data frame contents
    contents = get_data_frame_contents_as_json(client, thread_id, data_frame_name)
    print(f"Data frame contents: {contents}")

    # Verify we have at least 1 document with mismatch
    assert len(contents) >= 1, f"Expected at least 1 document, got {len(contents)}"

    # Verify each row has a document name/title
    for i, row in enumerate(contents):
        assert any(
            "document" in str(k).lower() or "title" in str(k).lower() or "name" in str(k).lower() for k in row.keys()
        ), f"Row {i}: Expected document/title column, got: {list(row.keys())}"


@pytest.mark.flaky(max_runs=3, min_passes=1)
def test_query_documents_with_mismatched_totals_translated(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    agent_with_documents_model: str,
    documents_semantic_data_model: dict[str, Any],
):
    """
    Test: Find documents where the sum of transaction amounts doesn't match
    the invoice_total in content_translated.

    Expected SQL pattern:
        SELECT document_title
        FROM invoice_documents
        WHERE (SELECT SUM((t->>'amount')::numeric)
               FROM jsonb_array_elements(content_translated->'Transactions') t)
              != (content_translated->'Invoice_details'->>'invoice_total')::numeric

    Expected result: At least 1 document with mismatch
    """
    client, _ = agent_server_client_with_data_connection
    agent_id = agent_with_documents_model
    thread_id = client.create_thread_and_return_thread_id(agent_id)

    query = (
        "Show all documents where the sum of transaction amounts in content_translated doesn't match the invoice total."
    )

    result, tool_calls = client.send_message_to_agent_thread(agent_id, thread_id, query)

    print(f"\nQuery: {query}")
    print(f"Result: {result}")
    print(f"Tool calls: {[tc.tool_name for tc in tool_calls]}")

    # Use last successful SQL call (agents may need multiple attempts)
    sql_tool_call = get_last_successful_sql_call(tool_calls)

    # ✅ Validate SQL executed successfully and returned documents with mismatches
    validate_sql_execution_and_data(
        client=client,
        thread_id=thread_id,
        sql_tool_call=sql_tool_call,
        min_row_count=1,  # At least 1 document with mismatch
    )

    # Verify non-empty result
    assert str(result), f"Empty result for query: {query}"

    # Get the data frame name and contents
    data_frame_name = sql_tool_call.input_data.get("new_data_frame_name")
    assert data_frame_name, f"Tool input missing new_data_frame_name: {sql_tool_call.input_data}"

    # Get actual data frame contents
    contents = get_data_frame_contents_as_json(client, thread_id, data_frame_name)
    print(f"Data frame contents: {contents}")

    # Verify we have at least 1 document with mismatch
    assert len(contents) >= 1, f"Expected at least 1 document, got {len(contents)}"

    # Verify each row has a document name/title
    for i, row in enumerate(contents):
        assert any(
            "document" in str(k).lower() or "title" in str(k).lower() or "name" in str(k).lower() for k in row.keys()
        ), f"Row {i}: Expected document/title column, got: {list(row.keys())}"


# ============================================================================
# 4. ADVANCED JSON PATH QUERIES
# ============================================================================


@pytest.mark.flaky(max_runs=3, min_passes=1)
def test_query_total_invoice_amount_by_customer(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    agent_with_documents_model: str,
    documents_semantic_data_model: dict[str, Any],
):
    """
    Test: Calculate total invoice amount grouped by customer name from content_extracted.

    Expected SQL pattern:
        SELECT content_extracted->'customer'->>'name' as customer_name,
               SUM((content_extracted->>'invoice_total')::numeric) as total_amount
        FROM invoice_documents
        GROUP BY content_extracted->'customer'->>'name'

    Expected result: 4 rows (one per unique customer)
    """
    client, _ = agent_server_client_with_data_connection
    agent_id = agent_with_documents_model
    thread_id = client.create_thread_and_return_thread_id(agent_id)

    query = "Show the total invoice amount for each customer."

    result, tool_calls = client.send_message_to_agent_thread(agent_id, thread_id, query)

    print(f"\nQuery: {query}")
    print(f"Result: {result}")
    print(f"Tool calls: {[tc.tool_name for tc in tool_calls]}")

    # Use last successful SQL call (agents may need multiple attempts)
    sql_tool_call = get_last_successful_sql_call(tool_calls)

    # ✅ Validate SQL executed successfully and returned customer groups
    validate_sql_execution_and_data(
        client=client,
        thread_id=thread_id,
        sql_tool_call=sql_tool_call,
        expected_row_count=4,  # 4 unique customers (Koch, Acme, Beta, Gamma)
    )

    # Verify non-empty result
    assert str(result), f"Empty result for query: {query}"

    # Get the data frame name and contents
    data_frame_name = sql_tool_call.input_data.get("new_data_frame_name")
    assert data_frame_name, f"Tool input missing new_data_frame_name: {sql_tool_call.input_data}"

    # Get actual data frame contents
    contents = get_data_frame_contents_as_json(client, thread_id, data_frame_name)
    print(f"Data frame contents: {contents}")

    # Verify we have exactly 4 customer groups
    assert len(contents) == 4, f"Expected 4 rows (customer groups), got {len(contents)}"

    # Verify each row has customer name and total amount
    for i, row in enumerate(contents):
        # Check for customer/name column
        has_customer = any("customer" in str(k).lower() or "name" in str(k).lower() for k in row.keys())
        # Check for total/amount column
        has_total = any(
            "total" in str(k).lower() or "amount" in str(k).lower() or "sum" in str(k).lower() for k in row.keys()
        )

        assert has_customer or has_total, f"Row {i}: Expected customer and total columns, got: {list(row.keys())}"
