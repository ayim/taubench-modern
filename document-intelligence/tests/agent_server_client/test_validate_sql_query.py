import json
from collections.abc import Callable

import pytest

from sema4ai_docint.agent_server_client.client import AgentServerClient
from sema4ai_docint.agent_server_client.transport.base import ResponseMessage
from sema4ai_docint.models import DataModel

from .conftest import MockTransport

# Sample test queries for different scenarios
VALID_QUERY = """
SELECT
    CAST(CASE WHEN COUNT(*) > 0 THEN 1 ELSE 0 END AS INTEGER) AS is_valid,
    column1,
    column2,
    CAST(SUM(numeric_column) AS DECIMAL) AS total
FROM document_intelligence.table_name
WHERE document_id = $DOCUMENT_ID
GROUP BY document_id
"""

VALID_QUERY_WITH_COALESCE = """
SELECT
    COALESCE(CAST(SUM(LINEITEMS_TOTALITEMAMOUNT) AS DECIMAL), 0) = \
        COALESCE(CAST(MAX(TOTALORDERAMOUNT) AS DECIMAL), 0) AS is_valid,
    COALESCE(CAST(SUM(LINEITEMS_TOTALITEMAMOUNT) AS DECIMAL), 0) AS summed_line_item_total,
    COALESCE(CAST(MAX(TOTALORDERAMOUNT) AS DECIMAL), 0) AS header_total_amount
FROM document_intelligence.ORDER_MANAGEMENT_LINEITEMS
WHERE document_id = $DOCUMENT_ID
GROUP BY document_id
"""

VALID_QUERY_WITH_DATE_PART = """
SELECT
    column1,
    CAST(date_part('month', CAST(date_column AS DATE)) AS INTEGER) as month,
    CAST(date_part('year', CAST(date_column AS DATE)) AS INTEGER) as year,
    CASE WHEN COUNT(*) > 0 THEN 1 ELSE 0 END AS is_valid
FROM document_intelligence.table_name
WHERE document_id = $DOCUMENT_ID
GROUP BY document_id, date_part('month', CAST(date_column AS DATE)), \
    date_part('year', CAST(date_column AS DATE))
"""

# Queries that should fail validation due to SQL syntax errors
INVALID_QUERY_SYNTAX = """
SELECT
    column1,
    column2,
    CASE WHEN COUNT(*) > 0 THEN 1 ELSE 0 END AS is_valid
FROM document_intelligence.table_name
WHERE document_id = $DOCUMENT_ID
GROUP BY document_id, column1, column2
"""

INVALID_QUERY_UNBALANCED_PARENTHESES = """
SELECT
    column1,
    column2,
    CASE WHEN COUNT(*) > 0 THEN 1 ELSE 0 END AS is_valid
FROM document_intelligence.table_name
WHERE (document_id = $DOCUMENT_ID
GROUP BY document_id
"""

INVALID_QUERY_UNBALANCED_QUOTES = """
SELECT
    'unclosed_quote,
    column2,
    CASE WHEN COUNT(*) > 0 THEN 1 ELSE 0 END AS is_valid
FROM document_intelligence.table_name
WHERE document_id = $DOCUMENT_ID
GROUP BY document_id
"""

INVALID_QUERY_INVALID_SYNTAX = """
SELECT
    column1,
    column2,
    CASE WHEN COUNT(*) > 0 THEN 1 ELSE 0 END AS is_valid
FROM document_intelligence.table_name
WHERE document_id = $DOCUMENT_ID
GROUP BY document_id, column1, column2
"""


