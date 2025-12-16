from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

    from agent_platform.orchestrator.agent_server_client import AgentServerClient

    from agent_platform.core.data_frames.semantic_data_model_types import LogicalTable
    from agent_platform.core.payloads.data_connection import DataConnection
    from agent_platform.server.semantic_data_models.semantic_data_model_manipulation import (
        ValueForDimension,
    )

pytestmark = [pytest.mark.spar, pytest.mark.semantic_data_models]


def assert_inspect_response_structure(inspect_response: dict[str, Any], expect_timestamp: bool = False) -> None:
    """Validate the structure of a data connection inspection response.

    Checks that the response has the expected metadata structure for tables and columns.
    This helps catch issues early if the inspection response structure changes.

    Args:
        inspect_response: The inspection response from client.inspect_data_connection().
        expect_timestamp: If True, validates that inspected_at timestamp is present.

    Raises:
        AssertionError: If any required field is missing or has an unexpected type.
    """
    # DataConnectionsInspectResponse structure
    assert "tables" in inspect_response, "Response should have 'tables' field"
    assert len(inspect_response["tables"]) > 0, "Response should have at least one table"

    # Optionally check for timestamp (added by the API endpoint)
    if expect_timestamp:
        assert "inspected_at" in inspect_response, "Response should have 'inspected_at' field"
        assert inspect_response["inspected_at"] is not None, "inspected_at should not be None"

    # Verify each table has the expected metadata structure (TableInfo)
    for table in inspect_response["tables"]:
        assert "name" in table, "Table should have 'name' field"
        assert "database" in table, "Table should have 'database' field"
        assert "schema" in table, "Table should have 'schema' field"
        assert "description" in table, "Table should have 'description' field"
        assert "columns" in table, "Table should have 'columns' field"
        assert isinstance(table["columns"], list), "Table columns should be a list"
        assert len(table["columns"]) > 0, f"Table {table['name']} should have at least one column"

        # Verify each column has the expected structure (ColumnInfo)
        for column in table["columns"]:
            assert "name" in column, "Column should have 'name' field"
            assert "data_type" in column, f"Column {column.get('name')} should have 'data_type' field"
            # Optional fields: sample_values, primary_key, unique, description, synonyms


def assert_data_connection_info_structure(data_connection_info: dict[str, Any]) -> None:
    """Validate the structure of DataConnectionInfo used in semantic model generation.

    Args:
        data_connection_info: The DataConnectionInfo dict.

    Raises:
        AssertionError: If any required field is missing or has an unexpected type.
    """
    # DataConnectionInfo required fields
    assert "data_connection_id" in data_connection_info, "DataConnectionInfo should have 'data_connection_id'"
    assert data_connection_info["data_connection_id"], "data_connection_id should not be empty"

    assert "tables_info" in data_connection_info, "DataConnectionInfo should have 'tables_info'"
    assert isinstance(data_connection_info["tables_info"], list), "tables_info should be a list"

    # Optional fields: inspect_request, inspect_response
    # Validate tables_info structure (each is a TableInfo)
    for table in data_connection_info["tables_info"]:
        assert "name" in table, "Table should have 'name' field"
        assert "columns" in table, "Table should have 'columns' field"


def assert_table_enhanced(table: LogicalTable) -> None:
    """Validate the structure and content of a logical table and that it was enhanced.

    Checks that the table has required metadata (description, synonyms) and that
    all columns (dimensions, facts, metrics, time_dimensions) have required fields.

    Args:
        table: The logical table to validate.

    Raises:
        AssertionError: If any required field is missing or invalid.
    """
    import typing

    from agent_platform.core.data_frames.semantic_data_model_types import SemanticDataModel
    from agent_platform.server.semantic_data_models.semantic_data_model_manipulation import (
        SemanticDataModelIndex,
    )

    assert table.get("name") is not None, f"Expected name for table {table.get('name')}"
    assert table.get("base_table") is not None, f"Expected base table for table {table.get('base_table')}"
    assert table.get("description") is not None, f"Expected description for table {table.get('name')}"
    assert table.get("synonyms") is not None, f"Expected synonyms for table {table.get('name')}"

    # Verify columns are in the table
    columns = (
        *(table.get("dimensions") or []),
        *(table.get("facts") or []),
        *(table.get("metrics") or []),
        *(table.get("time_dimensions") or []),
    )
    assert len(columns) > 0, f"Expected columns for table {table.get('name')}"

    # Create a minimal semantic model to use SemanticDataModelIndex
    temp_model = typing.cast(SemanticDataModel, {"tables": [table]})
    index = SemanticDataModelIndex(temp_model)

    for column in columns:
        # Check sample_values (not part of ValueForDimension)
        assert column.get("sample_values") is not None, f"Expected sample values for column {column.get('name')}"

        # Use assert_column_enhanced for the rest (DRY)
        table_name = table.get("name")
        expr = column.get("expr")
        if table_name and expr:
            column_value = index.table_name_and_dim_expr_to_dimension.get(f"{table_name}.{expr}")
            if column_value:
                assert_column_enhanced(column_value)


