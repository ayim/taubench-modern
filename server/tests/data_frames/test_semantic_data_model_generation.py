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


def test_create_semantic_data_model_for_llm_from_semantic_data_model(data_regression):
    """Test creating a semantic data model for LLM from a semantic data model."""
    from agent_platform.core.data_frames.semantic_data_model_types import (
        BaseTable,
        Dimension,
        Filter,
        LogicalTable,
        SemanticDataModel,
        TimeDimension,
    )
    from agent_platform.server.kernel.semantic_data_model_generator_types import (
        create_semantic_data_model_for_llm_from_semantic_data_model,
        update_semantic_data_model_with_semantic_data_model_from_llm,
    )

    dimension_example_1: Dimension = {
        "name": "product_category",
        "synonyms": ["item_category", "product_type"],
        "description": "The category of the product sold.",
        "expr": "cat",
        "data_type": "NUMBER",
        "unique": False,
        "sample_values": ["501", "544"],
    }

    dimension_example_2: Dimension = {
        "name": "store_country",
        "description": "The country where the sale took place.",
        "expr": "cntry",
        "data_type": "TEXT",
        "unique": False,
        "sample_values": ["USA", "GBR"],
    }

    dimensions_example: list[Dimension] = [
        dimension_example_1,
        dimension_example_2,
    ]

    base_table_example: BaseTable = {"database": "sales", "schema": "public", "table": "sd_data"}

    time_dimensions_example: list[TimeDimension] = [
        {
            "name": "sale_timestamp",
            "synonyms": ["time_of_sale", "transaction_time"],
            "description": "The time when the sale occurred. In UTC.",
            "expr": "dt",
            "data_type": "TIMESTAMP",
            "unique": False,
        }
    ]

    filter_example_1: Filter = {
        "name": "north_america",
        "synonyms": ["North America", "N.A.", "NA"],
        "description": "A filter to restrict only to north american countries",
        "expr": "cntry IN ('canada', 'mexico', 'usa')",
    }

    tables_example: list[LogicalTable] = [
        {
            "name": "sales_data",
            "description": """A logical table capturing daily sales information across different
                store locations and product categories.""",
            "base_table": base_table_example,
            "dimensions": dimensions_example,
            "time_dimensions": time_dimensions_example,
            "facts": [],
            "filters": [
                filter_example_1,
            ],
        }
    ]

    semantic_model_example: SemanticDataModel = {
        "name": "Sales Data",
        "description": "This semantic model can be used for asking questions over the sales data.",
        "tables": tables_example,
    }

    semantic_data_model_for_llm = create_semantic_data_model_for_llm_from_semantic_data_model(
        semantic_model_example
    )

    data_regression.check(semantic_data_model_for_llm.model_dump())

    # Now, add some synonyms and change the categories of some columns
    assert semantic_data_model_for_llm.tables
    table = semantic_data_model_for_llm.tables[0]
    assert table.columns
    table.columns[0].category = "fact"
    table.columns[0].synonyms = [
        "product_category_synonym1",
        "product_category_synonym2",
    ]

    table.columns[1].category = "dimension"
    table.columns[1].synonyms = [
        "store_country_synonym1",
        "store_country_synonym2",
    ]

    table.columns[2].synonyms = [
        "sales_channel_synonym1",
        "sales_channel_synonym2",
    ]
    data_regression.check(semantic_data_model_for_llm.model_dump(), basename="changed_for_llm")

    update_semantic_data_model_with_semantic_data_model_from_llm(
        semantic_model_example, semantic_data_model_for_llm
    )
    data_regression.check(semantic_model_example, basename="updated_from_llm")

    # Recreating it for the LLM should give the same result
    semantic_data_model_for_llm = create_semantic_data_model_for_llm_from_semantic_data_model(
        semantic_model_example
    )
    data_regression.check(semantic_data_model_for_llm.model_dump(), basename="changed_for_llm")

    update_semantic_data_model_with_semantic_data_model_from_llm(
        semantic_model_example, semantic_data_model_for_llm
    )
    data_regression.check(semantic_model_example, basename="updated_from_llm")


def test_output_schema_format(file_regression):
    """Test the output schema format."""
    from agent_platform.server.kernel.semantic_data_model_generator_types import (
        OUTPUT_SCHEMA_FORMAT,
    )

    file_regression.check(OUTPUT_SCHEMA_FORMAT, basename="output_schema_format")