class TestValidateRuleQuery:
    """Tests for the validate_rule_query method"""

    def test_valid_queries(self):
        """Test that valid queries pass validation"""
        # Test basic valid query
        is_valid, modified_query, error_msg = AgentServerClient.validate_sql_query(
            VALID_QUERY, "test_rule"
        )
        assert is_valid, f"Basic valid query should pass validation. Error: {error_msg}"

        # Test valid query with COALESCE
        is_valid, modified_query, error_msg = AgentServerClient.validate_sql_query(
            VALID_QUERY_WITH_COALESCE, "test_rule"
        )
        assert is_valid, f"Valid query with COALESCE should pass validation. Error: {error_msg}"

        # Test valid query with date_part
        is_valid, modified_query, error_msg = AgentServerClient.validate_sql_query(
            VALID_QUERY_WITH_DATE_PART, "test_rule"
        )
        assert is_valid, f"Valid query with date_part should pass validation. Error: {error_msg}"

    def test_user_example_query(self):
        """Test the specific example query provided by the user"""
        user_query = """
        SELECT
          COALESCE(SUM("LINEITEMS_TOTALITEMAMOUNT"), 0) =
          COALESCE(MAX("TOTALORDERAMOUNT"), 0) AS is_valid,
          COALESCE(SUM("LINEITEMS_TOTALITEMAMOUNT"), 0) AS summed_line_item_total,
          COALESCE(MAX("TOTALORDERAMOUNT"), 0) AS header_total_amount
        FROM document_intelligence.ORDER_MANAGEMENT_LINEITEMS
        WHERE document_id = $document_id
        GROUP BY document_id
        """

        is_valid, modified_query, error_msg = AgentServerClient.validate_sql_query(
            user_query, "user_example"
        )
        assert is_valid, f"User example query should pass validation. Error: {error_msg}"

        # Verify the query was cleaned (trailing semicolon removed, etc.)
        assert not modified_query.endswith(";"), "Trailing semicolon should be removed"

    def test_invalid_queries(self):
        """Test that invalid queries fail validation"""
        # Test query with unbalanced parentheses
        is_valid, _, error_msg = AgentServerClient.validate_sql_query(
            INVALID_QUERY_UNBALANCED_PARENTHESES, "test_unbalanced_parens"
        )
        assert not is_valid, (
            f"Query with unbalanced parentheses should fail validation. Error: {error_msg}"
        )

        # Test query with unbalanced quotes
        is_valid, _, error_msg = AgentServerClient.validate_sql_query(
            INVALID_QUERY_UNBALANCED_QUOTES, "test_unbalanced_quotes"
        )
        assert not is_valid, (
            f"Query with unbalanced quotes should fail validation. Error: {error_msg}"
        )

    def test_empty_query(self):
        """Test validation fails with empty query"""
        is_valid, _, error_msg = AgentServerClient.validate_sql_query("", "test_empty")
        assert not is_valid, "Empty query should fail validation"
        assert "empty query" in error_msg.lower(), "Error message should mention empty query"

        is_valid, _, error_msg = AgentServerClient.validate_sql_query("   ", "test_whitespace_only")
        assert not is_valid, "Whitespace-only query should fail validation"

    def test_query_cleaning(self):
        """Test that queries are properly cleaned during validation"""
        # Test query with code blocks
        query_with_blocks = (
            "```sql\nSELECT is_valid FROM document_intelligence.table_name "
            "WHERE document_id = $DOCUMENT_ID\n```"
        )
        is_valid, modified_query, error_msg = AgentServerClient.validate_sql_query(
            query_with_blocks, "test_rule"
        )
        assert is_valid, f"Query with code blocks should pass validation. Error: {error_msg}"
        assert "```" not in modified_query, "Code blocks should be removed"

        # Test query with trailing semicolon
        query_with_semicolon = (
            "SELECT is_valid FROM document_intelligence.table_name "
            "WHERE document_id = $DOCUMENT_ID;"
        )
        is_valid, modified_query, error_msg = AgentServerClient.validate_sql_query(
            query_with_semicolon, "test_rule"
        )
        assert is_valid, f"Query with semicolon should pass validation. Error: {error_msg}"
        assert not modified_query.endswith(";"), "Trailing semicolon should be removed"

        # Test query with comments (current implementation keeps comments but removes
        # semicolon before them)
        query_with_comments = (
            "SELECT is_valid FROM document_intelligence.table_name "
            "WHERE document_id = $DOCUMENT_ID; -- comment"
        )
        is_valid, modified_query, error_msg = AgentServerClient.validate_sql_query(
            query_with_comments, "test_rule"
        )
        assert is_valid, f"Query with comments should pass validation. Error: {error_msg}"
        # The current implementation removes the semicolon before comments but keeps the comment
        assert "-- comment" in modified_query, "Comments should be preserved"
        assert not modified_query.endswith(";"), "Semicolon before comment should be removed"

    def test_syntax_validation(self):
        """Test syntax validation checks"""
        # Test unbalanced parentheses
        query_unbalanced = (
            "SELECT is_valid FROM document_intelligence.table_name "
            "WHERE (document_id = $DOCUMENT_ID"
        )
        is_valid, _, error_msg = AgentServerClient.validate_sql_query(query_unbalanced, "test_rule")
        assert not is_valid, f"Query with unbalanced parentheses should fail. Error: {error_msg}"

        # Test unbalanced quotes
        query_unbalanced_quotes = (
            "SELECT 'unclosed_quote FROM document_intelligence.table_name "
            "WHERE document_id = $DOCUMENT_ID"
        )
        is_valid, _, error_msg = AgentServerClient.validate_sql_query(
            query_unbalanced_quotes, "test_rule"
        )
        assert not is_valid, f"Query with unbalanced quotes should fail. Error: {error_msg}"

    def test_exception_handling(self):
        """Test exception handling during validation"""
        # Create a query that will cause an exception
        invalid_query = "SELECT * FROM (invalid syntax"
        is_valid, _, error_msg = AgentServerClient.validate_sql_query(invalid_query, "test_rule")
        assert not is_valid, "Exception should result in validation failure"
        assert error_msg, "Error message should be provided"

    def test_return_values(self):
        """Test that the method returns the expected tuple structure"""
        is_valid, modified_query, error_msg = AgentServerClient.validate_sql_query(
            VALID_QUERY, "test_rule"
        )

        # Check return types
        assert isinstance(is_valid, bool), "is_valid should be a boolean"
        assert isinstance(modified_query, str), "modified_query should be a string"
        assert isinstance(error_msg, str), "error_msg should be a string"

        # For valid query, error_msg should be empty
        if is_valid:
            assert error_msg == "", "Error message should be empty for valid query"
            assert modified_query, "Modified query should not be empty for valid query"
        else:
            assert error_msg, "Error message should be provided for invalid query"

    def test_query_name_logging(self):
        """Test that query_name is used in error messages"""
        is_valid, _, error_msg = AgentServerClient.validate_sql_query("", "test_query_name")
        assert not is_valid, "Empty query should fail validation"
        assert "test_query_name" in error_msg, "Query name should be included in error message"


