"""
Integration tests for generate_natural_language_query_on_views using parameterized test data.
"""

import json
from pathlib import Path

import pytest

from sema4ai_docint.agent_server_client.models import Column, View
from sema4ai_docint.models.data_model import DataModel

from .nl_to_sql_utils import (
    COMPARISON_MODE_EXACT,
    evaluate_sql_results,
)


@pytest.mark.nl2sql_eval
class TestNLToSQL:
    """Unified test class for NL-to-SQL functionality."""

    @pytest.fixture(autouse=True)
    def check_eval_marker(self, request):
        """Check if eval marker is being used, skip if not."""
        if "nl2sql_eval" not in request.config.getoption("-m", default=""):
            pytest.skip("This test requires the nl2sql_eval marker to run")

    @pytest.fixture
    def setup_test_data(self, test_case: str, postgres, request, check_eval_marker):
        """Setup test-specific data for each test case."""
        conn, props = postgres

        # Load test case data
        test_case_dir = Path(__file__).parent / "test-data" / "nl_to_sql" / test_case
        views_file = test_case_dir / "views.json"
        test_data_file = test_case_dir / "test_data.csv"

        # Load views configuration
        with open(views_file) as f:
            views_config = json.load(f)

        # Create tables based on views configuration
        with conn.cursor() as cursor:
            for view_config in views_config:
                table_name = view_config["name"]

                # Create table based on columns
                columns_def = []
                for col in view_config["columns"]:
                    col_type = col["type"]
                    if col_type == "decimal":
                        col_type = "DECIMAL(10,2)"
                    elif col_type == "date":
                        col_type = "DATE"
                    else:
                        col_type = "TEXT"
                    columns_def.append(f"{col['name']} {col_type}")

                create_table_sql = f"""
                    CREATE TABLE IF NOT EXISTS {table_name} (
                        {", ".join(columns_def)}
                    )
                """
                cursor.execute(create_table_sql)

                # Clear any existing data
                cursor.execute(f"TRUNCATE TABLE {table_name} CASCADE")

                # Load data from CSV
                if test_data_file.exists():
                    with open(test_data_file) as f:
                        # Skip header
                        next(f)
                        for line in f:
                            values = line.strip().split(",")
                            placeholders = ", ".join(["%s"] * len(values))
                            insert_sql = f"INSERT INTO {table_name} VALUES ({placeholders})"
                            cursor.execute(insert_sql, values)

        yield conn

        # Cleanup after test
        with conn.cursor() as cursor:
            for view_config in views_config:
                table_name = view_config["name"]
                cursor.execute(f"DROP TABLE IF EXISTS {table_name} CASCADE")

    @pytest.mark.parametrize(
        "test_case",
        ["test_case_1", "test_case_2", "test_case_3", "test_case_4", "test_case_5"],
    )
    def test_generate_nl_query_on_views(
        self,
        test_case,
        setup_test_data,
        postgres_datasource,
        mindsdb_db_name,
        agent_client,
    ):
        """Test NL query generation for the specified test case."""

        # Load test case data
        test_case_dir = Path(__file__).parent / "test-data" / "nl_to_sql" / test_case
        queries_file = test_case_dir / "queries.json"

        # Load all queries for this test case
        with open(queries_file) as f:
            test_data = json.load(f)

        # Load views configuration
        views_file = test_case_dir / "views.json"
        with open(views_file) as f:
            views_config = json.load(f)

        # Create View objects
        views = []
        for view_config in views_config:
            view = View(
                name=view_config["name"],
                sql="unused",  # we don't use CREATE VIEW statements in NL2SQL
                columns=[Column(**col) for col in view_config["columns"]],
            )
            views.append(view)

        # Gather view reference data
        view_reference_data = []
        for view in views:
            # Get sample data from the view
            sample_data_query = f"SELECT * FROM {mindsdb_db_name}.{view.name} LIMIT 10"
            sample_data = postgres_datasource.execute_sql(sample_data_query)

            # Extract column information from the sample data
            sample_data_list = []

            if sample_data and sample_data.to_table().columns:
                # Get column names
                column_names = sample_data.to_table().columns

                # Convert all sample data rows to dictionaries
                if sample_data.to_table().rows:
                    for row in sample_data.to_table().rows:
                        sample_data_list.append(dict(zip(column_names, row, strict=False)))

            view_reference_data.append(
                {
                    "name": view.name,
                    "columns": column_names,
                    "sample_data": sample_data_list,
                }
            )

        print(f"Testing category: {test_data['category']}")

        # Test each query in the test case
        for query in test_data["queries"]:
            print(f"  Testing query: {query['name']}")

            # Generate SQL from NL query
            sql = agent_client.generate_natural_language_query_on_views(
                query["nl_query"],
                [view.model_dump() for view in views],
                database_name=mindsdb_db_name,
                document_id=query.get("document_id"),
                view_reference_data=view_reference_data,
            )
            print(f"  NL Query: {query['nl_query']}")
            print(f"  Generated SQL: {sql}")

            # Validate GROUP BY clause if required
            if query.get("validate_group_by"):
                sql_upper = sql.upper()
                assert "GROUP BY" in sql_upper, (
                    f"Query '{query['name']}' requires GROUP BY but none was generated:\n"
                )

                if query.get("required_group_by_columns"):
                    for col in query["required_group_by_columns"]:
                        group_by_pos = sql_upper.find("GROUP BY")
                        after_group_by = sql[group_by_pos:]
                        assert col.lower() in after_group_by.lower(), (
                            f"Query '{query['name']}' requires '{col}' in GROUP BY:\n"
                        )

            # Execute the generated SQL
            results = postgres_datasource.execute_sql(sql)
            actual_result = results.to_dict_list()

            # Compare results using enhanced evaluation
            comparison_result = evaluate_sql_results(
                expected_result=query["expected_result"],
                actual_result=actual_result,
                comparison_mode=query.get("comparison_mode", COMPARISON_MODE_EXACT),
                grouping_columns=query.get("grouping_columns"),
            )

            # Assert with detailed error message
            assert comparison_result["success"], (
                f"Query '{query['name']}' in category '{test_data['category']}' failed:\n"
                f"NL Query: {query['nl_query']}\n"
                f"Generated SQL: {sql}\n"
                f"Differences: {comparison_result['differences']}\n"
                f"Stats: {comparison_result['comparison_stats']}"
            )

    @pytest.mark.parametrize(
        "test_case",
        ["test_case_6", "test_case_7", "test_case_8", "test_case_9", "test_case_10"],
    )
    def test_generate_validation_rules(
        self,
        test_case,
        setup_test_data,
        postgres_datasource,
        mindsdb_db_name,
        agent_client,
    ):
        """Test validation rules generation for the specified test case."""

        # Load test case data
        test_case_dir = Path(__file__).parent / "test-data" / "nl_to_sql" / test_case
        validation_rules_file = test_case_dir / "validation_rules.json"

        # Load validation rules configuration
        with open(validation_rules_file) as f:
            test_data = json.load(f)

        # Load views configuration
        views_file = test_case_dir / "views.json"
        with open(views_file) as f:
            views_config = json.load(f)

        # Create View objects
        views = []
        for view_config in views_config:
            view = View(
                name=view_config["name"],
                sql="unused",  # we don't use CREATE VIEW statements in NL2SQL
                columns=[Column(**col) for col in view_config["columns"]],
            )
            views.append(view)

        # Gather view reference data
        view_reference_data = []
        for view in views:
            # Get sample data from the view
            sample_data_query = f"SELECT * FROM {mindsdb_db_name}.{view.name} LIMIT 10"
            sample_data = postgres_datasource.execute_sql(sample_data_query)

            # Extract column information from the sample data
            sample_data_list = []

            if sample_data and sample_data.to_table().columns:
                # Get column names
                column_names = sample_data.to_table().columns

                # Convert all sample data rows to dictionaries
                if sample_data.to_table().rows:
                    for row in sample_data.to_table().rows:
                        sample_data_list.append(dict(zip(column_names, row, strict=False)))

            view_reference_data.append(
                {
                    "name": view.name,
                    "columns": column_names,
                    "sample_data": sample_data_list,
                }
            )

        print(f"  Use case: {test_data['use_case_description']}")
        print(f"  Rules description: {test_data['rules_description']}")

        # Create DataModel from views and test data
        data_model = DataModel(
            name="test_data_model",
            description=test_data["use_case_description"],
            model_schema={},  # Not used for validation rules generation
            views=[view.model_dump() for view in views],
        )

        # Generate validation rules
        rules = agent_client.generate_validation_rules(
            rules_description=test_data["rules_description"],
            data_model=data_model,
            datasource=postgres_datasource,
            database_name=mindsdb_db_name,
        )

        # For now, we expect only one rule as per the test case design
        assert len(rules) == 1, f"Expected 1 rule, got {len(rules)}"

        rule = rules[0]
        print(f"  Rule name: {rule['rule_name']}")
        print(f"  Rule description: {rule['rule_description']}")
        print(f"  Generated SQL: {rule['sql_query']}")

        # Execute the generated SQL
        sql = rule["sql_query"]
        sql = sql.replace("$document_id", f"'{test_data['document_id']}'")
        print(f"  Executing SQL: {sql}")

        results = postgres_datasource.execute_sql(sql)
        actual_result = results.to_dict_list()

        # Compare results using enhanced evaluation
        comparison_result = evaluate_sql_results(
            expected_result=test_data["expected_result"],
            actual_result=actual_result,
            comparison_mode=test_data.get("comparison_mode", COMPARISON_MODE_EXACT),
        )

        # Assert with detailed error message
        assert comparison_result["success"], (
            f"Validation rule '{rule['rule_name']}' failed:\n"
            f"Use case: {test_data['use_case_description']}\n"
            f"Rules description: {test_data['rules_description']}\n"
            f"Generated SQL: {sql}\n"
            f"Differences: {comparison_result['differences']}\n"
            f"Stats: {comparison_result['comparison_stats']}"
        )
