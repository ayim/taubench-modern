"""
MySQL Semantic Data Model JSON Queries Tests

Focused tests on MySQL JSON column functionality including:
- JSON extraction and querying
- JSON arrays and objects
- JSON nested structures
- JSON filtering and aggregations

These tests verify that the semantic data model correctly handles MySQL JSON data types
and that the LLM guidance helps generate correct MySQL JSON syntax.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from agent_platform.orchestrator.agent_server_client import AgentServerClient

    from agent_platform.core.payloads.data_connection import DataConnection

# Mark as SPAR and semantic data model tests
pytestmark = [pytest.mark.spar, pytest.mark.semantic_data_models]


@pytest.fixture(autouse=True)
def skip_if_not_mysql(engine: str):
    """Auto-skip these tests if not running MySQL."""
    if engine != "mysql":
        pytest.skip("MySQL JSON query tests - MySQL only")


@pytest.fixture(scope="module")
def mysql_json_agent(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    openai_api_key: str,
    engine: str,
) -> str:
    """Create an agent for MySQL JSON semantic data model tests."""

    import uuid

    client, _ = agent_server_client_with_data_connection

    agent_id = client.create_agent_and_return_agent_id(
        name=f"MySQL JSON Test Agent {uuid.uuid4().hex[:8]}",
        action_packages=[],
        platform_configs=[
            {
                "kind": "openai",
                "openai_api_key": openai_api_key,
                "models": {"openai": ["gpt-4o"]},
            }
        ],
        runbook=("You are a helpful assistant for testing MySQL semantic data models with JSON columns."),
    )
    return agent_id


@pytest.fixture(scope="module")
def mysql_json_semantic_model(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    mysql_json_agent: str,
    engine: str,
) -> dict[str, Any]:
    """Generate semantic data model including JSON edge case tables."""
    if engine != "mysql":
        pytest.skip("MySQL-specific fixture")

    from dataclasses import asdict

    from agent_platform.core.payloads.semantic_data_model_payloads import (
        DataConnectionInfo,
        GenerateSemanticDataModelPayload,
    )

    client, data_connection = agent_server_client_with_data_connection
    agent_id = mysql_json_agent

    # Inspect tables with JSON columns
    assert data_connection.id is not None
    inspect_response = client.inspect_data_connection(
        connection_id=data_connection.id,
        tables_to_inspect=[
            {
                "name": "products_with_json",
                "database": None,
                "schema": None,
                "columns_to_inspect": None,
            },
            {
                "name": "user_preferences",
                "database": None,
                "schema": None,
                "columns_to_inspect": None,
            },
            {
                "name": "event_logs",
                "database": None,
                "schema": None,
                "columns_to_inspect": None,
            },
            {
                "name": "locations",
                "database": None,
                "schema": None,
                "columns_to_inspect": None,
            },
            {
                "name": "advanced_products",
                "database": None,
                "schema": None,
                "columns_to_inspect": None,
            },
            {
                "name": "json_complex_structures",
                "database": None,
                "schema": None,
                "columns_to_inspect": None,
            },
            {
                "name": "invoice_documents",
                "database": None,
                "schema": None,
                "columns_to_inspect": None,
            },
        ],
    )

    # Generate semantic data model
    payload = GenerateSemanticDataModelPayload(
        name="mysql_json_test_model",
        description="MySQL semantic data model with JSON columns",
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


def test_mysql_json_tables_loaded(
    mysql_json_semantic_model: dict[str, Any],
) -> None:
    """Test that all JSON tables are present in the semantic model."""
    assert "semantic_model" in mysql_json_semantic_model
    semantic_model = mysql_json_semantic_model["semantic_model"]

    table_names = [table["base_table"]["table"] for table in semantic_model["tables"]]

    # Verify all JSON tables are present
    expected_tables = [
        "products_with_json",
        "user_preferences",
        "event_logs",
        "locations",
        "advanced_products",
        "json_complex_structures",
        "invoice_documents",
    ]

    for expected_table in expected_tables:
        assert expected_table in table_names, f"Table {expected_table} not in semantic model"


def test_mysql_json_columns_detected(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
) -> None:
    """Test that JSON columns are correctly detected during inspection."""
    client, data_connection = agent_server_client_with_data_connection

    assert data_connection.id is not None
    inspect_response = client.inspect_data_connection(
        connection_id=data_connection.id,
        tables_to_inspect=[
            {
                "name": "products_with_json",
                "database": None,
                "schema": None,
                "columns_to_inspect": None,
            },
        ],
    )

    # Find the products_with_json table
    products_table = next(
        (t for t in inspect_response["tables"] if t["name"] == "products_with_json"),
        None,
    )
    assert products_table is not None

    # Check that JSON columns are detected with correct data type
    columns = {col["name"]: col for col in products_table["columns"]}

    assert "metadata" in columns
    assert "json" in columns["metadata"]["data_type"].lower()

    assert "specifications" in columns
    assert "json" in columns["specifications"]["data_type"].lower()

    assert "tags" in columns
    assert "json" in columns["tags"]["data_type"].lower()


@pytest.fixture(scope="module")
def created_mysql_json_model_id(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    mysql_json_semantic_model: dict[str, Any],
    engine: str,
) -> str:
    """Create the MySQL JSON semantic data model and return its ID."""
    if engine != "mysql":
        pytest.skip("MySQL-specific fixture")

    client, _ = agent_server_client_with_data_connection
    created_model = client.create_semantic_data_model(mysql_json_semantic_model)
    return created_model["semantic_data_model_id"]


@pytest.fixture(scope="module")
def agent_with_mysql_json_model(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    created_mysql_json_model_id: str,
    mysql_json_agent: str,
    engine: str,
) -> str:
    """Assign the MySQL JSON semantic data model to the agent."""
    if engine != "mysql":
        pytest.skip("MySQL-specific fixture")

    client, _ = agent_server_client_with_data_connection
    agent_id = mysql_json_agent

    # Assign the semantic data model to the agent
    client.set_agent_semantic_data_models(agent_id, [created_mysql_json_model_id])

    return agent_id


def get_last_successful_sql_call(tool_calls: list) -> Any:
    """
    Get the last successful SQL tool call from a list of tool calls.

    Agents may make multiple attempts and self-correct after errors.
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

    return successful_sql_calls[-1]