def assert_column_enhanced(column: ValueForDimension):
    """Checks that a column is enhanced (has description and synonyms).

    Args:
        column: The column ValueForDimension from SemanticDataModelIndex to check.
    """
    assert column.dimension.get("name") is not None, f"Expected name for column {column.dimension.get('name')}"
    assert column.dimension.get("expr") is not None, f"Expected expr for column {column.dimension.get('name')}"
    assert column.dimension.get("description") is not None, (
        f"Expected description for column {column.dimension.get('name')}"
    )
    assert column.dimension.get("synonyms") is not None, f"Expected synonyms for column {column.dimension.get('name')}"
    assert column.dimension.get("data_type") is not None, (
        f"Expected data type for column {column.dimension.get('name')}"
    )


@pytest.mark.flaky(max_runs=5, min_passes=1)
def test_generate_semantic_data_model_basic(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    agent_factory: Callable[[], str],
    openai_api_key: str,
):
    """Test generating a semantic data model from the e-commerce schema.

    This test is marked as flaky for the same reasons as
    test_generated_semantic_data_model_structure - see that test's docstring for details.
    """
    import uuid

    from agent_platform.core.payloads.semantic_data_model_payloads import (
        DataConnectionInfo,
        GenerateSemanticDataModelPayload,
    )

    client, data_connection = agent_server_client_with_data_connection
    # Create agent directly with unique name to avoid conflicts
    agent_id = client.create_agent_and_return_agent_id(
        name=f"Basic Test Agent {uuid.uuid4().hex[:8]}",
        action_packages=[],
        platform_configs=[
            {
                "kind": "openai",
                "openai_api_key": openai_api_key,
                "models": {"openai": ["gpt-5"]},
            }
        ],
        runbook="You are a helpful assistant.",
        description="This is a test agent",
        document_intelligence="v2",
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
    assert_inspect_response_structure(inspect_response)

    # Create the payload for generating the semantic data model
    data_connection_info = DataConnectionInfo(
        data_connection_id=data_connection.id or "",
        tables_info=inspect_response["tables"],
    )
    # Validate the DataConnectionInfo structure
    assert_data_connection_info_structure(data_connection_info.model_dump())

    payload = GenerateSemanticDataModelPayload(
        name="test_model",  # Enhancement should improve this
        description=None,  # Enhancement should add this
        data_connections_info=[data_connection_info],
        files_info=[],
        agent_id=agent_id,
    )

    # Generate the semantic data model
    result = client.generate_semantic_data_model(payload.model_dump())

    # Verify the result
    assert result is not None
    assert "semantic_model" in result

    # Verify the semantic model has expected structure
    semantic_model = result["semantic_model"]
    assert semantic_model["name"] is not None, "Model should have a name"
    # Enhancement should have added a description (name change is optional)
    assert semantic_model["description"] is not None, "Enhancement should have added a description"
    assert len(semantic_model["description"]) > 0, "Description should not be empty"

    # Verify tables are in the model
    assert "tables" in semantic_model
    tables = semantic_model["tables"]
    table_names = [table["base_table"]["table"] for table in tables]
    assert "customers" in table_names, "Expected 'customers' table to be in the model"
    assert "orders" in table_names, "Expected 'orders' table to be in the model"

    # Verify table enhancements
    for table in tables:
        assert_table_enhanced(table)


@pytest.fixture(scope="module")
def agent_for_full_model(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    openai_api_key: str,
) -> str:
    """Create an agent for the full model."""
    import uuid

    client, _ = agent_server_client_with_data_connection

    return client.create_agent_and_return_agent_id(
        name=f"Full Model Test Agent {uuid.uuid4().hex[:8]}",
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
        document_intelligence="v2",
    )


def _generate_full_semantic_data_model(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    agent_for_full_model: str,
) -> dict[str, Any]:
    """Helper function to generate a semantic data model from all e-commerce tables.

    This is extracted as a helper so it can be used by both module-scoped and
    function-scoped fixtures.

    Returns:
        dict: Generated semantic data model response with 'semantic_model' key
    """

    from agent_platform.core.payloads.semantic_data_model_payloads import (
        DataConnectionInfo,
        GenerateSemanticDataModelPayload,
    )

    client, data_connection = agent_server_client_with_data_connection
    agent_id = agent_for_full_model

    # Inspect the data connection with all tables
    assert data_connection.id is not None
    assert data_connection.configuration is not None
    # Configuration type varies by engine (Postgres, Snowflake, etc.)
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

    # Verify inspection response has expected structure
    assert_inspect_response_structure(inspect_response)

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
    return client.generate_semantic_data_model(payload.model_dump())


@pytest.fixture(scope="module")
def generated_semantic_data_model(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    agent_for_full_model: str,
) -> dict[str, Any]:
    """
    Fixture that generates a semantic data model from all e-commerce tables.

    Module-scoped for performance - used by other module-scoped fixtures.
    For flaky tests that need regeneration on retry, use
    generated_semantic_data_model_for_flaky_tests instead.

    Returns:
        dict: Generated semantic data model response with 'semantic_model' key
    """
    return _generate_full_semantic_data_model(agent_server_client_with_data_connection, agent_for_full_model)


@pytest.fixture
def generated_semantic_data_model_for_flaky_tests(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    agent_for_full_model: str,
) -> dict[str, Any]:
    """
    Function-scoped fixture for flaky tests that need to regenerate the model on retry.

    This allows the flaky decorator to regenerate the semantic data model if enhancement
    fails due to LLM nondeterminism.

    Returns:
        dict: Generated semantic data model response with 'semantic_model' key
    """
    return _generate_full_semantic_data_model(agent_server_client_with_data_connection, agent_for_full_model)


@pytest.mark.flaky(max_runs=5, min_passes=1)
def test_generated_semantic_data_model_structure(
    generated_semantic_data_model_for_flaky_tests: dict[str, Any],
):
    """Test that the generated semantic data model has the expected structure.

    This test is marked as flaky because:
    - Enhancement uses LLM generation which is nondeterministic
    - Quality checks are disabled to avoid performance issues and problems in partial
      enhancement scenarios
    - When enhancement fails due to poor formatting in LLM response, the original model
      is returned unchanged
    - The underlying issue is that we don't provide output structure as a tool, so the
      LLM's training isn't being fully leveraged for structured output. This will need
      to be addressed in the future.

    The flaky decorator allows retries with function-scoped fixtures to regenerate the
    model if enhancement fails.
    """
    # Verify the result
    assert generated_semantic_data_model_for_flaky_tests is not None
    assert "semantic_model" in generated_semantic_data_model_for_flaky_tests

    semantic_model = generated_semantic_data_model_for_flaky_tests["semantic_model"]

    # Verify basic model properties
    # Enhancement should have added a description (name change is optional)
    assert semantic_model["name"] is not None, "Model should have a name"
    assert semantic_model["description"] is not None, "Model should have a description"
    assert len(semantic_model["description"]) > 0, "Description should not be empty"

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
            assert column["description"] is not None, f"Expected description for column {column['name']}"
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


@pytest.mark.flaky(max_runs=3, min_passes=1)
def test_data_frame_column_headers_populated(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    agent_and_thread_with_semantic_data_model: tuple[str, str],
    created_semantic_data_model_id: str,
    engine: str,
    openai_api_key: str,
):
    """
    Test that num_columns and column_headers are correctly populated after
    creating a data frame from SQL computation.

    This validates the fix for the lazy column resolution issue where some
    backends (like Redshift) don't populate ibis expression columns until
    query execution. The fix ensures column metadata is derived from the
    materialized Table (sliced_data) rather than the lazy DataNodeResult.

    Background:
    - On some backends (e.g., Redshift), conn.sql().columns returns empty tuple
      until the query is executed
    - The fix ensures we use sliced_data.columns which is always populated
      after materialization

    Note: Snowflake uses uppercase edge case tables (CUSTOMERS_WITH_OBJECTS) due to
    case sensitivity with quoted lowercase identifiers in the main schema.
    """
    import uuid

    from agent_platform.core.payloads.semantic_data_model_payloads import (
        DataConnectionInfo,
        GenerateSemanticDataModelPayload,
    )

    client, data_connection = agent_server_client_with_data_connection

    # For Snowflake, use edge case tables (uppercase) due to case sensitivity
    if engine == "snowflake":
        # Create separate agent and semantic model for Snowflake with edge case tables
        agent_id = client.create_agent_and_return_agent_id(
            name=f"Column Headers Test Agent {uuid.uuid4().hex[:8]}",
            action_packages=[],
            platform_configs=[
                {
                    "kind": "openai",
                    "openai_api_key": openai_api_key,
                    "models": {"openai": ["gpt-4o"]},
                }
            ],
            runbook=(
                "You are an agent that creates data frames using data_frames_create_from_sql. "
                "Use the semantic data model to answer questions."
            ),
        )

        # Inspect Snowflake edge case table (uppercase, works with Snowflake)
        assert data_connection.id is not None
        inspect_response = client.inspect_data_connection(
            connection_id=data_connection.id,
            tables_to_inspect=[
                {
                    "name": "CUSTOMERS_WITH_OBJECTS",
                    "database": None,
                    "schema": None,
                    "columns_to_inspect": None,
                },
            ],
        )

        # Generate and create semantic model
        payload = GenerateSemanticDataModelPayload(
            name=f"column_headers_snowflake_{uuid.uuid4().hex[:8]}",
            description="Test model for column headers validation on Snowflake",
            data_connections_info=[
                DataConnectionInfo(
                    data_connection_id=data_connection.id,
                    tables_info=inspect_response["tables"],
                ),
            ],
            files_info=[],
            agent_id=agent_id,
        )
        generated_model = client.generate_semantic_data_model(payload.model_dump())
        created_model = client.create_semantic_data_model(generated_model)
        model_id = created_model["semantic_data_model_id"]

        # Assign model to agent and create thread
        client.set_agent_semantic_data_models(agent_id, [model_id])
        thread_id = client.create_thread_and_return_thread_id(agent_id)

        query = "Show all customers with their addresses, limited to 5 rows."
    else:
        # Use the shared fixtures for other databases
        agent_id, thread_id = agent_and_thread_with_semantic_data_model

        # Verify the model was assigned to the agent
        agent_models = client.get_agent_semantic_data_models(agent_id)
        assert len(agent_models) == 1
        assert created_semantic_data_model_id in agent_models[0]

        query = "Show all customers, limited to 5 rows."

    # Send a simple query that will create a data frame
    result, tool_calls = client.send_message_to_agent_thread(agent_id, thread_id, query)

    print(f"\nQuery: {query}")
    print(f"Result: {result}")
    print(f"Tool calls: {[tc.tool_name for tc in tool_calls]}")

    # Find successful data_frames_create_from_sql tool calls
    sql_tool_calls = [tc for tc in tool_calls if tc.tool_name == "data_frames_create_from_sql"]
    assert len(sql_tool_calls) > 0, (
        f"Expected data_frames_create_from_sql call. Got: {[tc.tool_name for tc in tool_calls]}"
    )

    # Get the last successful call
    successful_sql_calls = [tc for tc in sql_tool_calls if tc.error is None]
    assert len(successful_sql_calls) > 0, f"No successful SQL queries. Errors: {[tc.error for tc in sql_tool_calls]}"
    sql_tool_call = successful_sql_calls[-1]

    # Get data frame name from tool input
    data_frame_name = sql_tool_call.input_data.get("new_data_frame_name")
    assert data_frame_name, f"Tool input missing new_data_frame_name: {sql_tool_call.input_data}"

    # Get the data frame and verify column metadata
    data_frames = client.get_data_frames(thread_id)
    matching_df = next((df for df in data_frames if df["name"] == data_frame_name), None)
    assert matching_df is not None, f"Data frame {data_frame_name} not found in thread"

    # Validate that column headers are populated
    num_columns = matching_df.get("num_columns", 0)
    column_headers = matching_df.get("column_headers", [])

    # num_columns should be > 0
    assert num_columns > 0, (
        f"num_columns should be > 0 on {engine}, got {num_columns}. This indicates the lazy column resolution bug."
    )

    # column_headers should not be empty
    assert len(column_headers) > 0, (
        f"column_headers should not be empty on {engine}, got {column_headers}. "
        "This indicates the lazy column resolution bug."
    )

    # num_columns should match column_headers length
    assert num_columns == len(column_headers), (
        f"num_columns ({num_columns}) should match len(column_headers) ({len(column_headers)})"
    )

    # Verify we got reasonable column count
    assert num_columns >= 2, f"Expected at least 2 columns, got {num_columns}"

    # Verify we have column names (not empty strings)
    for col in column_headers:
        assert col, f"Column header should not be None/empty, got: {column_headers}"
        assert len(col) > 0, f"Column header should not be empty string, got: {column_headers}"

    print(f"\n✓ {engine}: num_columns={num_columns}, column_headers={column_headers}")


# ============================================================================
# Tests for SDM Enhancer Update Functionality
# ============================================================================


@pytest.fixture(scope="module")
def agent_for_enhancer_tests(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    openai_api_key: str,
) -> str:
    """Create an agent for enhancer tests."""
    import uuid

    client, _ = agent_server_client_with_data_connection

    return client.create_agent_and_return_agent_id(
        name=f"Enhancer Test Agent {uuid.uuid4().hex[:8]}",
        action_packages=[],
        platform_configs=[
            {
                "kind": "openai",
                "openai_api_key": openai_api_key,
                "models": {"openai": ["gpt-5"]},
            }
        ],
        runbook="You are a helpful assistant.",
        description="Agent for testing SDM enhancer update functionality",
        document_intelligence="v2",
    )


@pytest.fixture(scope="module")
def initial_sdm_with_one_table(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    agent_for_enhancer_tests: str,
) -> dict[str, Any]:
    """
    Generate initial SDM with customers table (subset of columns).

    Customers table starts with only id and name columns.
    """

    from agent_platform.core.payloads.semantic_data_model_payloads import (
        DataConnectionInfo,
        GenerateSemanticDataModelPayload,
    )

    client, data_connection = agent_server_client_with_data_connection
    agent_id = agent_for_enhancer_tests

    # Inspect customers table with only id and name columns
    assert data_connection.id is not None
    inspect_response = client.inspect_data_connection(
        connection_id=data_connection.id,
        tables_to_inspect=[
            {
                "name": "customers",
                "database": None,
                "schema": None,
                "columns_to_inspect": ["id", "name"],
            },
        ],
    )

    # Verify inspection response has expected structure
    assert_inspect_response_structure(inspect_response)

    # Create the payload for generating the semantic data model
    payload = GenerateSemanticDataModelPayload(
        name="test_enhancer_initial",
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
    return client.generate_semantic_data_model(payload.model_dump())


@pytest.fixture(scope="module")
def sdm_after_column_change(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    agent_for_enhancer_tests: str,
    initial_sdm_with_one_table: dict[str, Any],
) -> dict[str, Any]:
    """
    Regenerate SDM adding orders table and more columns to customers table.

    Customers table now has id, name, email, created_at.
    Orders table has all columns.
    This should trigger full mode enhancement (both new table and new columns).
    """

    from agent_platform.core.payloads.semantic_data_model_payloads import (
        DataConnectionInfo,
        GenerateSemanticDataModelPayload,
    )

    client, data_connection = agent_server_client_with_data_connection
    agent_id = agent_for_enhancer_tests

    # Inspect customers table with more columns (id, name, email, created_at) and orders
    assert data_connection.id is not None
    inspect_response = client.inspect_data_connection(
        connection_id=data_connection.id,
        tables_to_inspect=[
            {
                "name": "customers",
                "database": None,
                "schema": None,
                "columns_to_inspect": ["id", "name", "email", "created_at"],
            },
            {
                "name": "orders",
                "database": None,
                "schema": None,
                "columns_to_inspect": None,  # All columns
            },
        ],
    )

    # Verify inspection response has expected structure
    assert_inspect_response_structure(inspect_response)

    # Create the payload with existing_semantic_data_model to trigger partial enhancement
    payload = GenerateSemanticDataModelPayload(
        name="test_enhancer_column_change",
        description=None,
        data_connections_info=[
            DataConnectionInfo(
                data_connection_id=data_connection.id or "",
                tables_info=inspect_response["tables"],
            ),
        ],
        files_info=[],
        agent_id=agent_id,
        existing_semantic_data_model=initial_sdm_with_one_table["semantic_model"],
    )

    # Generate the semantic data model
    return client.generate_semantic_data_model(payload.model_dump())


@pytest.fixture(scope="module")
def sdm_after_table_added(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    agent_for_enhancer_tests: str,
    sdm_after_column_change: dict[str, Any],
) -> dict[str, Any]:
    """
    Regenerate SDM adding products table with subset of columns.

    This should trigger tables mode enhancement.
    Products table starts with only id and name columns.
    """

    from agent_platform.core.payloads.semantic_data_model_payloads import (
        DataConnectionInfo,
        GenerateSemanticDataModelPayload,
    )

    client, data_connection = agent_server_client_with_data_connection
    agent_id = agent_for_enhancer_tests

    # Inspect with customers (expanded columns), orders, and products (subset)
    assert data_connection.id is not None
    inspect_response = client.inspect_data_connection(
        connection_id=data_connection.id,
        tables_to_inspect=[
            {
                "name": "customers",
                "database": None,
                "schema": None,
                "columns_to_inspect": ["id", "name", "email", "created_at"],
            },
            {
                "name": "orders",
                "database": None,
                "schema": None,
                "columns_to_inspect": None,  # All columns
            },
            {
                "name": "products",
                "database": None,
                "schema": None,
                "columns_to_inspect": ["id", "name"],  # Subset of columns
            },
        ],
    )

    # Verify inspection response has expected structure
    assert_inspect_response_structure(inspect_response)

    # Create the payload with existing_semantic_data_model to trigger partial enhancement
    payload = GenerateSemanticDataModelPayload(
        name="test_enhancer_table_added",
        description=None,
        data_connections_info=[
            DataConnectionInfo(
                data_connection_id=data_connection.id or "",
                tables_info=inspect_response["tables"],
            ),
        ],
        files_info=[],
        agent_id=agent_id,
        existing_semantic_data_model=sdm_after_column_change["semantic_model"],
    )

    # Generate the semantic data model
    return client.generate_semantic_data_model(payload.model_dump())


@pytest.fixture(scope="module")
def sdm_after_more_columns(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    agent_for_enhancer_tests: str,
    sdm_after_table_added: dict[str, Any],
) -> dict[str, Any]:
    """
    Regenerate SDM adding more columns to products table.

    Products table now has id, name, price, category (more than before).
    This should trigger columns mode enhancement.
    """

    from agent_platform.core.payloads.semantic_data_model_payloads import (
        DataConnectionInfo,
        GenerateSemanticDataModelPayload,
    )

    client, data_connection = agent_server_client_with_data_connection
    agent_id = agent_for_enhancer_tests

    # Get the current products table to see what columns it has
    # Then add more columns (price, category) to products
    assert data_connection.id is not None
    inspect_response = client.inspect_data_connection(
        connection_id=data_connection.id,
        tables_to_inspect=[
            {
                "name": "customers",
                "database": None,
                "schema": None,
                "columns_to_inspect": ["id", "name", "email", "created_at"],
            },
            {
                "name": "orders",
                "database": None,
                "schema": None,
                "columns_to_inspect": None,  # All columns
            },
            {
                "name": "products",
                "database": None,
                "schema": None,
                "columns_to_inspect": ["id", "name", "price", "category"],  # More columns
            },
        ],
    )

    # Verify inspection response has expected structure
    assert_inspect_response_structure(inspect_response)

    # Create the payload with existing_semantic_data_model to trigger partial enhancement
    payload = GenerateSemanticDataModelPayload(
        name="test_enhancer_more_columns",
        description=None,
        data_connections_info=[
            DataConnectionInfo(
                data_connection_id=data_connection.id or "",
                tables_info=inspect_response["tables"],
            ),
        ],
        files_info=[],
        agent_id=agent_id,
        existing_semantic_data_model=sdm_after_table_added["semantic_model"],
    )

    # Generate the semantic data model
    return client.generate_semantic_data_model(payload.model_dump())


def assert_table_metadata_unchanged(initial_table_value: LogicalTable, updated_table_value: LogicalTable):
    """Checks that the table metadata is the same for both index values. You must use
    the SemanticDataModelIndex to get the table values.
    """
    assert updated_table_value.get("name") == initial_table_value.get("name"), (
        f"Table name should remain the same: {initial_table_value.get('name')} -> {updated_table_value.get('name')}"
    )
    assert updated_table_value.get("description") == initial_table_value.get("description"), (
        f"Table description should remain the same: {initial_table_value.get('description')} "
        f"-> {updated_table_value.get('description')}"
    )
    assert updated_table_value.get("synonyms") == initial_table_value.get("synonyms"), (
        f"Table synonyms should remain the same: {initial_table_value.get('synonyms')} "
        f"-> {updated_table_value.get('synonyms')}"
    )


def assert_table_metadta_enhanced(initial_table_value: LogicalTable, updated_table_value: LogicalTable):
    """Verifies that the table metadata was enhanced. You must use the SemanticDataModelIndex
    to get the table values.
    """
    # FLAKY
    assert initial_table_value.get("name") != updated_table_value.get("name"), (
        f"Table name should be enhanced: {initial_table_value.get('name')} -> {updated_table_value.get('name')}"
    )
    assert initial_table_value.get("description") != updated_table_value.get("description"), (
        f"Table description should be enhanced: {initial_table_value.get('description')} -> "
        f"{updated_table_value.get('description')}"
    )
    assert initial_table_value.get("synonyms") != updated_table_value.get("synonyms"), (
        f"Table synonyms should be enhanced: {initial_table_value.get('synonyms')} -> "
        f"{updated_table_value.get('synonyms')}"
    )


def assert_column_metadata_unchanged(initial_column: ValueForDimension, updated_column: ValueForDimension):
    """Checks that the column metadata is the same for both index values. You must use
    the SemanticDataModelIndex to get the column values.
    """
    assert initial_column.category == updated_column.category, (
        f"Column category should remain the same: {initial_column.category} -> {updated_column.category}"
    )
    assert initial_column.dimension.get("name") == updated_column.dimension.get("name"), (
        f"Column name should remain the same: {initial_column.dimension.get('name')} "
        f"-> {updated_column.dimension.get('name')}"
    )
    assert initial_column.dimension.get("expr") == updated_column.dimension.get("expr"), (
        f"Column expr should remain the same: {initial_column.dimension.get('expr')} "
        f"-> {updated_column.dimension.get('expr')}"
    )
    assert initial_column.dimension.get("data_type") == updated_column.dimension.get("data_type"), (
        f"Column data type should remain the same: {initial_column.dimension.get('data_type')} -> "
        f"{updated_column.dimension.get('data_type')}"
    )
    assert initial_column.dimension.get("synonyms") == updated_column.dimension.get("synonyms"), (
        f"Column synonyms should remain the same: "
        f"{initial_column.dimension.get('synonyms')} -> {updated_column.dimension.get('synonyms')}"
    )
    assert initial_column.dimension.get("description") == updated_column.dimension.get("description"), (
        f"Column description should remain the same: {initial_column.dimension.get('description')} "
        f"-> {updated_column.dimension.get('description')}"
    )


def assert_column_metadata_enhanced(initial_column: ValueForDimension, updated_column: ValueForDimension):
    """Verifies that the column metadata was enhanced. You must use the SemanticDataModelIndex to
    get the column values."""
    # Expr and data type shouldn't change
    assert initial_column.dimension.get("expr") == updated_column.dimension.get("expr"), (
        f"Column expr should remain the same: {initial_column.dimension.get('expr')} "
        f"-> {updated_column.dimension.get('expr')}"
    )
    assert initial_column.dimension.get("data_type") == updated_column.dimension.get("data_type"), (
        f"Column data type should remain the same: {initial_column.dimension.get('data_type')} "
        f"-> {updated_column.dimension.get('data_type')}"
    )

    # Expected changes. FLAKY
    assert initial_column.category != updated_column.category, (
        f"Column category should be enhanced: {initial_column.category} -> {updated_column.category}"
    )
    assert initial_column.dimension.get("name") != updated_column.dimension.get("name"), (
        f"Column name should be enhanced: {initial_column.dimension.get('name')} -> "
        f"{updated_column.dimension.get('name')}"
    )
    assert initial_column.dimension.get("description") != updated_column.dimension.get("description"), (
        f"Column description should be enhanced: {initial_column.dimension.get('description')} -> "
        f"{updated_column.dimension.get('description')}"
    )
    assert initial_column.dimension.get("synonyms") != updated_column.dimension.get("synonyms"), (
        f"Column synonyms should be enhanced: {initial_column.dimension.get('synonyms')} -> "
        f"{updated_column.dimension.get('synonyms')}"
    )


@pytest.mark.flaky(max_runs=3, min_passes=1)
def test_enhancer_handles_column_changes(
    initial_sdm_with_one_table: dict[str, Any],
    sdm_after_column_change: dict[str, Any],
):
    """
    Verify enhancement when adding columns to existing table and a new table.

    This test adds both new table (orders) and new columns to existing table (customers).
    Enhancement should run in full mode and enhance both.

    This test is marked as flaky because:
    - Enhancement uses LLM generation which is nondeterministic
    - The LLM may fail to add descriptions/synonyms to new tables/columns
    """
    from agent_platform.server.semantic_data_models.semantic_data_model_manipulation import (
        KeyForBaseTable,
        SemanticDataModelIndex,
    )

    initial_model = initial_sdm_with_one_table["semantic_model"]
    updated_model = sdm_after_column_change["semantic_model"]

    # Verify orders table was added
    initial_table_names = {t["base_table"]["table"] for t in initial_model["tables"]}
    updated_table_names = {t["base_table"]["table"] for t in updated_model["tables"]}
    assert "orders" in updated_table_names, "Orders table should be in updated model"
    assert "orders" not in initial_table_names, "Orders table should not be in initial model"

    # Find orders tables in both models
    initial_orders = next((t for t in initial_model["tables"] if t["base_table"]["table"] == "orders"), None)
    updated_orders = next((t for t in updated_model["tables"] if t["base_table"]["table"] == "orders"), None)
    assert initial_orders is None, "Initial model should not have orders table"
    assert updated_orders is not None, "Updated model should have orders table"
    assert_table_enhanced(updated_orders)

    # Find customers table in both models
    initial_customers = next((t for t in initial_model["tables"] if t["base_table"]["table"] == "customers"), None)
    updated_customers = next((t for t in updated_model["tables"] if t["base_table"]["table"] == "customers"), None)

    assert initial_customers is not None, "Initial model should have customers table"
    assert updated_customers is not None, "Updated model should have customers table"

    # Get all columns from both models
    initial_columns = (
        initial_customers.get("dimensions", [])
        + initial_customers.get("facts", [])
        + initial_customers.get("metrics", [])
        + initial_customers.get("time_dimensions", [])
    )
    updated_columns = (
        updated_customers.get("dimensions", [])
        + updated_customers.get("facts", [])
        + updated_customers.get("metrics", [])
        + updated_customers.get("time_dimensions", [])
    )

    # Verify more columns in updated model
    assert len(updated_columns) > len(initial_columns), "Updated model should have more columns than initial model"

    # Find new columns (columns in updated but not in initial)
    # Compare by expr (database column name) not name (logical name which can be changed)
    initial_column_exprs = {col["expr"] for col in initial_columns}
    updated_column_exprs = {col["expr"] for col in updated_columns}
    new_column_exprs = updated_column_exprs - initial_column_exprs

    assert len(new_column_exprs) > 0, "Should have new columns in updated model"
    assert all(expr in ["email", "created_at"] for expr in new_column_exprs), (
        "New columns should be email and created_at"
    )

    # Verify that top-level logical information remains the same
    assert updated_model["name"] == initial_model["name"], "Model name should remain the same"
    assert updated_model["description"] == initial_model["description"], "Model description should remain the same"

    initial_sdm_index = SemanticDataModelIndex(initial_model)
    updated_sdm_index = SemanticDataModelIndex(updated_model)

    # Verify that "customer" table metadata remains the same
    assert updated_customers is not None, "Should find customers table"
    initial_customers_value = initial_sdm_index.base_table_to_logical_table[
        KeyForBaseTable.from_base_table(initial_customers["base_table"])
    ]
    updated_customers_value = updated_sdm_index.base_table_to_logical_table[
        KeyForBaseTable.from_base_table(updated_customers["base_table"])
    ]
    assert_table_metadata_unchanged(initial_customers_value.table, updated_customers_value.table)

    # Verify that originally selected column metadata remains the same
    # Use logical table name (not base table name) for index lookup
    initial_table_name = initial_customers["name"]
    updated_table_name = updated_customers["name"]

    initial_id_column = initial_sdm_index.table_name_and_dim_expr_to_dimension[f"{initial_table_name}.id"]
    updated_id_column = updated_sdm_index.table_name_and_dim_expr_to_dimension[f"{updated_table_name}.id"]
    assert_column_metadata_unchanged(initial_id_column, updated_id_column)

    initial_name_column = initial_sdm_index.table_name_and_dim_expr_to_dimension[f"{initial_table_name}.name"]
    updated_name_column = updated_sdm_index.table_name_and_dim_expr_to_dimension[f"{updated_table_name}.name"]
    assert_column_metadata_unchanged(initial_name_column, updated_name_column)

    # Verify new columns (email, created_at) were enhanced
    # Note: These columns didn't exist in initial model (only had id and name)
    # So we can only verify they're enhanced in the updated model
    new_column_exprs = ["email", "created_at"]
    for expr in new_column_exprs:
        updated_column = updated_sdm_index.table_name_and_dim_expr_to_dimension[f"{updated_table_name}.{expr}"]
        assert_column_enhanced(updated_column)


@pytest.mark.flaky(max_runs=3, min_passes=1)
def test_enhancer_handles_new_tables(
    sdm_after_column_change: dict[str, Any],
    sdm_after_table_added: dict[str, Any],
):
    """
    Verify tables mode enhancement when adding new table.

    This test adds a new table (products) with subset of columns (id, name).
    Enhancement should run in tables mode and enhance the new table.

    This test is marked as flaky because:
    - Enhancement uses LLM generation which is nondeterministic
    - The LLM may fail to add descriptions/synonyms to new tables
    """
    from agent_platform.server.semantic_data_models.semantic_data_model_manipulation import (
        KeyForBaseTable,
        SemanticDataModelIndex,
    )

    initial_model = sdm_after_column_change["semantic_model"]
    updated_model = sdm_after_table_added["semantic_model"]

    # Verify products table was added
    initial_table_names = {t["base_table"]["table"] for t in initial_model["tables"]}
    updated_table_names = {t["base_table"]["table"] for t in updated_model["tables"]}
    assert "products" in updated_table_names, "Products table should be in updated model"
    assert "products" not in initial_table_names, "Products table should not be in initial model"

    # Find products table
    initial_products = next((t for t in initial_model["tables"] if t["base_table"]["table"] == "products"), None)
    updated_products = next((t for t in updated_model["tables"] if t["base_table"]["table"] == "products"), None)
    assert initial_products is None, "Initial model should not have products table"
    assert updated_products is not None, "Updated model should have products table"
    assert_table_enhanced(updated_products)

    # Verify that top-level model name and description remain the same
    assert updated_model["name"] == initial_model["name"], "Model name should remain the same"
    assert updated_model["description"] == initial_model["description"], "Model description should remain the same"

    initial_sdm_index = SemanticDataModelIndex(initial_model)
    updated_sdm_index = SemanticDataModelIndex(updated_model)

    # Verify that existing tables (customers, orders) metadata remains unchanged
    for base_table_name in ["customers", "orders"]:
        initial_table = next(
            (t for t in initial_model["tables"] if t["base_table"]["table"] == base_table_name),
            None,
        )
        updated_table = next(
            (t for t in updated_model["tables"] if t["base_table"]["table"] == base_table_name),
            None,
        )
        assert initial_table is not None, f"Initial model should have {base_table_name} table"
        assert updated_table is not None, f"Updated model should have {base_table_name} table"

        initial_table_value = initial_sdm_index.base_table_to_logical_table[
            KeyForBaseTable.from_base_table(initial_table["base_table"])
        ]
        updated_table_value = updated_sdm_index.base_table_to_logical_table[
            KeyForBaseTable.from_base_table(updated_table["base_table"])
        ]
        assert_table_metadata_unchanged(initial_table_value.table, updated_table_value.table)


def test_validation_resolves_file_references_with_thread_context(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
):
    """Test that the validate endpoint resolves file references when given thread context.

    This test verifies the fix for SDM validation where file references should be
    resolved against thread files when a thread_id is provided in the validation request.

    This is a SPAR integration test that runs against the actual compose stack.
    """
    import uuid
    from urllib.parse import urljoin

    import requests

    from agent_platform.core.data_frames.semantic_data_model_types import SemanticDataModel

    client, _ = agent_server_client_with_data_connection

    # Create agent and thread
    agent_id = client.create_agent_and_return_agent_id(
        name=f"Validation Test Agent {uuid.uuid4().hex[:8]}",
        action_packages=[],
        platform_configs=[
            {
                "kind": "openai",
                "openai_api_key": "unused",
                "models": {"openai": ["gpt-4o-mini"]},
            }
        ],
    )
    thread_id = client.create_thread_and_return_thread_id(agent_id)

    # Create a semantic model with UNRESOLVED file references (empty thread_id/file_ref)
    semantic_model: SemanticDataModel = {
        "name": "test_validation_with_file_resolution",
        "description": "Test model for validation with file reference resolution",
        "tables": [
            {
                "name": "test_data",
                "base_table": {
                    "table": "data_frame_test_data",
                    "file_reference": {
                        "thread_id": "",  # Empty - should be resolved
                        "file_ref": "",  # Empty - should be resolved
                        "sheet_name": "",
                    },
                },
                "dimensions": [
                    {
                        "name": "customer_name",
                        "expr": "customer_name",
                        "data_type": "TEXT",
                        "description": "Customer name column",
                    },
                    {
                        "name": "revenue",
                        "expr": "revenue",
                        "data_type": "NUMBER",
                        "description": "Revenue column",
                    },
                ],
            },
        ],
    }

    # Validate BEFORE uploading file - should have unresolved file reference warnings
    base_url = urljoin(client.base_url + "/", "semantic-data-models/validate")

    response_before = requests.post(
        base_url,
        json={"semantic_data_model": semantic_model, "thread_id": thread_id},
        headers={"Content-Type": "application/json"},
    )
    assert response_before.status_code == 200, (
        f"Validation request failed with status {response_before.status_code}: {response_before.text}"
    )
    validation_result_before = response_before.json()

    assert len(validation_result_before["results"]) == 1
    result_before = validation_result_before["results"][0]
    # Should have warnings about unresolved file references
    assert len(result_before.get("warnings", [])) > 0, (
        f"Expected warnings about unresolved file references before upload, "
        f"but got: {result_before.get('warnings', [])}"
    )

    # Upload matching CSV file
    csv_content = b"""customer_name,revenue
Acme Corp,150000
TechStart Inc,250000
GlobalTrade Ltd,180000"""

    client.upload_file_to_thread(
        thread_id,
        "test_data.csv",
        embedded=False,
        content=csv_content,
    )

    # Validate AFTER uploading file - file references should be resolved
    response_after = requests.post(
        base_url,
        json={"semantic_data_model": semantic_model, "thread_id": thread_id},
        headers={"Content-Type": "application/json"},
    )
    assert response_after.status_code == 200, (
        f"Validation request failed with status {response_after.status_code}: {response_after.text}"
    )
    validation_result_after = response_after.json()

    assert len(validation_result_after["results"]) == 1
    result_after = validation_result_after["results"][0]

    # Should have NO warnings about unresolved file references now
    unresolved_warnings_after = [
        w for w in result_after.get("warnings", []) if "unresolved" in w.get("message", "").lower()
    ]
    assert len(unresolved_warnings_after) == 0, (
        f"Expected no unresolved file reference warnings after upload, but got: {unresolved_warnings_after}"
    )
