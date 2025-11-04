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
    assert table.get("base_table") is not None, (
        f"Expected base table for table {table.get('base_table')}"
    )
    assert table.get("description") is not None, (
        f"Expected description for table {table.get('name')}"
    )
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
        assert column.get("sample_values") is not None, (
            f"Expected sample values for column {column.get('name')}"
        )

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
    assert column.dimension.get("name") is not None, (
        f"Expected name for column {column.dimension.get('name')}"
    )
    assert column.dimension.get("expr") is not None, (
        f"Expected expr for column {column.dimension.get('name')}"
    )
    assert column.dimension.get("description") is not None, (
        f"Expected description for column {column.dimension.get('name')}"
    )
    assert column.dimension.get("synonyms") is not None, (
        f"Expected synonyms for column {column.dimension.get('name')}"
    )
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
    from dataclasses import asdict

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
    assert "tables" in inspect_response
    assert len(inspect_response["tables"]) > 0

    # Create the payload for generating the semantic data model
    payload = GenerateSemanticDataModelPayload(
        name="test_model",  # Enhancement should improve this
        description=None,  # Enhancement should add this
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
    assert semantic_model["name"] is not None, "Model should have a name"
    # Enhancement should have changed the name from the input
    assert semantic_model["name"] != "test_model", "Enhancement should have changed the model name"
    assert semantic_model["description"] is not None, "Enhancement should have added a description"

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
    from dataclasses import asdict

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
    return _generate_full_semantic_data_model(
        agent_server_client_with_data_connection, agent_for_full_model
    )


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
    return _generate_full_semantic_data_model(
        agent_server_client_with_data_connection, agent_for_full_model
    )


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
    # Enhancement should have changed the name from the input
    assert semantic_model["name"] != "test_full_model", (
        "Enhancement should have changed the model name"
    )
    assert semantic_model["description"] is not None, "Model should have a description"

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
    from dataclasses import asdict

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
    return client.generate_semantic_data_model(asdict(payload))


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
    from dataclasses import asdict

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
    return client.generate_semantic_data_model(asdict(payload))


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
    from dataclasses import asdict

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
    return client.generate_semantic_data_model(asdict(payload))


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
    from dataclasses import asdict

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
    return client.generate_semantic_data_model(asdict(payload))


def assert_table_metadata_unchanged(
    initial_table_value: LogicalTable, updated_table_value: LogicalTable
):
    """Checks that the table metadata is the same for both index values. You must use
    the SemanticDataModelIndex to get the table values.
    """
    assert updated_table_value.get("name") == initial_table_value.get("name"), (
        f"Table name should remain the same: {initial_table_value.get('name')} "
        f"-> {updated_table_value.get('name')}"
    )
    assert updated_table_value.get("description") == initial_table_value.get("description"), (
        f"Table description should remain the same: {initial_table_value.get('description')} "
        f"-> {updated_table_value.get('description')}"
    )
    assert updated_table_value.get("synonyms") == initial_table_value.get("synonyms"), (
        f"Table synonyms should remain the same: {initial_table_value.get('synonyms')} "
        f"-> {updated_table_value.get('synonyms')}"
    )


def assert_table_metadta_enhanced(
    initial_table_value: LogicalTable, updated_table_value: LogicalTable
):
    """Verifies that the table metadata was enhanced. You must use the SemanticDataModelIndex
    to get the table values.
    """
    # FLAKY
    assert initial_table_value.get("name") != updated_table_value.get("name"), (
        f"Table name should be enhanced: {initial_table_value.get('name')} -> "
        f"{updated_table_value.get('name')}"
    )
    assert initial_table_value.get("description") != updated_table_value.get("description"), (
        f"Table description should be enhanced: {initial_table_value.get('description')} -> "
        f"{updated_table_value.get('description')}"
    )
    assert initial_table_value.get("synonyms") != updated_table_value.get("synonyms"), (
        f"Table synonyms should be enhanced: {initial_table_value.get('synonyms')} -> "
        f"{updated_table_value.get('synonyms')}"
    )


def assert_column_metadata_unchanged(
    initial_column: ValueForDimension, updated_column: ValueForDimension
):
    """Checks that the column metadata is the same for both index values. You must use
    the SemanticDataModelIndex to get the column values.
    """
    assert initial_column.category == updated_column.category, (
        f"Column category should remain the same: "
        f"{initial_column.category} -> {updated_column.category}"
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
    assert initial_column.dimension.get("description") == updated_column.dimension.get(
        "description"
    ), (
        f"Column description should remain the same: {initial_column.dimension.get('description')} "
        f"-> {updated_column.dimension.get('description')}"
    )


def assert_column_metadata_enhanced(
    initial_column: ValueForDimension, updated_column: ValueForDimension
):
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
        f"Column category should be enhanced: "
        f"{initial_column.category} -> {updated_column.category}"
    )
    assert initial_column.dimension.get("name") != updated_column.dimension.get("name"), (
        f"Column name should be enhanced: {initial_column.dimension.get('name')} -> "
        f"{updated_column.dimension.get('name')}"
    )
    assert initial_column.dimension.get("description") != updated_column.dimension.get(
        "description"
    ), (
        f"Column description should be enhanced: {initial_column.dimension.get('description')} -> "
        f"{updated_column.dimension.get('description')}"
    )
    assert initial_column.dimension.get("synonyms") != updated_column.dimension.get("synonyms"), (
        f"Column synonyms should be enhanced: {initial_column.dimension.get('synonyms')} -> "
        f"{updated_column.dimension.get('synonyms')}"
    )


def test_enhancer_handles_column_changes(
    initial_sdm_with_one_table: dict[str, Any],
    sdm_after_column_change: dict[str, Any],
):
    """
    Verify enhancement when adding columns to existing table and a new table.

    This test adds both new table (orders) and new columns to existing table (customers).
    Enhancement should run in full mode and enhance both.
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
    initial_orders = next(
        (t for t in initial_model["tables"] if t["base_table"]["table"] == "orders"), None
    )
    updated_orders = next(
        (t for t in updated_model["tables"] if t["base_table"]["table"] == "orders"), None
    )
    assert initial_orders is None, "Initial model should not have orders table"
    assert updated_orders is not None, "Updated model should have orders table"
    assert_table_enhanced(updated_orders)

    # Find customers table in both models
    initial_customers = next(
        (t for t in initial_model["tables"] if t["base_table"]["table"] == "customers"), None
    )
    updated_customers = next(
        (t for t in updated_model["tables"] if t["base_table"]["table"] == "customers"), None
    )

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
    assert len(updated_columns) > len(initial_columns), (
        "Updated model should have more columns than initial model"
    )

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
    assert updated_model["description"] == initial_model["description"], (
        "Model description should remain the same"
    )

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

    initial_id_column = initial_sdm_index.table_name_and_dim_expr_to_dimension[
        f"{initial_table_name}.id"
    ]
    updated_id_column = updated_sdm_index.table_name_and_dim_expr_to_dimension[
        f"{updated_table_name}.id"
    ]
    assert_column_metadata_unchanged(initial_id_column, updated_id_column)

    initial_name_column = initial_sdm_index.table_name_and_dim_expr_to_dimension[
        f"{initial_table_name}.name"
    ]
    updated_name_column = updated_sdm_index.table_name_and_dim_expr_to_dimension[
        f"{updated_table_name}.name"
    ]
    assert_column_metadata_unchanged(initial_name_column, updated_name_column)

    # Verify new columns (email, created_at) were enhanced
    # Note: These columns didn't exist in initial model (only had id and name)
    # So we can only verify they're enhanced in the updated model
    new_column_exprs = ["email", "created_at"]
    for expr in new_column_exprs:
        updated_column = updated_sdm_index.table_name_and_dim_expr_to_dimension[
            f"{updated_table_name}.{expr}"
        ]
        assert_column_enhanced(updated_column)


def test_enhancer_handles_new_tables(
    sdm_after_column_change: dict[str, Any],
    sdm_after_table_added: dict[str, Any],
):
    """
    Verify tables mode enhancement when adding new table.

    This test adds a new table (products) with subset of columns (id, name).
    Enhancement should run in tables mode and enhance the new table.
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
    initial_products = next(
        (t for t in initial_model["tables"] if t["base_table"]["table"] == "products"), None
    )
    updated_products = next(
        (t for t in updated_model["tables"] if t["base_table"]["table"] == "products"), None
    )
    assert initial_products is None, "Initial model should not have products table"
    assert updated_products is not None, "Updated model should have products table"
    assert_table_enhanced(updated_products)

    # Verify that top-level model name and description remain the same
    assert updated_model["name"] == initial_model["name"], "Model name should remain the same"
    assert updated_model["description"] == initial_model["description"], (
        "Model description should remain the same"
    )

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


def test_enhancer_handles_additional_columns(
    sdm_after_table_added: dict[str, Any],
    sdm_after_more_columns: dict[str, Any],
):
    """
    Verify columns mode enhancement when adding columns to existing table.

    This test adds more columns to products table (price, category added to id, name).
    Enhancement should run in columns mode and enhance only the new columns.
    """
    from agent_platform.server.semantic_data_models.semantic_data_model_manipulation import (
        KeyForBaseTable,
        SemanticDataModelIndex,
    )

    initial_model = sdm_after_table_added["semantic_model"]
    updated_model = sdm_after_more_columns["semantic_model"]

    # Find products table in both models
    initial_products = next(
        (t for t in initial_model["tables"] if t["base_table"]["table"] == "products"), None
    )
    updated_products = next(
        (t for t in updated_model["tables"] if t["base_table"]["table"] == "products"), None
    )

    assert initial_products is not None, "Initial model should have products table"
    assert updated_products is not None, "Updated model should have products table"

    # Get all columns from both models
    initial_columns = (
        initial_products.get("dimensions", [])
        + initial_products.get("facts", [])
        + initial_products.get("metrics", [])
        + initial_products.get("time_dimensions", [])
    )
    updated_columns = (
        updated_products.get("dimensions", [])
        + updated_products.get("facts", [])
        + updated_products.get("metrics", [])
        + updated_products.get("time_dimensions", [])
    )

    # Verify more columns in updated model
    assert len(updated_columns) > len(initial_columns), (
        "Updated model should have more columns than initial model"
    )

    # Find new columns (columns in updated but not in initial)
    # Compare by expr (database column name) not name (logical name which can be changed)
    initial_column_exprs = {col["expr"] for col in initial_columns}
    updated_column_exprs = {col["expr"] for col in updated_columns}
    new_column_exprs = updated_column_exprs - initial_column_exprs

    assert len(new_column_exprs) > 0, "Should have new columns in products table"
    assert all(expr in ["price", "category"] for expr in new_column_exprs), (
        "New columns should be price and category"
    )

    # Verify that top-level model name and description remain the same
    assert updated_model["name"] == initial_model["name"], "Model name should remain the same"
    assert updated_model["description"] == initial_model["description"], (
        "Model description should remain the same"
    )

    initial_sdm_index = SemanticDataModelIndex(initial_model)
    updated_sdm_index = SemanticDataModelIndex(updated_model)

    # Verify that products table metadata remains unchanged (columns mode, not tables mode)
    initial_products_value = initial_sdm_index.base_table_to_logical_table[
        KeyForBaseTable.from_base_table(initial_products["base_table"])
    ]
    updated_products_value = updated_sdm_index.base_table_to_logical_table[
        KeyForBaseTable.from_base_table(updated_products["base_table"])
    ]
    assert_table_metadata_unchanged(initial_products_value.table, updated_products_value.table)

    # Verify that existing columns (id, name) metadata remains unchanged
    # Use logical table name (not base table name) for index lookup
    initial_table_name = initial_products["name"]
    updated_table_name = updated_products["name"]

    for column_expr in ["id", "name"]:
        initial_column = initial_sdm_index.table_name_and_dim_expr_to_dimension[
            f"{initial_table_name}.{column_expr}"
        ]
        updated_column = updated_sdm_index.table_name_and_dim_expr_to_dimension[
            f"{updated_table_name}.{column_expr}"
        ]
        assert_column_metadata_unchanged(initial_column, updated_column)

    # Verify new columns (price, category) were enhanced
    # Note: These columns didn't exist in initial model (only had id and name)
    # So we can only verify they're enhanced in the updated model
    for expr in new_column_exprs:
        updated_column = updated_sdm_index.table_name_and_dim_expr_to_dimension[
            f"{updated_table_name}.{expr}"
        ]
        assert_column_enhanced(updated_column)
