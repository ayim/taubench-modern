"""
Tests for the factory functions.
"""

import pytest

from sema4ai_docint.views import (
    BusinessSchema,
    DataFormat,
    PostgresAdapter,
    SchemaField,
    create_db_adapter,
    create_view_generator,
)


class TestFactory:
    """Tests for the factory functions."""

    def test_create_db_adapter(self):
        """Test that create_db_adapter creates the correct adapter."""
        # Test with postgres
        adapter = create_db_adapter("postgres")
        assert isinstance(adapter, PostgresAdapter)

        # Test with invalid type
        with pytest.raises(ValueError, match="Unsupported database type"):
            create_db_adapter("invalid_db")

    def test_create_view_generator(self):
        """Test that create_view_generator creates a ViewGenerator with the correct adapter."""
        # Test with default parameters
        generator = create_view_generator()
        assert isinstance(generator.db_adapter, PostgresAdapter)
        assert generator.source_table_name == "docs"
        assert generator.document_column_name == "doc"

        # Test with custom parameters
        generator = create_view_generator(
            db_type="postgres",
            source_table_name="custom_table",
            document_column_name="custom_doc",
        )
        assert isinstance(generator.db_adapter, PostgresAdapter)
        assert generator.source_table_name == "custom_table"
        assert generator.document_column_name == "custom_doc"

    def test_view_generator_with_new_schema_format(self):
        """Test that the ViewGenerator created by the factory works with the new schema format."""
        generator = create_view_generator()

        # Create a schema with the new format
        schema = BusinessSchema(
            fields=[
                SchemaField(
                    path="customer.id",
                    name="CUSTOMER_ID",
                    format=DataFormat(type="string", attributes={"length": 50}),
                ),
                SchemaField(
                    path="customer.name",
                    name="CUSTOMER_NAME",
                    format=DataFormat(type="string"),
                ),
                SchemaField(
                    path="orders[].id",
                    name="ORDER_ID",
                    format=DataFormat(type="string"),
                ),
            ]
        )

        # Generate views
        use_case_name = "orders_payments"
        views = generator.generate_views(schema, use_case_name)

        # Verify that views were generated
        assert len(views) == 1
        actual = next((v for v in views if v.name == "ORDERS_PAYMENTS_ORDERS"), None)
        assert actual is not None, "did not find the ORDERS view in the generated view."

        # Check SQL content
        sql = actual.sql
        assert "CAST(doc->'customer'->>'id' AS VARCHAR(50)) AS CUSTOMER_ID" in sql
        assert "CAST(doc->'customer'->>'name' AS VARCHAR) AS CUSTOMER_NAME" in sql
        assert "CAST(json_array_elements(doc->'orders')->>'id' AS VARCHAR) AS ORDER_ID" in sql
