"""Unit tests for semantic data model generator."""

import pytest

from agent_platform.core.payloads.semantic_data_model_payloads import (
    ColumnInfo,
    DataConnectionInfo,
    FileInfo,
    TableInfo,
)
from agent_platform.server.kernel.semantic_data_model_generator import (
    SemanticDataModelGenerator,
)


@pytest.mark.asyncio
async def test_generate_semantic_data_model_with_data_connection(data_regression):
    """Test generating a semantic data model from data connection info."""
    generator = SemanticDataModelGenerator()

    # Create sample data
    column_info = ColumnInfo(
        name="user_id",
        data_type="INTEGER",
        sample_values=[1, 2, 3],
        description="User identifier",
        synonyms=["id", "user_identifier"],
    )

    table_info = TableInfo(
        name="users",
        database="test_db",
        schema="public",
        description="User table",
        columns=[column_info],
    )

    data_connection_info = DataConnectionInfo(
        data_connection_id="conn_123",
        tables_info=[table_info],
    )

    # Generate semantic model
    result = await generator.generate_semantic_data_model(
        name="test_model",
        description="Test semantic model",
        data_connections_info=[data_connection_info],
        files_info=[],
    )

    data_regression.check(result)


@pytest.mark.asyncio
async def test_generate_semantic_data_model_with_file(data_regression):
    """Test generating a semantic data model from file info."""
    generator = SemanticDataModelGenerator()

    # Create sample data
    column_info = ColumnInfo(
        name="product_name",
        data_type="TEXT",
        sample_values=["Product A", "Product B"],
        description="Product name",
        synonyms=["name", "product"],
    )

    table_info = TableInfo(
        name="products",
        database=None,
        schema=None,
        description="Product table",
        columns=[column_info],
    )

    file_info = FileInfo(
        thread_id="thread_123",
        file_ref="file_456",
        sheet_name="Sheet1",
        tables_info=[table_info],
    )

    # Generate semantic model
    result = await generator.generate_semantic_data_model(
        name="file_model",
        description="File-based semantic model",
        data_connections_info=[],
        files_info=[file_info],
    )

    data_regression.check(result)


@pytest.mark.asyncio
async def test_generate_semantic_data_model_with_numeric_columns(data_regression):
    """Test generating a semantic data model with numeric columns (facts)."""
    generator = SemanticDataModelGenerator()

    # Create sample data with numeric column
    numeric_column = ColumnInfo(
        name="price",
        data_type="DECIMAL",
        sample_values=[10.99, 20.50],
        description="Product price",
        synonyms=["cost", "amount"],
    )

    table_info = TableInfo(
        name="products",
        database="test_db",
        schema="public",
        description="Product table",
        columns=[numeric_column],
    )

    data_connection_info = DataConnectionInfo(
        data_connection_id="conn_123",
        tables_info=[table_info],
    )

    # Generate semantic model
    result = await generator.generate_semantic_data_model(
        name="numeric_model",
        description="Model with numeric columns",
        data_connections_info=[data_connection_info],
        files_info=[],
    )

    data_regression.check(result)


@pytest.mark.asyncio
async def test_generate_semantic_data_model_with_time_columns(data_regression):
    """Test generating a semantic data model with time columns."""
    generator = SemanticDataModelGenerator()

    # Create sample data with time column
    time_column = ColumnInfo(
        name="created_at",
        data_type="TIMESTAMP",
        sample_values=["2023-01-01 10:00:00", "2023-01-02 11:00:00"],
        description="Creation timestamp",
        synonyms=["timestamp", "date_created"],
    )

    table_info = TableInfo(
        name="events",
        database="test_db",
        schema="public",
        description="Event table",
        columns=[time_column],
    )

    data_connection_info = DataConnectionInfo(
        data_connection_id="conn_123",
        tables_info=[table_info],
    )

    # Generate semantic model
    result = await generator.generate_semantic_data_model(
        name="time_model",
        description="Model with time columns",
        data_connections_info=[data_connection_info],
        files_info=[],
    )

    data_regression.check(result)