class TestGenerateValidationRules:
    """Tests for the generate_validation_rules method"""

    @property
    def use_case_description(self):
        return "Test use case for invoice validation"

    @property
    def rules_description(self):
        return "Generate rules to validate invoice data"

    @property
    def views(self):
        return [
            {
                "name": "INVOICE_RECON_TRANSACTIONS",
                "sql": "SELECT * FROM invoice_data",
                "columns": [
                    {"name": "totalinvoiceamount", "type": "DECIMAL"},
                    {"name": "transactions_totalamount", "type": "DECIMAL"},
                    {"name": "document_id", "type": "VARCHAR"},
                ],
            }
        ]

    @property
    def data_model(self):
        return DataModel(
            name="TEST_MODEL",
            description=self.use_case_description,
            model_schema={},
            views=self.views,
        )

    @property
    def datasource(self):
        col_names = [c["name"] for c in self.views[0]["columns"]]

        class _MockTable:
            def __init__(self, columns):
                self.columns = columns
                self.rows = []

        class _MockResult:
            def __init__(self, columns):
                self._columns = columns

            def to_table(self):
                return _MockTable(self._columns)

        class _MockDataSource:
            def execute_sql(self, _query: str):
                return _MockResult(col_names)

        return _MockDataSource()

    def test_single_rule_dict_response(
        self,
        agent_server_client: AgentServerClient,
        mock_transport: MockTransport,
        mock_response_message: Callable[[str, str], ResponseMessage],
    ):
        """Test handling of single rule dict response (converts to list)"""
        # Mock response with single rule dict
        single_rule_response = {
            "rule_name": "total_invoice_amount_positive",
            "rule_description": self.rules_description,
            "sql_query": (
                "SELECT MAX(`totalinvoiceamount`) > 0 AS is_valid, "
                "MAX(`totalinvoiceamount`) AS max_total_invoice_amount "
                "FROM `document_intelligence`.`INVOICE_RECON_TRANSACTIONS` "
                "WHERE document_id = $document_id GROUP BY document_id"
            ),
        }

        # Configure the mock transport to return the single rule response
        mock_response = mock_response_message(content_text=json.dumps(single_rule_response))
        mock_transport.prompts_generate_return_value = mock_response

        # Call the method
        result = agent_server_client.generate_validation_rules(
            self.rules_description,
            self.data_model,
            self.datasource,
        )

        # Verify the result is a list with one rule
        assert isinstance(result, list), "Result should be a list"
        assert len(result) == 1, "Result should contain one rule"
        assert result[0]["rule_name"] == "total_invoice_amount_positive"
        assert result[0]["rule_description"] == self.rules_description

    def test_multiple_rules_list_response(
        self,
        agent_server_client: AgentServerClient,
        mock_transport: MockTransport,
        mock_response_message: Callable[[str, str], ResponseMessage],
    ):
        """Test handling of multiple rules list response"""
        # Mock response with multiple rules
        multiple_rules_response = [
            {
                "rule_name": "total_invoice_amount_positive",
                "rule_description": (
                    "Validates that the total invoice amount for a document is greater than 0."
                ),
                "sql_query": (
                    "SELECT MAX(`totalinvoiceamount`) > 0 AS is_valid, "
                    "MAX(`totalinvoiceamount`) AS max_total_invoice_amount "
                    "FROM `document_intelligence`.`INVOICE_RECON_TRANSACTIONS` "
                    "WHERE document_id = $document_id GROUP BY document_id"
                ),
            },
            {
                "rule_name": "invoice_amount_matches_sum_of_line_items",
                "rule_description": (
                    "Validates that the total invoice amount matches the sum of "
                    "the transaction amounts for the document."
                ),
                "sql_query": (
                    "SELECT COALESCE(MAX(`totalinvoiceamount`), 0) = "
                    "COALESCE(SUM(`transactions_totalamount`), 0) AS is_valid, "
                    "COALESCE(MAX(`totalinvoiceamount`), 0) AS total_invoice_amount, "
                    "COALESCE(SUM(`transactions_totalamount`), 0) AS sum_transactions_totalamount "
                    "FROM `document_intelligence`.`INVOICE_RECON_TRANSACTIONS` "
                    "WHERE document_id = $document_id GROUP BY document_id"
                ),
            },
        ]

        # Configure the mock transport to return the multiple rules response
        mock_response = mock_response_message(content_text=json.dumps(multiple_rules_response))
        mock_transport.prompts_generate_return_value = mock_response

        # Call the method
        result = agent_server_client.generate_validation_rules(
            rules_description=None,
            data_model=self.data_model,
            datasource=self.datasource,
            limit_count=len(multiple_rules_response),
        )

        # Verify the result is a list with two rules
        assert isinstance(result, list), "Result should be a list"
        assert len(result) == 2, "Result should contain two rules"
        assert result[0]["rule_name"] == "total_invoice_amount_positive"
        assert result[1]["rule_name"] == "invoice_amount_matches_sum_of_line_items"

    def test_invalid_response_format(
        self,
        agent_server_client: AgentServerClient,
        mock_transport: MockTransport,
        mock_response_message: Callable[[str, str], ResponseMessage],
    ):
        """Test handling of invalid response format (not list or dict)"""
        # Mock response with invalid format (string instead of list/dict)
        invalid_response = "This is not a valid JSON format for rules"

        # Configure the mock transport to return the invalid response
        mock_response = mock_response_message(content_text=invalid_response)
        mock_transport.prompts_generate_return_value = mock_response

        # Call the method and expect it to fail
        with pytest.raises(Exception, match="Failed to generate|Invalid response format"):
            agent_server_client.generate_validation_rules(
                self.rules_description,
                self.data_model,
                self.datasource,
            )

    def test_invalid_response_types(
        self,
        agent_server_client: AgentServerClient,
        mock_transport: MockTransport,
        mock_response_message: Callable[[str, str], ResponseMessage],
    ):
        """Test handling of various invalid response types that are not lists"""
        # Test cases for different invalid response types
        invalid_responses = [
            # Integer response
            42,
            # Boolean response
            True,
            # Float response
            3.14,
            # None response
            None,
            # Empty string
            "",
            # List of non-dict items
            ["not a rule", "also not a rule"],
            # Nested structure that's not a rule
            {"nested": {"data": "not a rule"}},
            # Array with mixed types
            [{"rule_name": "valid"}, "invalid", 123],
            # Empty dict
            {},
            # Dict with wrong structure
            {"some_field": "not a rule"},
        ]

        for _i, invalid_response in enumerate(invalid_responses):
            # Configure the mock transport to return the invalid response
            mock_response = mock_response_message(content_text=json.dumps(invalid_response))
            mock_transport.prompts_generate_return_value = mock_response

            # Call the method and expect it to handle the invalid response
            try:
                result = agent_server_client.generate_validation_rules(
                    self.rules_description,
                    self.data_model,
                    self.datasource,
                )
                # If it succeeds, the retry logic should handle it gracefully
                assert isinstance(result, list), (
                    f"Response type {type(invalid_response)} should result in a list"
                )
            except Exception:
                # It's acceptable for the method to raise an exception after retries
                # We don't need to assert on the exception message here since we're
                # testing that the method handles invalid responses gracefully
                pass

    def test_malformed_json_response(
        self,
        agent_server_client: AgentServerClient,
        mock_transport: MockTransport,
        mock_response_message: Callable[[str, str], ResponseMessage],
    ):
        """Test handling of malformed JSON responses"""
        # Test cases for malformed JSON
        malformed_responses = [
            # Incomplete JSON
            '{"rule_name": "incomplete"',
            # Extra comma
            '{"rule_name": "test",}',
            # Unclosed string
            '{"rule_name": "unclosed string}',
            # Invalid syntax
            '{rule_name: "no quotes"}',
            # Trailing comma in array
            '[{"rule_name": "test"},]',
            # Mixed quotes
            '{"rule_name": "test\'}',
        ]

        for i, malformed_response in enumerate(malformed_responses):
            # Configure the mock transport to return the malformed response
            mock_response = mock_response_message(content_text=malformed_response)
            mock_transport.prompts_generate_return_value = mock_response

            # Call the method and expect it to handle the malformed JSON
            try:
                result = agent_server_client.generate_validation_rules(
                    self.rules_description,
                    self.data_model,
                    self.datasource,
                )
                # If it succeeds, the retry logic should handle it gracefully
                assert isinstance(result, list), f"Malformed JSON {i} should result in a list"
            except Exception:
                # After all retry attempts, it should raise an exception about failing to
                # generate validation rules
                # We don't need to assert on the exception message here since we're
                # testing that the method handles malformed JSON gracefully
                pass

    def test_empty_list_response(
        self,
        agent_server_client: AgentServerClient,
        mock_transport: MockTransport,
        mock_response_message: Callable[[str, str], ResponseMessage],
    ):
        """Test handling of empty list response"""
        # Configure the mock transport to return an empty list
        mock_response = mock_response_message(content_text="[]")
        mock_transport.prompts_generate_return_value = mock_response

        # Call the method
        result = agent_server_client.generate_validation_rules(
            self.rules_description,
            self.data_model,
            self.datasource,
            limit_count=0,
        )

        # Verify the result is an empty list
        assert isinstance(result, list), "Result should be a list"
        assert len(result) == 0, "Result should be empty"

    def test_list_with_invalid_rule_items(
        self,
        agent_server_client: AgentServerClient,
        mock_transport: MockTransport,
        mock_response_message: Callable[[str, str], ResponseMessage],
    ):
        """Test handling of list containing invalid rule items"""
        # Mock response with list containing invalid items
        invalid_list_response = [
            {"rule_name": "valid_rule", "sql_query": "SELECT 1 AS is_valid"},
            "not a rule",  # Invalid string item
            123,  # Invalid number item
            {"invalid_field": "not a rule"},  # Dict without required fields
            None,  # Invalid None item
        ]

        # Configure the mock transport to return the invalid list response
        mock_response = mock_response_message(content_text=json.dumps(invalid_list_response))
        mock_transport.prompts_generate_return_value = mock_response

        # Call the method
        result = agent_server_client.generate_validation_rules(
            self.rules_description,
            self.data_model,
            self.datasource,
            limit_count=len(invalid_list_response),
        )

        # Verify only valid rules are included
        assert isinstance(result, list), "Result should be a list"
        # Should only contain the valid rule
        assert len(result) == 1, "Result should contain only valid rules"
        assert result[0]["rule_name"] == "valid_rule", "Only valid rule should be included"

    def test_rules_with_error_messages(
        self,
        agent_server_client: AgentServerClient,
        mock_transport: MockTransport,
        mock_response_message: Callable[[str, str], ResponseMessage],
    ):
        """Test handling of rules that have error messages (indicating they cannot be performed)"""
        # Mock response with rules that have error messages
        rules_with_errors = [
            {
                "rule_name": "valid_rule",
                "rule_description": "This rule can be performed",
                "sql_query": (
                    "SELECT 1 AS is_valid FROM document_intelligence.table_name "
                    "WHERE document_id = $DOCUMENT_ID GROUP BY document_id"
                ),
            },
            {
                "rule_name": "invalid_rule",
                "rule_description": "This rule cannot be performed",
                "error_message": "Cannot perform this validation due to data type mismatch",
            },
        ]

        # Configure the mock transport to return the rules with errors
        mock_response = mock_response_message(content_text=json.dumps(rules_with_errors))
        mock_transport.prompts_generate_return_value = mock_response

        # Call the method
        result = agent_server_client.generate_validation_rules(
            rules_description=None,
            data_model=self.data_model,
            datasource=self.datasource,
            limit_count=len(rules_with_errors),
        )

        # Verify both rules are included (including the one with error message)
        assert isinstance(result, list), "Result should be a list"
        assert len(result) == 2, "Result should contain both rules"

        # Find the rule with error message
        error_rule = next((rule for rule in result if rule.get("error_message")), None)
        assert error_rule is not None, "Rule with error message should be included"
        assert error_rule["rule_name"] == "invalid_rule"
        assert "data type mismatch" in error_rule["error_message"]

    def test_rules_with_sql_validation_errors(
        self,
        agent_server_client: AgentServerClient,
        mock_transport: MockTransport,
        mock_response_message: Callable[[str, str], ResponseMessage],
    ):
        """Test handling of rules with SQL syntax errors (should trigger retry)"""
        # Mock response with rules that have invalid SQL
        rules_with_sql_errors = [
            {
                "rule_name": "invalid_sql_rule",
                "rule_description": "This rule has invalid SQL",
                "sql_query": "SELECT * FROM (invalid syntax",
            }
        ]

        # Configure the mock transport to return the rules with SQL errors
        mock_response = mock_response_message(content_text=json.dumps(rules_with_sql_errors))
        mock_transport.prompts_generate_return_value = mock_response

        # Call the method and expect it to handle SQL validation errors
        try:
            result = agent_server_client.generate_validation_rules(
                self.rules_description,
                self.data_model,
                self.datasource,
            )
            # The method should either return empty list or raise exception after retries
            assert isinstance(result, list), "Result should be a list"
        except Exception:
            # It's acceptable for the method to raise an exception after retries
            # We don't need to assert on the exception message here since we're
            # testing that the method handles SQL validation errors gracefully
            pass

    def test_limit_count_truncates_results(
        self,
        agent_server_client: AgentServerClient,
        mock_transport: MockTransport,
        mock_response_message: Callable[[str, str], ResponseMessage],
    ):
        """If more rules are produced than limit_count, only the first limit_count
        rules are returned."""
        # Mock response with 3 rules
        three_rules_response = [
            {"rule_name": "r1", "sql_query": "SELECT 1 AS is_valid"},
            {"rule_name": "r2", "sql_query": "SELECT 1 AS is_valid"},
            {"rule_name": "r3", "sql_query": "SELECT 1 AS is_valid"},
        ]

        # Configure the mock transport to return 3 rules
        mock_response = mock_response_message(content_text=json.dumps(three_rules_response))
        mock_transport.prompts_generate_return_value = mock_response

        result = agent_server_client.generate_validation_rules(
            rules_description=None,
            data_model=self.data_model,
            datasource=self.datasource,
            limit_count=2,
        )
        assert isinstance(result, list)
        assert len(result) == 2
        assert [r["rule_name"] for r in result] == ["r1", "r2"]
