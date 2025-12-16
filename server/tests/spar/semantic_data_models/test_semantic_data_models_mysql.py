"""
MySQL Semantic Data Model Tests

Tests semantic data model functionality specifically for MySQL databases.
Covers MySQL-specific data types, queries, and edge cases.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from agent_platform.orchestrator.agent_server_client import AgentServerClient

    from agent_platform.core.payloads.data_connection import DataConnection

# Mark as SPAR and semantic data model tests
# These tests are written for MySQL specifically but will run for all engines via parametrization
pytestmark = [pytest.mark.spar, pytest.mark.semantic_data_models]


@pytest.fixture(autouse=True)
def skip_if_not_mysql(engine: str):
    """Auto-skip these tests if not running MySQL."""
    if engine != "mysql":
        pytest.skip("MySQL-specific tests")


@pytest.fixture(scope="module")
def mysql_agent(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    openai_api_key: str,
) -> str:
    """Create an agent for MySQL semantic data model tests."""
    import uuid

    client, _ = agent_server_client_with_data_connection

    agent_id = client.create_agent_and_return_agent_id(
        name=f"MySQL Test Agent {uuid.uuid4().hex[:8]}",
        action_packages=[],
        platform_configs=[
            {
                "kind": "openai",
                "openai_api_key": openai_api_key,
                "models": {"openai": ["gpt-4o"]},
            }
        ],
        runbook="You are a helpful assistant for testing MySQL semantic data models.",
    )
    return agent_id


def test_mysql_connection(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
) -> None:
    """Test MySQL connection is established."""
    _, data_connection = agent_server_client_with_data_connection

    assert data_connection is not None
    assert data_connection.id is not None


def test_mysql_inspection(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
) -> None:
    """Test MySQL database inspection."""
    client, data_connection = agent_server_client_with_data_connection

    assert data_connection.id is not None
    inspect_response = client.inspect_data_connection(
        connection_id=data_connection.id,
        tables_to_inspect=None,  # Inspect all tables
    )

    # Verify the response structure
    assert "tables" in inspect_response
    assert len(inspect_response["tables"]) > 0

    # Verify expected tables are present
    table_names = [table["name"] for table in inspect_response["tables"]]
    assert "customers" in table_names
    assert "orders" in table_names
    assert "products" in table_names
    assert "order_items" in table_names

    # Verify a sample table has columns
    customers_table = next(t for t in inspect_response["tables"] if t["name"] == "customers")
    assert "columns" in customers_table
    assert len(customers_table["columns"]) > 0

    # Verify column structure
    columns = {col["name"]: col for col in customers_table["columns"]}
    assert "id" in columns
    assert "name" in columns
    assert "email" in columns


def test_mysql_data_types_inspection(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
) -> None:
    """Test that various MySQL data types are inspected correctly."""
    client, data_connection = agent_server_client_with_data_connection

    assert data_connection.id is not None
    inspect_response = client.inspect_data_connection(
        connection_id=data_connection.id,
        tables_to_inspect=[
            {
                "name": "mysql_data_types_test",
                "database": None,
                "schema": None,
                "columns_to_inspect": None,
            }
        ],
    )

    assert "tables" in inspect_response
    assert len(inspect_response["tables"]) > 0

    # Find the data types test table
    data_types_table = inspect_response["tables"][0]
    assert data_types_table["name"] == "mysql_data_types_test"
    assert "columns" in data_types_table

    # Verify various MySQL data types are present
    columns = {col["name"]: col for col in data_types_table["columns"]}

    # Integer types
    assert "tinyint_col" in columns
    assert "smallint_col" in columns
    assert "mediumint_col" in columns
    assert "int_col" in columns
    assert "bigint_col" in columns

    # Floating point types
    assert "float_col" in columns
    assert "double_col" in columns
    assert "decimal_col" in columns

    # String types
    assert "char_col" in columns
    assert "varchar_col" in columns
    assert "text_col" in columns

    # Date/Time types
    assert "date_col" in columns
    assert "datetime_col" in columns
    assert "timestamp_col" in columns

    # Other types
    assert "enum_col" in columns
    assert "json_col" in columns

    # Verify sample values exist for at least some columns
    int_col = columns.get("int_col")
    assert int_col is not None
    assert "sample_values" in int_col
    assert int_col["sample_values"] is not None
    assert len(int_col["sample_values"]) > 0


@pytest.mark.flaky(max_runs=3, min_passes=1)
def test_mysql_basic_query_generation(
    agent_server_client_with_data_connection: tuple[AgentServerClient, DataConnection],
    mysql_agent: str,
) -> None:
    """Test basic SQL query generation for MySQL."""

    from agent_platform.core.payloads.semantic_data_model_payloads import (
        DataConnectionInfo,
        GenerateSemanticDataModelPayload,
    )

    client, data_connection = agent_server_client_with_data_connection
    agent_id = mysql_agent

    # Inspect the data connection
    assert data_connection.id is not None
    inspect_response = client.inspect_data_connection(
        connection_id=data_connection.id,
        tables_to_inspect=None,  # Inspect all tables
    )

    # Generate semantic data model
    payload = GenerateSemanticDataModelPayload(
        name="mysql_basic_test_model",
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

    result = client.generate_semantic_data_model(payload.model_dump())

    # Verify the result
    assert result is not None
    assert "semantic_model" in result

    semantic_model = result["semantic_model"]
    assert semantic_model["name"] is not None
    assert "tables" in semantic_model
    assert len(semantic_model["tables"]) > 0

    # Verify expected tables are present
    table_names = [table["base_table"]["table"] for table in semantic_model["tables"]]
    assert "customers" in table_names
    assert "orders" in table_names
    assert "products" in table_names
