"""Unit tests for SQL parameter utilities."""

import pytest

from agent_platform.core.semantic_data_model.types import QueryParameter
from agent_platform.core.semantic_data_model.utils import (
    extract_parameters_from_sql,
)
from agent_platform.server.data_frames.sql_parameter_utils import (
    _extract_column_and_table_from_node,
    substitute_sql_parameters_safe,
)


class TestExtractParametersFromSQLValidation:
    """Generic validation and error handling tests for extract_parameters_from_sql.

    These tests verify error conditions and edge cases that are dialect-agnostic.
    Dialect-specific SQL pattern tests should be in test_sql_parameter_utils_<dialect>.py files.
    """

    def test_invalid_sql_raises_error(self):
        """Test that invalid SQL raises ValueError."""
        sql = "SELECT * FROM WHERE invalid syntax"
        with pytest.raises(ValueError, match="Failed to parse SQL query"):
            extract_parameters_from_sql(sql, dialect="postgres")

    def test_empty_sql_raises_error(self):
        """Test that empty SQL raises ValueError."""
        sql = ""
        with pytest.raises(ValueError, match="Failed to parse SQL query"):
            extract_parameters_from_sql(sql, dialect="postgres")

    def test_parameters_in_deep_nested_subqueries(self):
        """Test parameter extraction in deeply nested subqueries (10 levels).

        This test verifies that find_all() can handle deep AST structures
        without recursion issues. The query has 11 parameters total:
        1 user_id + 10 params (param0 through param9).
        """
        # Create a query with 10 nested subqueries
        nested_levels = 10
        sql = "SELECT * FROM users WHERE id = :user_id"
        for i in range(nested_levels):
            sql = f"SELECT * FROM ({sql}) AS subq{i} WHERE col{i} = :param{i}"

        result = extract_parameters_from_sql(sql, dialect="postgres")

        # Should find all 11 parameters (user_id + param0 through param9)
        expected_params = ["user_id"] + [f"param{i}" for i in range(nested_levels)]
        assert len(result) == len(expected_params)
        assert set(result) == set(expected_params)


class TestSubstituteSQLParametersSafeErrorHandling:
    """Generic error handling tests for substitute_sql_parameters_safe.

    These tests are dialect-agnostic and test error conditions that should
    work the same way regardless of SQL dialect.
    """

    def test_missing_required_parameter_raises_error(self):
        """Test that missing required parameter raises ValueError."""
        sql = "SELECT * FROM users WHERE id = :user_id AND country = :country"
        param_defs = [
            QueryParameter(name="user_id", data_type="integer", description="User ID", example_value=1),
            QueryParameter(name="country", data_type="string", description="Country", example_value="US"),
        ]
        with pytest.raises(ValueError, match=r"Required parameter\(s\) not provided: country"):
            substitute_sql_parameters_safe(sql, {"user_id": 123}, param_defs, "postgres")

    def test_extra_parameters_ignored(self):
        """Test that extra parameters not in param_definitions are silently ignored."""
        sql = "SELECT * FROM users WHERE id = :user_id"
        param_defs = [QueryParameter(name="user_id", data_type="integer", description="User ID", example_value=1)]
        # Pass extra parameter 'country' that's not in SQL or param_defs
        result = substitute_sql_parameters_safe(sql, {"user_id": 123, "country": "Germany"}, param_defs, "postgres")
        assert result == "SELECT * FROM users WHERE id = 123"

    def test_parameter_in_sql_not_in_definitions_raises_error(self):
        """Test that parameter found in SQL but not in definitions raises ValueError."""
        sql = "SELECT * FROM users WHERE id = :user_id AND country = :country"
        param_defs = [
            QueryParameter(name="user_id", data_type="integer", description="User ID", example_value=1)
            # Missing 'country' parameter definition
        ]
        with pytest.raises(ValueError, match="Parameter 'country' found in SQL but not in parameter definitions"):
            substitute_sql_parameters_safe(sql, {"user_id": 123, "country": "US"}, param_defs, "postgres")

    def test_type_conversion_error_raises_error(self):
        """Test that type conversion error raises ValueError."""
        sql = "SELECT * FROM users WHERE id = :user_id"
        param_defs = [QueryParameter(name="user_id", data_type="integer", description="User ID", example_value=1)]
        with pytest.raises(ValueError, match="Failed to convert parameter 'user_id'"):
            substitute_sql_parameters_safe(sql, {"user_id": "not_a_number"}, param_defs, "postgres")


