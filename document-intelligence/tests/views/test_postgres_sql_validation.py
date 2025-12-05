"""
Tests to validate that generated Postgres SQL is syntactically correct.
"""

import json
from pathlib import Path

import pytest
from sema4ai.data import DataSource

from sema4ai_docint.views import (
    BusinessSchema,
    DataFormat,
    SchemaField,
    ViewGenerator,
)


def load_fixture(schema: str, filename: str):
    """Load a schema from the test-data directory."""
    f = Path(__file__).parent / "test-data" / schema / filename
    with open(f) as f:
        return json.load(f)


class TestPostgresSQLValidation:
    """Tests to validate Postgres SQL syntax."""

    def test_postgres_sql_no_duplicate_create_view(self):
        """Test that generated Postgres SQL doesn't have duplicate CREATE VIEW statements."""
        schema = BusinessSchema(
            fields=[
                SchemaField(
                    path="customer_name", name="CUSTOMER_NAME", format=DataFormat(type="string")
                ),
                SchemaField(
                    path="total_amount", name="TOTAL_AMOUNT", format=DataFormat(type="number")
                ),
            ]
        )

        generator = ViewGenerator(
            source_table_name="documents",
            document_column_name="translated_content",
            datasource_name=None,
            project_name=None,
        )
        views = generator.generate_views(schema, use_case_name="test_model")

        assert len(views) > 0
        for view in views:
            # Count occurrences of "CREATE VIEW" - should be exactly 1
            create_view_count = view.sql.count("CREATE VIEW")
            assert create_view_count == 1, (
                f"View {view.name} has {create_view_count} CREATE VIEW statements. "
                f"Expected exactly 1. SQL:\n{view.sql}"
            )

    def test_postgres_sql_structure(self):
        """Test that Postgres SQL has the correct structure."""
        schema = BusinessSchema(
            fields=[
                SchemaField(
                    path="customer_name", name="CUSTOMER_NAME", format=DataFormat(type="string")
                ),
                SchemaField(
                    path="total_amount", name="TOTAL_AMOUNT", format=DataFormat(type="number")
                ),
            ]
        )

        generator = ViewGenerator(
            source_table_name="documents",
            document_column_name="translated_content",
            datasource_name=None,
            project_name=None,
        )
        views = generator.generate_views(schema, use_case_name="test_model")

        assert len(views) > 0
        for view in views:
            sql = view.sql

            # Should start with CREATE VIEW
            assert sql.strip().startswith("CREATE VIEW"), (
                f"View {view.name} SQL should start with 'CREATE VIEW'. Got: {sql[:50]}"
            )

            # Should contain AS keyword
            assert " AS " in sql or " AS\n" in sql or " AS(" in sql, (
                f"View {view.name} SQL should contain 'AS'. SQL:\n{sql}"
            )

            # Should contain SELECT
            assert "SELECT" in sql.upper(), (
                f"View {view.name} SQL should contain SELECT. SQL:\n{sql}"
            )

            # Should contain FROM
            assert "FROM" in sql.upper(), f"View {view.name} SQL should contain FROM. SQL:\n{sql}"

            # Should end with semicolon
            assert sql.strip().endswith(";"), (
                f"View {view.name} SQL should end with semicolon. Got: {sql[-20:]}"
            )

            # Should NOT have MindsDB-specific syntax
            assert "`" not in sql, (
                f"View {view.name} SQL should not contain backticks (MindsDB syntax). SQL:\n{sql}"
            )

            # Should NOT have datasource prefix in FROM clause
            assert "FROM\n    documents" in sql or "FROM documents" in sql, (
                f"View {view.name} SQL should have direct table reference in FROM. SQL:\n{sql}"
            )

    def test_postgres_sql_balanced_parentheses(self):
        """Test that Postgres SQL has balanced parentheses."""
        schema = BusinessSchema(
            fields=[
                SchemaField(
                    path="customer_name", name="CUSTOMER_NAME", format=DataFormat(type="string")
                ),
                SchemaField(
                    path="total_amount", name="TOTAL_AMOUNT", format=DataFormat(type="number")
                ),
            ]
        )

        generator = ViewGenerator(
            source_table_name="documents",
            document_column_name="translated_content",
            datasource_name=None,
            project_name=None,
        )
        views = generator.generate_views(schema, use_case_name="test_model")

        for view in views:
            sql = view.sql
            open_count = sql.count("(")
            close_count = sql.count(")")

            assert open_count == close_count, (
                f"View {view.name} has unbalanced parentheses: "
                f"{open_count} opening, {close_count} closing. SQL:\n{sql}"
            )

    def test_postgres_sql_no_nested_create_view(self):
        """Test that Postgres SQL doesn't nest CREATE VIEW statements."""
        schema = BusinessSchema(
            fields=[
                SchemaField(
                    path="customer_name", name="CUSTOMER_NAME", format=DataFormat(type="string")
                ),
            ]
        )

        generator = ViewGenerator(
            source_table_name="documents",
            document_column_name="translated_content",
            datasource_name=None,
            project_name=None,
        )
        views = generator.generate_views(schema, use_case_name="test_model")

        for view in views:
            sql = view.sql

            # Check that we don't have CREATE VIEW inside CREATE VIEW
            # Split by CREATE VIEW and check the parts
            parts = sql.split("CREATE VIEW")
            assert len(parts) == 2, (
                f"View {view.name} should have exactly one CREATE VIEW statement. "
                f"Found {len(parts) - 1}. SQL:\n{sql}"
            )

            # The part after CREATE VIEW should not contain another CREATE VIEW
            after_create = parts[1]
            assert "CREATE VIEW" not in after_create, (
                f"View {view.name} has nested CREATE VIEW statements. SQL:\n{sql}"
            )

    def test_postgres_sql_valid_view_name(self):
        """Test that Postgres SQL uses valid view names."""
        schema = BusinessSchema(
            fields=[
                SchemaField(
                    path="customer_name", name="CUSTOMER_NAME", format=DataFormat(type="string")
                ),
            ]
        )

        generator = ViewGenerator(
            source_table_name="documents",
            document_column_name="translated_content",
            datasource_name=None,
            project_name=None,
        )
        views = generator.generate_views(schema, use_case_name="test_model")

        for view in views:
            sql = view.sql

            # View name should be uppercase and contain only valid characters
            # Extract view name from CREATE VIEW statement
            create_view_part = sql.split("CREATE VIEW")[1].split(" AS")[0].strip()
            view_name = create_view_part.split()[0] if create_view_part.split() else ""

            assert view_name == view.name, (
                f"View name in SQL ({view_name}) doesn't match view.name ({view.name}). SQL:\n{sql}"
            )

            # View name should be valid PostgreSQL identifier (uppercase, alphanumeric, underscore)
            assert view_name.isupper() or view_name.replace("_", "").isalnum(), (
                f"View name {view_name} should be uppercase alphanumeric with underscores. "
                f"SQL:\n{sql}"
            )

    @pytest.mark.integration
    def test_postgres_sql_executable(self, postgres_datasource: DataSource):
        """Test that generated Postgres SQL can actually be executed by Postgres."""
        # First, ensure the documents table exists
        try:
            postgres_datasource.native_query(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    id VARCHAR PRIMARY KEY,
                    document_name VARCHAR,
                    document_layout VARCHAR,
                    translated_content JSONB,
                    data_model VARCHAR
                )
                """,
                {},
            )
        except Exception:
            pass  # Table might already exist

        schema = BusinessSchema(
            fields=[
                SchemaField(
                    path="customer_name", name="CUSTOMER_NAME", format=DataFormat(type="string")
                ),
                SchemaField(
                    path="total_amount", name="TOTAL_AMOUNT", format=DataFormat(type="number")
                ),
            ]
        )

        generator = ViewGenerator(
            source_table_name="documents",
            document_column_name="translated_content",
            datasource_name=None,
            project_name=None,
        )
        views = generator.generate_views(schema, use_case_name="test_model")

        for view in views:
            sql = view.sql

            # Drop view if it exists
            try:
                postgres_datasource.native_query(f"DROP VIEW IF EXISTS {view.name} CASCADE", {})
            except Exception:
                pass  # View might not exist

            # Try to create the view - if it fails with a syntax error, that's a problem
            try:
                # Use CREATE OR REPLACE to avoid errors if view exists
                create_sql = sql.replace("CREATE VIEW", "CREATE OR REPLACE VIEW", 1)
                postgres_datasource.native_query(create_sql, {})
            except Exception as e:
                error_msg = str(e).lower()
                # If it's a syntax error, that's a problem
                if "syntax" in error_msg or "parse" in error_msg:
                    pytest.fail(f"View {view.name} has invalid SQL syntax. Error: {e}\nSQL:\n{sql}")
                # Other errors (like missing table) are OK for syntax validation
                # but we should log them
                if "does not exist" not in error_msg and "relation" not in error_msg:
                    # Re-raise if it's not a "relation doesn't exist" error
                    raise

            # Clean up - drop the view
            try:
                postgres_datasource.native_query(f"DROP VIEW IF EXISTS {view.name} CASCADE", {})
            except Exception:
                pass  # Ignore cleanup errors

    def test_create_postgres_views_method(self):
        """Test that create_postgres_views method works correctly with mock datasource."""
        schema = BusinessSchema(
            fields=[
                SchemaField(
                    path="customer_name", name="CUSTOMER_NAME", format=DataFormat(type="string")
                ),
            ]
        )

        generator = ViewGenerator(
            source_table_name="documents",
            document_column_name="translated_content",
            datasource_name=None,
            project_name=None,
        )
        views = generator.generate_views(schema, use_case_name="test_model")

        # Create a mock datasource that records queries
        class MockDataSource:
            def __init__(self):
                self.queries = []

            def native_query(self, sql, params):
                self.queries.append((sql, params))

        mock_datasource = MockDataSource()

        # Call create_postgres_views
        ViewGenerator.create_postgres_views(views, mock_datasource)

        # Verify that queries were executed
        assert len(mock_datasource.queries) == len(views), (
            f"Expected {len(views)} queries, got {len(mock_datasource.queries)}"
        )

        # Verify each query is valid SQL
        for i, (sql, params) in enumerate(mock_datasource.queries):
            view = views[i]

            # SQL should match the view's SQL exactly
            assert sql == view.sql, (
                f"Query {i} SQL doesn't match view SQL. Expected:\n{view.sql}\nGot:\n{sql}"
            )

            # Should have exactly one CREATE VIEW
            assert sql.count("CREATE VIEW") == 1, (
                f"Query {i} should have exactly one CREATE VIEW. SQL:\n{sql}"
            )

            # Params should be empty dict
            assert params == {}, f"Query {i} should have empty params, got {params}"

    def test_postgres_sql_with_complex_schema(self):
        """Test Postgres SQL validation with a complex schema (arrays, nested objects)."""
        schema_data = load_fixture("invoices", "business_schema.json")
        schema = BusinessSchema.from_dict(schema_data)

        generator = ViewGenerator(
            source_table_name="documents",
            document_column_name="translated_content",
            datasource_name=None,
            project_name=None,
        )
        views = generator.generate_views(schema, use_case_name="invoices")

        assert len(views) > 0

        for view in views:
            sql = view.sql

            # Basic structure checks
            assert sql.count("CREATE VIEW") == 1, (
                f"View {view.name} should have exactly one CREATE VIEW. SQL:\n{sql}"
            )

            # Balanced parentheses
            assert sql.count("(") == sql.count(")"), (
                f"View {view.name} has unbalanced parentheses. SQL:\n{sql}"
            )

            # Should end with semicolon
            assert sql.strip().endswith(";"), (
                f"View {view.name} should end with semicolon. SQL:\n{sql}"
            )

            # Should not have MindsDB syntax
            assert "`" not in sql, f"View {view.name} should not contain backticks. SQL:\n{sql}"