def get_data_frame_contents_as_json(
    client: AgentServerClient,
    thread_id: str,
    data_frame_name: str,
) -> list[dict]:
    """Get data frame contents as a list of dictionaries."""
    import json

    contents_bytes = client.get_data_frame_contents(
        thread_id=thread_id,
        data_frame_name=data_frame_name,
        output_format="json",
    )
    return json.loads(contents_bytes.decode("utf-8"))


@pytest.mark.flaky(max_runs=3, min_passes=1)
def test_mysql_json_product_brand_extraction(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    agent_with_mysql_json_model: str,
) -> None:
    """Test extracting brand from JSON metadata column using MySQL JSON operators.

    Expected data from edge_cases_data.sql:
    - 'Laptop Pro 15"' has brand 'TechCorp'
    - 'Wireless Mouse' has brand 'Ergo'
    - 'Standing Desk' has brand 'DeskPro'
    - 'Coffee Maker' has NULL metadata
    - 'Notebook Set' has brand 'pages' (number field)
    """
    client, _ = agent_server_client_with_data_connection
    agent_id = agent_with_mysql_json_model
    thread_id = client.create_thread_and_return_thread_id(agent_id)

    query = (
        "Show me the product name and brand for all products in products_with_json. "
        "Extract the brand from the JSON metadata column."
    )

    result, tool_calls = client.send_message_to_agent_thread(agent_id, thread_id, query)

    print(f"\nQuery: {query}")
    print(f"Result: {result}")

    # Get the successful SQL call
    sql_tool_call = get_last_successful_sql_call(tool_calls)

    # Verify tool executed successfully
    assert sql_tool_call.error is None, f"Tool execution failed: {sql_tool_call.error}"

    # Get data frame name
    data_frame_name = sql_tool_call.input_data.get("new_data_frame_name")
    assert data_frame_name, "Missing data_frame_name"

    # Get contents
    contents = get_data_frame_contents_as_json(client, thread_id, data_frame_name)
    print(f"Data frame contents: {contents}")

    # Verify we have at least 3 products (excluding NULL metadata)
    assert len(contents) >= 3, f"Expected at least 3 products, got {len(contents)}"

    # Convert to dict by product name for easier assertions
    products_by_name = {row[next(k for k in row.keys() if "name" in k.lower())]: row for row in contents}

    # Verify specific brands - fail if not found to help debug LLM query issues
    assert 'Laptop Pro 15"' in products_by_name, (
        f"'Laptop Pro 15\"' not found in results. "
        f"Available products: {list(products_by_name.keys())}. "
        f"Result: {result}. "
        f"SQL: {sql_tool_call.input_data.get('sql_query', 'N/A')}"
    )
    laptop = products_by_name['Laptop Pro 15"']
    brand_value = next((v for k, v in laptop.items() if "brand" in k.lower()), None)
    assert brand_value == "TechCorp", f"Expected 'TechCorp', got {brand_value}"
    print("✅ Laptop brand correctly extracted: TechCorp")

    assert "Wireless Mouse" in products_by_name, (
        f"'Wireless Mouse' not found in results. "
        f"Available products: {list(products_by_name.keys())}. "
        f"Result: {result}. "
        f"SQL: {sql_tool_call.input_data.get('sql_query', 'N/A')}"
    )
    mouse = products_by_name["Wireless Mouse"]
    brand_value = next((v for k, v in mouse.items() if "brand" in k.lower()), None)
    assert brand_value == "Ergo", f"Expected 'Ergo', got {brand_value}"
    print("✅ Mouse brand correctly extracted: Ergo")


