"""
Tests for the ViewGenerator class with JSON path-based view generation.
"""

import json
from pathlib import Path

import pytest

from sema4ai_docint.views import (
    BusinessSchema,
    DataFormat,
    PostgresAdapter,
    SchemaField,
    ViewGenerator,
)
from sema4ai_docint.views.views import ArrayPath


def normalize_whitespace(sql):
    """Normalize whitespace in SQL statements for comparison."""
    # Remove extra spaces and newlines
    return " ".join(sql.split())


def load_fixture(schema: str, filename: str):
    """Load a schema from the test-data directory."""
    f = Path(__file__).parent / "test-data" / schema / filename
    with open(f) as f:
        return json.load(f)


class TestViewGenerator:
    """Tests for the ViewGenerator class."""

    def test_view_generator_initialization(self):
        """Test that ViewGenerator can be initialized with different parameters."""
        # Default initialization
        generator = ViewGenerator()
        assert generator.source_table_name == "docs"
        assert generator.document_column_name == "doc"
        assert generator.datasource_name == "local_datasource"
        assert isinstance(generator.db_adapter, PostgresAdapter)

        # Custom initialization
        generator = ViewGenerator(
            source_table_name="custom_table",
            document_column_name="custom_doc",
            datasource_name="custom_datasource",
        )
        assert generator.source_table_name == "custom_table"
        assert generator.document_column_name == "custom_doc"
        assert generator.datasource_name == "custom_datasource"

        # With custom adapter
        adapter = PostgresAdapter()
        generator = ViewGenerator(db_adapter=adapter)
        assert generator.db_adapter is adapter

    def test_create_view(self):
        """Test view generation for a business schema with multiple entities."""
        # Load the schema and expected views
        schema_data = load_fixture("invoices", "business_schema.json")
        expected_views = load_fixture("invoices", "expected_business_views.json")
        expected_columns = load_fixture("invoices", "expected_columns.json")

        # Convert the schema data to a BusinessSchema object
        schema = BusinessSchema.from_dict(schema_data)

        # Generate views with test project name
        generator = ViewGenerator(project_name="test_project")
        views = generator.generate_views(schema, use_case_name="invoices")

        # Verify view names
        assert set([view.name for view in views]) == set(expected_views.keys())

        # Verify each view's SQL
        for view_name, expected_sql in expected_views.items():
            view = next((v for v in views if v.name == view_name), None)
            assert view is not None, f"View {view_name} not found"

            # Normalize whitespace for comparison
            actual_sql_normalized = normalize_whitespace(view.sql)
            expected_sql_normalized = normalize_whitespace(expected_sql)

            assert actual_sql_normalized == expected_sql_normalized, (
                f"View {view_name} does not match expected SQL"
            )

            assert len(view.columns) == len(expected_columns), (
                f"View {view_name} has {len(view.columns)} columns, "
                f"expected {len(expected_columns)}"
            )
            for expected_column in expected_columns:
                actual_column = next(
                    (c for c in view.columns if c.name == expected_column["name"]), None
                )
                assert actual_column is not None, (
                    f"Column {expected_column['name']} not found in view {view_name}"
                )
                assert expected_column["type"] == expected_column["type"], (
                    f"Column {expected_column['name']} does not match expected type"
                )

    def test_business_schema_with_multiple_entities(self):
        """Test view generation for a business schema with multiple entities."""
        # Load the schema and expected views
        schema_data = load_fixture("orders_payments", "business_schema.json")
        expected_views = load_fixture("orders_payments", "expected_business_views.json")

        # Convert the schema data to a BusinessSchema object
        schema = BusinessSchema.from_dict(schema_data)

        # Generate views with test project name
        generator = ViewGenerator(project_name="test_project")
        views = generator.generate_views(schema, use_case_name="orders_payments")

        # Check that the expected views are generated
        assert len(views) == 2

        # Verify view names
        assert set([v.name for v in views]) == set(expected_views.keys())

        # Verify each view's SQL
        for view_name, expected_sql in expected_views.items():
            view = next((v for v in views if v.name == view_name), None)
            assert view is not None, f"View {view_name} not found"

            # Normalize whitespace for comparison
            actual_sql_normalized = normalize_whitespace(view.sql)
            expected_sql_normalized = normalize_whitespace(expected_sql)

            assert actual_sql_normalized == expected_sql_normalized, (
                f"View {view_name} does not match expected SQL"
            )

    def test_group_paths_by_arrays(self):
        """Test the _group_paths_by_arrays method directly."""
        generator = ViewGenerator()

        # Simple schema with different arrays
        schema = BusinessSchema(
            fields=[
                SchemaField(path="field1", name="FIELD1", format=DataFormat(type="string")),
                SchemaField(
                    path="array1[]",
                    name="ARRAY1_ITEM",
                    format=DataFormat(type="string"),
                ),
                SchemaField(
                    path="array2[]",
                    name="ARRAY2_ITEM",
                    format=DataFormat(type="string"),
                ),
                SchemaField(
                    path="nested.array3[]",
                    name="ARRAY3_ITEM",
                    format=DataFormat(type="string"),
                ),
            ]
        )

        groups = generator._group_paths_by_arrays(schema)

        # Should create a group for each array type
        assert len(groups) == 3

        # Check that base paths are added to all groups
        assert any(field.name == "FIELD1" for field in groups["ARRAY1"])
        assert any(field.name == "FIELD1" for field in groups["ARRAY2"])
        assert any(field.name == "FIELD1" for field in groups["ARRAY3"])

    def test_parse_paths(self):
        """Test the _parse_paths method directly."""
        generator = ViewGenerator()

        # Paths with different types of expressions
        paths = [
            SchemaField(path="simple", name="SIMPLE", format=DataFormat(type="string")),
            SchemaField(
                path="nested.field",
                name="NESTED_FIELD",
                format=DataFormat(type="string"),
            ),
            SchemaField(path="array[]", name="ARRAY_ITEM", format=DataFormat(type="string")),
            SchemaField(
                path="nested.array[]",
                name="NESTED_ARRAY_ITEM",
                format=DataFormat(type="string"),
            ),
            SchemaField(
                path="array[].nested",
                name="NESTED_IN_ARRAY",
                format=DataFormat(type="string"),
            ),
        ]

        array_paths, select_expressions = generator._parse_paths(paths)

        # Should have select expressions for each field
        assert (
            len(select_expressions) == 3
        )  # Only non-array fields and array fields with nested paths

        # Verify the expressions
        expressions = [expr.json_path for expr in select_expressions]
        assert "doc->>'simple'" in expressions
        assert "doc->'nested'->>'field'" in expressions
        assert "json_array_elements(doc->'array')->>'nested'" in expressions

    def test_get_parent_path(self):
        """Test the _get_parent_path method directly."""
        generator = ViewGenerator()

        # Create a scenario with nested arrays using ArrayPath objects
        previous_arrays = [
            ArrayPath(path="doc->'array1'", alias="array1_elem"),
            ArrayPath(path="array1_elem->'nested'", alias="nested_elem"),
        ]

        # Test getting parent path for a child of a nested array
        parent_path = generator._get_parent_path("nested_elem->'items'", previous_arrays)

        # Should be updated to use the alias
        assert parent_path == "nested_elem->'items'"

        # Test getting parent path without previous arrays
        parent_path = generator._get_parent_path("doc->'array1'", [])

        # Should remain unchanged
        assert parent_path == "doc->'array1'"

    def test_array_paths_sorting_order(self):
        """Test that array paths are correctly built with nested json_array_elements."""
        generator = ViewGenerator()

        # Create a complex schema with nested arrays
        paths = [
            SchemaField(
                path="orders[].items[].sku",
                name="ITEM_SKU",
                format=DataFormat(type="string"),
            ),  # Deepest nesting (orders -> items)
            SchemaField(
                path="customer.name",
                name="CUSTOMER_NAME",
                format=DataFormat(type="string"),
            ),  # No array
            SchemaField(
                path="orders[].id", name="ORDER_ID", format=DataFormat(type="string")
            ),  # Single-level array
            SchemaField(
                path="orders[].items[].name",
                name="ITEM_NAME",
                format=DataFormat(type="string"),
            ),  # Another deep nesting
            SchemaField(
                path="payments[].id",
                name="PAYMENT_ID",
                format=DataFormat(type="string"),
            ),  # Different single-level array
            SchemaField(
                path="customer.id", name="CUSTOMER_ID", format=DataFormat(type="string")
            ),  # No array
        ]

        # Generate SQL for this group of paths
        sql, columns = generator._generate_view_for_group(
            "test_view", paths, use_case_name="test_use_case"
        )

        # Verify that json_array_elements are used correctly
        assert "json_array_elements(doc->'orders')" in sql
        assert "json_array_elements(json_array_elements(doc->'orders')->'items')" in sql
        assert "json_array_elements(doc->'payments')" in sql

        # Verify that the FROM clause is correct
        assert "FROM\n    `local_datasource`.docs AS docs" in sql

        # Verify that the view is created in mindsdb project
        assert "CREATE VIEW mindsdb.test_view AS (" in sql

        # Verify that the columns are correct
        assert len(columns) == 6
        assert columns[0].name == "ITEM_SKU"
        assert columns[0].type == "string"
        assert columns[1].name == "CUSTOMER_NAME"
        assert columns[1].type == "string"
        assert columns[2].name == "ORDER_ID"
        assert columns[2].type == "string"
        assert columns[3].name == "ITEM_NAME"
        assert columns[3].type == "string"
        assert columns[4].name == "PAYMENT_ID"
        assert columns[4].type == "string"
        assert columns[5].name == "CUSTOMER_ID"
        assert columns[5].type == "string"

    def test_abstract_type_system(self):
        """Test the abstract type system with attributes."""
        generator = ViewGenerator()

        # Schema with the abstract type system
        paths = [
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
                path="customer.age",
                name="CUSTOMER_AGE",
                format=DataFormat(type="integer"),
            ),
            SchemaField(
                path="customer.balance",
                name="CUSTOMER_BALANCE",
                format=DataFormat(type="number", attributes={"precision": 10, "scale": 2}),
            ),
            SchemaField(
                path="customer.joined",
                name="CUSTOMER_JOINED_DATE",
                format=DataFormat(type="date"),
            ),
            SchemaField(path="orders[].id", name="ORDER_ID", format=DataFormat(type="string")),
            SchemaField(
                path="orders[].total",
                name="ORDER_TOTAL",
                format=DataFormat(type="number", attributes={"precision": 8}),
            ),
        ]

        # Generate SQL for this group of paths
        sql, columns = generator._generate_view_for_group(
            "typed_view", paths, use_case_name="test_use_case"
        )

        # Verify abstract type casts are applied correctly using CAST syntax with uppercase types
        assert "CAST(doc->'customer'->>'id' AS VARCHAR(50)) AS CUSTOMER_ID" in sql
        assert "CAST(doc->'customer'->>'name' AS VARCHAR) AS CUSTOMER_NAME" in sql
        assert "TRY_TO_NUMBER(doc->'customer'->>'age') AS CUSTOMER_AGE" in sql
        assert "TRY_TO_NUMBER(doc->'customer'->>'balance') AS CUSTOMER_BALANCE" in sql
        assert "CAST(doc->'customer'->>'joined' AS DATE) AS CUSTOMER_JOINED_DATE" in sql
        assert "CAST(json_array_elements(doc->'orders')->>'id' AS VARCHAR) AS ORDER_ID" in sql
        assert "TRY_TO_NUMBER(json_array_elements(doc->'orders')->>'total') AS ORDER_TOTAL" in sql

        # Verify that the columns are correct
        assert len(columns) == 7
        assert columns[0].name == "CUSTOMER_ID"
        assert columns[0].type == "string"
        assert columns[1].name == "CUSTOMER_NAME"
        assert columns[1].type == "string"
        assert columns[2].name == "CUSTOMER_AGE"
        assert columns[2].type == "integer"
        assert columns[3].name == "CUSTOMER_BALANCE"
        assert columns[3].type == "number"
        assert columns[4].name == "CUSTOMER_JOINED_DATE"
        assert columns[4].type == "date"
        assert columns[5].name == "ORDER_ID"
        assert columns[5].type == "string"
        assert columns[6].name == "ORDER_TOTAL"
        assert columns[6].type == "number"

    def test_unsupported_schema_field_type(self):
        """Test that the DataFormat class rejects unsupported field types."""
        # Verify DataFormat validation during initialization
        with pytest.raises(ValueError, match="Invalid type: unsupported"):
            DataFormat(type="unsupported")

    def test_postgres_native_views(self):
        """Test that Postgres-native views are generated without MindsDB syntax."""
        # Create a simple schema
        schema = BusinessSchema(
            fields=[
                SchemaField(
                    path="customer_name", name="CUSTOMER_NAME", format=DataFormat(type="string")
                ),
                SchemaField(
                    path="total_amount", name="TOTAL_AMOUNT", format=DataFormat(type="number")
                ),
                SchemaField(path="order_date", name="ORDER_DATE", format=DataFormat(type="date")),
            ]
        )

        # Generate Postgres-native views (no datasource_name, no project_name)
        postgres_generator = ViewGenerator(
            source_table_name="documents",
            document_column_name="translated_content",
            datasource_name=None,
            project_name=None,
        )
        postgres_views = postgres_generator.generate_views(schema, use_case_name="test_model")

        # Verify Postgres view SQL
        assert len(postgres_views) == 1
        postgres_view = postgres_views[0]

        # Should NOT have MindsDB-specific syntax
        assert "`" not in postgres_view.sql, "Postgres views should not use backticks"
        assert ".documents" not in postgres_view.sql or "FROM\n    documents" in postgres_view.sql
        assert "CREATE VIEW TEST_MODEL_BASE_VIEW AS (" in postgres_view.sql
        assert "FROM\n    documents" in postgres_view.sql
        assert "WHERE\n    documents.data_model = 'test_model'" in postgres_view.sql

        # Generate MindsDB views (with datasource_name and project_name)
        mindsdb_generator = ViewGenerator(
            source_table_name="documents",
            document_column_name="translated_content",
            datasource_name="DocumentIntelligence",
            project_name="document_intelligence",
        )
        mindsdb_views = mindsdb_generator.generate_views(schema, use_case_name="test_model")

        # Verify MindsDB view SQL
        assert len(mindsdb_views) == 1
        mindsdb_view = mindsdb_views[0]

        # Should have MindsDB-specific syntax
        assert "`DocumentIntelligence`.documents" in mindsdb_view.sql
        assert "CREATE VIEW document_intelligence.TEST_MODEL_BASE_VIEW AS (" in mindsdb_view.sql
        assert "FROM\n    `DocumentIntelligence`.documents AS documents" in mindsdb_view.sql

        # Both views should have the same columns
        assert len(postgres_view.columns) == len(mindsdb_view.columns)
        for pg_col, mdb_col in zip(postgres_view.columns, mindsdb_view.columns, strict=True):
            assert pg_col.name == mdb_col.name
            assert pg_col.type == mdb_col.type