class TestExtractColumnAndTableFromNode:
    """Comprehensive tests for _extract_column_and_table_from_node internal function.

    This function is the core logic for detecting parameter context in SQL AST.
    It determines whether a literal should be parameterized and generates
    intelligent parameter names based on column/function context.
    """

    def _get_literal_node(self, sql: str, dialect: str = "postgres"):
        """Helper to get the first literal node from SQL AST."""
        from sqlglot import exp, parse_one

        ast = parse_one(sql, dialect=dialect)
        for node in ast.walk():
            if isinstance(node, exp.Literal | exp.Boolean):
                return node
        raise ValueError(f"No literal found in SQL: {sql}")

    # --- Direct Column Comparisons ---

    def test_direct_column_comparison_eq(self):
        """Test: WHERE country = 'USA' → (column='country', table=None, function=None)"""
        sql = "SELECT * FROM users WHERE country = 'USA'"
        node = self._get_literal_node(sql)
        result = _extract_column_and_table_from_node(node)
        assert result == ("country", None, None)

    def test_direct_column_comparison_with_table_qualifier(self):
        """Test: WHERE users.country = 'USA' → (column='country', table='users', function=None)"""
        sql = "SELECT * FROM users WHERE users.country = 'USA'"
        node = self._get_literal_node(sql)
        result = _extract_column_and_table_from_node(node)
        assert result == ("country", "users", None)

    def test_comparison_operators(self):
        """Test various comparison operators (>, <, >=, <=, !=)"""
        test_cases = [
            ("SELECT * FROM products WHERE price > 100", ("price", None, None)),
            ("SELECT * FROM products WHERE price < 100", ("price", None, None)),
            ("SELECT * FROM products WHERE price >= 100", ("price", None, None)),
            ("SELECT * FROM products WHERE price <= 100", ("price", None, None)),
            ("SELECT * FROM products WHERE price != 100", ("price", None, None)),
        ]
        for sql, expected in test_cases:
            node = self._get_literal_node(sql)
            result = _extract_column_and_table_from_node(node)
            assert result == expected, f"Failed for SQL: {sql}"

    def test_like_comparison(self):
        """Test: WHERE name LIKE '%John%' → (column='name', table=None, function=None)"""
        sql = "SELECT * FROM users WHERE name LIKE 'John%'"
        node = self._get_literal_node(sql)
        result = _extract_column_and_table_from_node(node)
        assert result == ("name", None, None)

    # --- Aggregate Functions ---

    def test_aggregate_with_column(self):
        """Test: HAVING sum(revenue) > 1000 → (column='revenue', table=None, function='sum')"""
        sql = "SELECT user_id FROM orders GROUP BY user_id HAVING sum(revenue) > 1000"
        node = self._get_literal_node(sql)
        result = _extract_column_and_table_from_node(node)
        assert result == ("revenue", None, "sum")

    def test_aggregate_without_column(self):
        """Test: HAVING count(*) > 10 → (column=None, table=None, function='count')"""
        sql = "SELECT user_id FROM orders GROUP BY user_id HAVING count(*) > 10"
        node = self._get_literal_node(sql)
        result = _extract_column_and_table_from_node(node)
        assert result == (None, None, "count")

    def test_various_aggregate_functions(self):
        """Test various aggregate functions"""
        test_cases = [
            ("SELECT avg(price) FROM products HAVING avg(price) > 100", ("price", None, "avg")),
            ("SELECT max(price) FROM products HAVING max(price) < 1000", ("price", None, "max")),
            ("SELECT min(price) FROM products HAVING min(price) > 10", ("price", None, "min")),
        ]
        for sql, expected in test_cases:
            node = self._get_literal_node(sql)
            result = _extract_column_and_table_from_node(node)
            assert result == expected, f"Failed for SQL: {sql}"

    # --- Scalar Functions ---

    def test_scalar_function_comparison(self):
        """Test: WHERE ROUND(price) > 100 → (column='price', table=None, function='round')"""
        sql = "SELECT * FROM products WHERE ROUND(price) > 100"
        node = self._get_literal_node(sql)
        result = _extract_column_and_table_from_node(node)
        assert result == ("price", None, "round")

    def test_scalar_function_nested(self):
        """Test: WHERE UPPER(TRIM(name)) = 'JOHN' → extracts outermost function only

        For nested functions, iter_expressions() only returns immediate children,
        so we get the function name but not the deeply nested column.
        Result: parameter named like :upper instead of :upper_name
        """
        sql = "SELECT * FROM users WHERE UPPER(TRIM(name)) = 'JOHN'"
        node = self._get_literal_node(sql)
        result = _extract_column_and_table_from_node(node)
        # iter_expressions() doesn't recurse, so we only get the outermost function
        assert result == (None, None, "upper")

    # --- IN Clause ---

    def test_in_clause_single_value(self):
        """Test: WHERE status IN ('active') → (column='status', table=None, function=None)"""
        sql = "SELECT * FROM users WHERE status IN ('active')"
        node = self._get_literal_node(sql)
        result = _extract_column_and_table_from_node(node)
        assert result == ("status", None, None)

    def test_in_clause_multiple_values(self):
        """Test: WHERE status IN ('active', 'pending') → both literals should have status context"""
        from sqlglot import exp, parse_one

        sql = "SELECT * FROM users WHERE status IN ('active', 'pending')"
        ast = parse_one(sql, dialect="postgres")
        literals = [n for n in ast.walk() if isinstance(n, exp.Literal)]
        assert len(literals) == 2
        for literal in literals:
            result = _extract_column_and_table_from_node(literal)
            assert result == ("status", None, None)

    # --- BETWEEN Clause ---

    def test_between_clause(self):
        """Test: WHERE price BETWEEN 10 AND 100 → both values get column='price'"""
        from sqlglot import exp, parse_one

        sql = "SELECT * FROM products WHERE price BETWEEN 10 AND 100"
        ast = parse_one(sql, dialect="postgres")
        literals = [n for n in ast.walk() if isinstance(n, exp.Literal)]
        assert len(literals) == 2
        for literal in literals:
            result = _extract_column_and_table_from_node(literal)
            assert result == ("price", None, None)

    def test_between_clause_with_cast(self):
        """Test: BETWEEN with CAST expressions → should still detect column context"""
        from sqlglot import exp, parse_one

        sql = "SELECT * FROM races WHERE date BETWEEN CAST('2009-01-01' AS DATE) AND CAST('2009-06-30' AS DATE)"
        ast = parse_one(sql, dialect="postgres")
        # Find the date string literals (not the 'DATE' type literals)
        literals = [n for n in ast.walk() if isinstance(n, exp.Literal) and "-" in str(n.this)]
        assert len(literals) == 2, f"Expected 2 date literals, found {len(literals)}"

        for literal in literals:
            result = _extract_column_and_table_from_node(literal)
            assert result is not None, f"CAST literal should be parameterized: {literal.this}"
            assert result[0] == "date", f"Expected column 'date', got {result}"

    # --- LIMIT and OFFSET ---

    def test_limit_only(self):
        """Test: LIMIT 10 → (column=None, table=None, function='limit')"""
        sql = "SELECT * FROM users LIMIT 10"
        node = self._get_literal_node(sql)
        result = _extract_column_and_table_from_node(node)
        assert result == (None, None, "limit")

    def test_limit_with_offset(self):
        """Test: LIMIT 10 OFFSET 20 → LIMIT gets 'limit', OFFSET gets 'offset'"""
        from sqlglot import exp, parse_one

        sql = "SELECT * FROM users LIMIT 10 OFFSET 20"
        ast = parse_one(sql, dialect="postgres")
        literals = [n for n in ast.walk() if isinstance(n, exp.Literal)]
        assert len(literals) == 2

        # Find which is limit and which is offset by their values
        limit_node = next(n for n in literals if n.this == "10")
        offset_node = next(n for n in literals if n.this == "20")

        limit_result = _extract_column_and_table_from_node(limit_node)
        offset_result = _extract_column_and_table_from_node(offset_node)

        assert limit_result is not None, "LIMIT node returned None"
        assert limit_result == (None, None, "limit"), f"LIMIT node returned {limit_result}"
        assert offset_result is not None, "OFFSET node returned None"
        assert offset_result == (None, None, "offset"), f"OFFSET node returned {offset_result}"

    def test_offset_only(self):
        """Test: OFFSET 20 → (column=None, table=None, function='offset')"""
        sql = "SELECT * FROM users OFFSET 20"
        node = self._get_literal_node(sql)
        result = _extract_column_and_table_from_node(node)
        assert result == (None, None, "offset")

    # --- Expression Comparisons ---

    def test_arithmetic_expression(self):
        """Test: WHERE price * 1.1 > 100 → should extract 'price' column"""
        sql = "SELECT * FROM products WHERE price * 1.1 > 100"
        node = self._get_literal_node(sql)
        result = _extract_column_and_table_from_node(node)
        # Should extract the column from the arithmetic expression
        assert result is not None
        assert result[0] == "price"

    # --- Edge Cases: No Context (should return None) ---

    def test_function_argument_no_context(self):
        """Test: ROUND(price, 2) → the '2' should return None (function argument)"""
        from sqlglot import exp, parse_one

        sql = "SELECT ROUND(price, 2) FROM products"
        ast = parse_one(sql, dialect="postgres")
        # Find the literal '2'
        literals = [n for n in ast.walk() if isinstance(n, exp.Literal) and n.this == "2"]
        assert len(literals) == 1
        result = _extract_column_and_table_from_node(literals[0])
        assert result is None, "Function arguments should not be parameterized"

    def test_case_then_value_no_context(self):
        """Test: CASE WHEN age < 18 THEN 'minor' → 'minor' should return None"""
        from sqlglot import exp, parse_one

        sql = "SELECT CASE WHEN age < 18 THEN 'minor' ELSE 'adult' END FROM users"
        ast = parse_one(sql, dialect="postgres")
        # Find the literal 'minor'
        literals = [n for n in ast.walk() if isinstance(n, exp.Literal) and n.this == "minor"]
        assert len(literals) == 1
        result = _extract_column_and_table_from_node(literals[0])
        assert result is None, "CASE THEN/ELSE values should not be parameterized"

    def test_select_list_literal_no_context(self):
        """Test: SELECT 'constant' → should return None"""
        from sqlglot import exp, parse_one

        sql = "SELECT 'constant' AS const_col FROM users"
        ast = parse_one(sql, dialect="postgres")
        literals = [n for n in ast.walk() if isinstance(n, exp.Literal) and n.this == "constant"]
        assert len(literals) == 1
        result = _extract_column_and_table_from_node(literals[0])
        assert result is None, "SELECT list literals should not be parameterized"