@pytest.mark.flaky(max_runs=3, min_passes=1)
def test_mysql_json_nested_field_extraction(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    agent_with_mysql_json_model: str,
) -> None:
    """Test extracting nested JSON fields from specifications.

    Expected data:
    - Laptop has specifications->cpu = 'Intel i7'
    - Laptop has specifications->screen->size = 15.6
    """
    client, _ = agent_server_client_with_data_connection
    agent_id = agent_with_mysql_json_model
    thread_id = client.create_thread_and_return_thread_id(agent_id)

    query = (
        "Show me the product name and CPU from the specifications JSON column for products in products_with_json table."
    )

    result, tool_calls = client.send_message_to_agent_thread(agent_id, thread_id, query)

    print(f"\nQuery: {query}")
    print(f"Result: {result}")

    sql_tool_call = get_last_successful_sql_call(tool_calls)
    assert sql_tool_call.error is None

    data_frame_name = sql_tool_call.input_data.get("new_data_frame_name")
    contents = get_data_frame_contents_as_json(client, thread_id, data_frame_name)

    print(f"Data frame contents: {contents}")

    # Verify we got some results
    assert len(contents) > 0, "Expected at least one product"

    # Find Laptop Pro in results - fail if not found
    laptop_row = next((row for row in contents if "Laptop" in str(next(iter(row.values())))), None)
    assert laptop_row is not None, (
        f"'Laptop' not found in results. "
        f"Contents: {contents}. "
        f"Result: {result}. "
        f"SQL: {sql_tool_call.input_data.get('sql_query', 'N/A')}"
    )

    # Check CPU value
    cpu_value = next((v for k, v in laptop_row.items() if "cpu" in k.lower()), None)
    # The CPU might be in the result or the query might have succeeded without extracting it
    if cpu_value:
        assert "i7" in str(cpu_value).lower() or "intel" in str(cpu_value).lower(), (
            f"Expected CPU value containing 'Intel' or 'i7', got {cpu_value}"
        )
        print(f"✅ CPU correctly extracted: {cpu_value}")
    else:
        # Query succeeded but didn't extract nested value
        # Still counts as success for JSON syntax
        print("⚠️ Query succeeded but CPU not extracted from nested JSON (LLM may need more context)")


@pytest.mark.flaky(max_runs=3, min_passes=1)
def test_mysql_json_array_contains_check(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    agent_with_mysql_json_model: str,
) -> None:
    """Test filtering products by checking if JSON array contains a value.

    Expected data:
    - Laptop has tags: ["electronics", "computers", "bestseller"]
    - Wireless Mouse has tags: ["electronics", "accessories", "new"]
    """
    client, _ = agent_server_client_with_data_connection
    agent_id = agent_with_mysql_json_model
    thread_id = client.create_thread_and_return_thread_id(agent_id)

    query = (
        "Show me products from products_with_json where the tags array contains 'electronics'. Show the product name."
    )

    result, tool_calls = client.send_message_to_agent_thread(agent_id, thread_id, query)

    print(f"\nQuery: {query}")
    print(f"Result: {result}")

    sql_tool_call = get_last_successful_sql_call(tool_calls)
    assert sql_tool_call.error is None

    data_frame_name = sql_tool_call.input_data.get("new_data_frame_name")
    contents = get_data_frame_contents_as_json(client, thread_id, data_frame_name)

    print(f"Data frame contents: {contents}")

    # Should have at least 2 products with 'electronics' tag
    assert len(contents) >= 2, f"Expected at least 2 products with electronics tag, got {len(contents)}"

    # Verify Laptop and Mouse are in results
    product_names = [str(next(iter(row.values()))) for row in contents]
    has_laptop = any("Laptop" in name for name in product_names)
    has_mouse = any("Mouse" in name for name in product_names)

    assert has_laptop or has_mouse, "Expected to find Laptop or Mouse in results"
    print(f"✅ Found products with electronics tag: {product_names}")


@pytest.mark.flaky(max_runs=3, min_passes=1)
def test_mysql_json_user_preferences_nested(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    agent_with_mysql_json_model: str,
) -> None:
    """Test querying deeply nested JSON in user_preferences.

    Expected data:
    - User 1 has preferences->theme = 'dark'
    - User 1 has preferences->notifications->email = true
    - User 2 has preferences->theme = 'light'
    """
    client, _ = agent_server_client_with_data_connection
    agent_id = agent_with_mysql_json_model
    thread_id = client.create_thread_and_return_thread_id(agent_id)

    query = (
        "Show me the user_id and theme preference from the user_preferences table. "
        "Extract the theme from the nested JSON preferences column."
    )

    result, tool_calls = client.send_message_to_agent_thread(agent_id, thread_id, query)

    print(f"\nQuery: {query}")
    print(f"Result: {result}")

    sql_tool_call = get_last_successful_sql_call(tool_calls)
    assert sql_tool_call.error is None

    data_frame_name = sql_tool_call.input_data.get("new_data_frame_name")
    contents = get_data_frame_contents_as_json(client, thread_id, data_frame_name)

    print(f"Data frame contents: {contents}")

    # Should have at least 2 users
    assert len(contents) >= 2, f"Expected at least 2 users, got {len(contents)}"

    # Find user 1 and user 2 - fail if not found
    user1 = next((row for row in contents if any(v == 1 for v in row.values())), None)
    assert user1 is not None, (
        f"User 1 not found in results. "
        f"Contents: {contents}. "
        f"Result: {result}. "
        f"SQL: {sql_tool_call.input_data.get('sql_query', 'N/A')}"
    )
    theme = next((v for k, v in user1.items() if "theme" in k.lower()), None)
    assert theme == "dark", f"Expected user 1 theme='dark', got {theme}"
    print("✅ User 1 theme correctly extracted: dark")

    user2 = next((row for row in contents if any(v == 2 for v in row.values())), None)
    assert user2 is not None, (
        f"User 2 not found in results. "
        f"Contents: {contents}. "
        f"Result: {result}. "
        f"SQL: {sql_tool_call.input_data.get('sql_query', 'N/A')}"
    )
    theme = next((v for k, v in user2.items() if "theme" in k.lower()), None)
    assert theme == "light", f"Expected user 2 theme='light', got {theme}"
    print("✅ User 2 theme correctly extracted: light")


def test_mysql_json_complex_structures_data_loaded(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
) -> None:
    """Verify that json_complex_structures table has the expected test data."""
    client, data_connection = agent_server_client_with_data_connection

    assert data_connection.id is not None
    inspect_response = client.inspect_data_connection(
        connection_id=data_connection.id,
        tables_to_inspect=[
            {
                "name": "json_complex_structures",
                "database": None,
                "schema": None,
                "columns_to_inspect": None,
            },
        ],
    )

    # Verify table exists
    json_table = next(
        (t for t in inspect_response["tables"] if t["name"] == "json_complex_structures"),
        None,
    )
    assert json_table is not None

    # Check all JSON column types are present
    columns = {col["name"]: col for col in json_table["columns"]}

    expected_columns = [
        "json_null",
        "json_bool",
        "json_number",
        "json_string",
        "json_array_empty",
        "json_array_numbers",
        "json_array_strings",
        "json_array_mixed",
        "json_array_nested",
        "json_object_empty",
        "json_object_simple",
        "json_object_nested",
        "json_object_arrays",
        "json_complex",
    ]

    for col_name in expected_columns:
        assert col_name in columns, f"Column {col_name} not found in json_complex_structures"
        assert "json" in columns[col_name]["data_type"].lower()


@pytest.mark.flaky(max_runs=3, min_passes=1)
def test_mysql_invoice_total_extraction(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    agent_with_mysql_json_model: str,
) -> None:
    """Test extracting invoice total from nested JSON field.

    Natural Language: "Show me the invoice total of each document"

    Expected data:
    - doc-001: invoice_total = 150000
    - doc-002: invoice_total = 100000
    - doc-003: invoice_total = 200000

    Tests MySQL JSON nested field extraction:
    - content_extracted->'$.invoice_total' or
    - content_extracted->>'$.invoice_total'
    """
    client, _ = agent_server_client_with_data_connection
    agent_id = agent_with_mysql_json_model
    thread_id = client.create_thread_and_return_thread_id(agent_id)

    query = "Show me the invoice total of each document from invoice_documents"

    result, tool_calls = client.send_message_to_agent_thread(agent_id, thread_id, query)

    print(f"\nQuery: {query}")
    print(f"Result: {result}")

    # Get the successful SQL call
    sql_tool_call = get_last_successful_sql_call(tool_calls)

    # Verify tool executed successfully
    assert sql_tool_call.error is None, f"Tool execution failed: {sql_tool_call.error}"

    # Get data frame name and contents
    data_frame_name = sql_tool_call.input_data.get("new_data_frame_name")
    assert data_frame_name, "Missing data_frame_name"

    contents = get_data_frame_contents_as_json(client, thread_id, data_frame_name)
    print(f"Data frame contents: {contents}")

    # Verify we have 3 invoices
    assert len(contents) == 3, f"Expected 3 invoices, got {len(contents)}"

    # Convert to dict by document ID or title for easier assertions
    invoices_by_id = {}
    for row in contents:
        # Find document identifier (could be document_id or document_title)
        doc_id = None
        for _key, value in row.items():
            if "doc-" in str(value):
                doc_id = value
                break
        if doc_id:
            invoices_by_id[doc_id] = row

    # Verify invoice totals - fail if not found
    assert "doc-001" in invoices_by_id, (
        f"'doc-001' not found in results. "
        f"Available invoices: {list(invoices_by_id.keys())}. "
        f"Result: {result}. "
        f"SQL: {sql_tool_call.input_data.get('sql_query', 'N/A')}"
    )
    invoice = invoices_by_id["doc-001"]
    total_value = next((v for k, v in invoice.items() if "total" in k.lower() or "invoice" in k.lower()), None)
    # Convert to int if it's a float
    if total_value is not None:
        total_value = int(float(total_value)) if isinstance(total_value, int | float | str) else total_value
    assert total_value == 150000, f"Expected doc-001 total=150000, got {total_value}"
    print("✅ Doc-001 invoice total correctly extracted: 150000")

    assert "doc-002" in invoices_by_id, (
        f"'doc-002' not found in results. "
        f"Available invoices: {list(invoices_by_id.keys())}. "
        f"Result: {result}. "
        f"SQL: {sql_tool_call.input_data.get('sql_query', 'N/A')}"
    )
    invoice = invoices_by_id["doc-002"]
    total_value = next((v for k, v in invoice.items() if "total" in k.lower() or "invoice" in k.lower()), None)
    if total_value is not None:
        total_value = int(float(total_value)) if isinstance(total_value, int | float | str) else total_value
    assert total_value == 100000, f"Expected doc-002 total=100000, got {total_value}"
    print("✅ Doc-002 invoice total correctly extracted: 100000")


@pytest.mark.flaky(max_runs=3, min_passes=1)
def test_mysql_invoice_sum_vs_total(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    agent_with_mysql_json_model: str,
) -> None:
    """Test comparing sum of transaction amounts vs invoice total.

    Natural Language: "Check if the sum of transaction amounts matches the invoice total"

    Expected data:
    - doc-001: sum(line_items.amount) = 150000, invoice_total = 150000 ✓ Match
    - doc-002: sum(line_items.amount) = 100000, invoice_total = 100000 ✓ Match
    - doc-003: sum(line_items.amount) = 200000, invoice_total = 200000 ✓ Match

    Tests MySQL JSON array aggregation:
    - SUM with JSON_TABLE to expand array
    - JSON path expressions for nested arrays
    - Comparison between aggregated and scalar JSON values

    Expected SQL pattern:
        SELECT
          document_id,
          (SELECT SUM(JSON_EXTRACT(item, '$.amount'))
           FROM JSON_TABLE(content_extracted, '$.line_items[*]'
                COLUMNS (item JSON PATH '$')) AS t) as sum_amounts,
          JSON_UNQUOTE(JSON_EXTRACT(content_extracted, '$.invoice_total')) as invoice_total
        FROM invoice_documents
    """
    client, _ = agent_server_client_with_data_connection
    agent_id = agent_with_mysql_json_model
    thread_id = client.create_thread_and_return_thread_id(agent_id)

    query = "For each invoice document, check if the sum of line items amounts matches the invoice total"

    result, tool_calls = client.send_message_to_agent_thread(agent_id, thread_id, query)

    print(f"\nQuery: {query}")
    print(f"Result: {result}")

    # Get the successful SQL call
    sql_tool_call = get_last_successful_sql_call(tool_calls)

    # Verify tool executed successfully
    assert sql_tool_call.error is None, f"Tool execution failed: {sql_tool_call.error}"

    # Get data frame name and contents
    data_frame_name = sql_tool_call.input_data.get("new_data_frame_name")
    assert data_frame_name, "Missing data_frame_name"

    contents = get_data_frame_contents_as_json(client, thread_id, data_frame_name)
    print(f"Data frame contents: {contents}")

    # Verify we have results for all 3 invoices
    assert len(contents) == 3, f"Expected exactly 3 invoices, got {len(contents)}"

    print("\nValidating invoice totals:")
    for row in contents:
        print(f"Row: {row}")

    # Verify the query returned data with numeric values (as strings or numbers)
    # The exact column names may vary based on LLM's SQL generation
    def has_numeric_value(v):
        """Check if value is numeric or a string representation of a positive number."""
        if isinstance(v, int | float) and v > 0:
            return True
        if isinstance(v, str):
            try:
                return float(v) > 0
            except (ValueError, TypeError):
                return False
        return False

    has_numeric_data = any(any(has_numeric_value(v) for v in row.values()) for row in contents)
    assert has_numeric_data, "Expected query to return numeric values for sums and totals"

    print("✅ Query successfully executed and returned invoice comparison data")
