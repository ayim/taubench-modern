from .nl_to_sql_utils import (
    COMPARISON_MODE_EXACT,
    COMPARISON_MODE_FLEXIBLE,
    evaluate_sql_results,
)


class TestEvaluateMethod:
    """Unit tests for the evaluate method with static data."""

    def test_identical_results(self):
        """Test that identical results return no differences."""
        expected = [{"a": 1, "b": 2}]
        actual = [{"a": 1, "b": 2}]
        result = evaluate_sql_results(expected, actual)
        assert result["success"], f"Expected success, got: {result['differences']}"

    def test_different_order_same_values(self):
        """Test that different order but same values return no differences."""
        expected = [{"a": 1, "b": 2}]
        actual = [{"b": 2, "a": 1}]
        result = evaluate_sql_results(expected, actual)
        assert result["success"], f"Expected success, got: {result['differences']}"

    def test_different_values(self):
        """Test that different values return differences."""
        expected = [{"a": 1}]
        actual = [{"a": 0}]
        result = evaluate_sql_results(expected, actual)
        assert not result["success"], "Expected failure, got success"
        assert len(result["differences"]) == 1, (
            f"Expected 1 difference, got {len(result['differences'])}"
        )

    def test_flexible_match_aggregation(self):
        """Test flexible matching for aggregation queries."""
        expected = [{"total_payment_amount": 305.85}]
        actual = [{"sum_amount": 305.85}]
        result = evaluate_sql_results(expected, actual, COMPARISON_MODE_FLEXIBLE)
        assert result["success"], (
            f"Expected success with flexible match, got: {result['differences']}"
        )

    def test_flexible_match_aggregation_different_order(self):
        """Test flexible matching for aggregation queries with different column order."""
        expected = [{"total_payment_amount": 305.85, "payment_count": 5}]
        actual = [{"payment_count": 5, "sum_amount": 305.85}]  # Different order
        result = evaluate_sql_results(expected, actual, COMPARISON_MODE_FLEXIBLE)
        assert result["success"], (
            f"Expected success with flexible match, got: {result['differences']}"
        )

    def test_flexible_match_grouped_aggregation(self):
        """Test flexible matching for grouped aggregation queries."""
        expected = [
            {"customer_name": "John Doe", "total_payment_amount": 305.85},
            {"customer_name": "Jane Smith", "total_payment_amount": 150.50},
        ]
        actual = [
            {"customer_name": "John Doe", "sum_amount": 305.85},
            {"customer_name": "Jane Smith", "sum_amount": 150.50},
        ]
        result = evaluate_sql_results(
            expected,
            actual,
            COMPARISON_MODE_FLEXIBLE,
            grouping_columns=["customer_name"],
        )
        assert result["success"], (
            f"Expected success with grouped flexible match, got: {result['differences']}"
        )

    def test_flexible_match_grouped_aggregation_different_order(self):
        """Test flexible matching for grouped aggregation queries with different column order."""
        expected = [
            {
                "customer_name": "John Doe",
                "total_payment_amount": 305.85,
                "payment_count": 3,
            },
            {
                "customer_name": "Jane Smith",
                "total_payment_amount": 150.50,
                "payment_count": 2,
            },
        ]
        actual = [
            {
                "customer_name": "John Doe",
                "payment_count": 3,
                "sum_amount": 305.85,
            },  # Different order
            {
                "customer_name": "Jane Smith",
                "payment_count": 2,
                "sum_amount": 150.50,
            },  # Different order
        ]
        result = evaluate_sql_results(
            expected,
            actual,
            COMPARISON_MODE_FLEXIBLE,
            grouping_columns=["customer_name"],
        )
        assert result["success"], (
            f"Expected success with grouped flexible match, got: {result['differences']}"
        )

    def test_flexible_match_grouping_column_mismatch(self):
        """Test that grouping column mismatches are caught."""
        expected = [{"customer_name": "John Doe", "total_payment_amount": 305.85}]
        actual = [{"customer_name": "Jane Smith", "sum_amount": 305.85}]
        result = evaluate_sql_results(
            expected,
            actual,
            COMPARISON_MODE_FLEXIBLE,
            grouping_columns=["customer_name"],
        )
        assert not result["success"], "Expected failure with grouping column mismatch, got success"
        assert any("Grouping column" in diff for diff in result["differences"])

    def test_flexible_match_value_not_found(self):
        """Test that missing expected values are caught."""
        expected = [
            {
                "customer_name": "John Doe",
                "total_payment_amount": 305.85,
                "payment_count": 3,
            }
        ]
        actual = [
            {
                "customer_name": "John Doe",
                "sum_amount": 305.85,
                "payment_count": 2,
            }  # Different count
        ]
        result = evaluate_sql_results(
            expected,
            actual,
            COMPARISON_MODE_FLEXIBLE,
            grouping_columns=["customer_name"],
        )
        assert not result["success"], "Expected failure with missing value, got success"
        assert any("Expected value 3 not found" in diff for diff in result["differences"])

    def test_flexible_match_extra_values_ignored(self):
        """Test that extra values in actual result are handled gracefully."""
        expected = [{"customer_name": "John Doe", "total_payment_amount": 305.85}]
        actual = [{"customer_name": "John Doe", "sum_amount": 305.85, "extra_value": 123}]
        result = evaluate_sql_results(
            expected,
            actual,
            COMPARISON_MODE_FLEXIBLE,
            grouping_columns=["customer_name"],
        )
        assert result["success"], (
            f"Expected success with extra values, got: {result['differences']}"
        )

    def test_exact_match_row_count_mismatch(self):
        """Test that row count mismatches are caught in exact match."""
        expected = [
            {"customer_id": "C123", "payment_amount": 69.97},
            {"customer_id": "C123", "payment_amount": 47.97},
        ]
        actual = [
            {"customer_id": "C123", "payment_amount": 69.97},
            {"customer_id": "C123", "payment_amount": 47.97},
            {"customer_id": "C124", "payment_amount": 125.50},
        ]
        result = evaluate_sql_results(expected, actual, COMPARISON_MODE_EXACT)
        assert not result["success"], "Expected failure with row count mismatch, got success"
        assert any("Row count mismatch" in diff for diff in result["differences"])
        assert result["comparison_stats"]["expected_rows"] == 2
        assert result["comparison_stats"]["actual_rows"] == 3

    def test_flexible_match_row_count_mismatch(self):
        """Test that row count mismatches are caught in flexible match."""
        expected = [{"customer_name": "John Doe", "total_payment_amount": 305.85}]
        actual = [
            {"customer_name": "John Doe", "sum_amount": 305.85},
            {"customer_name": "Jane Smith", "sum_amount": 150.50},
        ]
        result = evaluate_sql_results(
            expected,
            actual,
            COMPARISON_MODE_FLEXIBLE,
            grouping_columns=["customer_name"],
        )
        assert not result["success"], "Expected failure with row count mismatch, got success"
        assert any("Row count mismatch" in diff for diff in result["differences"])
        assert result["comparison_stats"]["expected_rows"] == 1
        assert result["comparison_stats"]["actual_rows"] == 2

    def test_exact_match_extra_columns_ignored(self):
        """Test that extra columns in actual result are ignored in exact match."""
        expected = [{"customer_id": "C123", "payment_amount": 69.97}]
        actual = [
            {
                "customer_id": "C123",
                "payment_amount": 69.97,
                "extra_column": "extra_value",
                "another_extra": 123,
            }
        ]
        result = evaluate_sql_results(expected, actual, COMPARISON_MODE_EXACT)
        assert result["success"], (
            f"Expected success with extra columns ignored, got: {result['differences']}"
        )

    def test_exact_match_extra_columns_multiple_rows(self):
        """Test that extra columns are ignored across multiple rows in exact match."""
        expected = [
            {"customer_id": "C123", "payment_amount": 69.97},
            {"customer_id": "C124", "payment_amount": 125.50},
        ]
        actual = [
            {
                "customer_id": "C123",
                "payment_amount": 69.97,
                "extra_col1": "value1",
                "extra_col2": 456,
            },
            {"customer_id": "C124", "payment_amount": 125.50, "extra_col3": "value3"},
        ]
        result = evaluate_sql_results(expected, actual, COMPARISON_MODE_EXACT)
        assert result["success"], (
            f"Expected success with extra columns ignored, got: {result['differences']}"
        )

    def test_exact_match_extra_columns_with_value_mismatch(self):
        """Test that value mismatches are still caught even with extra columns."""
        expected = [{"customer_id": "C123", "payment_amount": 69.97}]
        actual = [
            {
                "customer_id": "C123",
                "payment_amount": 70.00,
                "extra_column": "extra_value",
            }
        ]
        result = evaluate_sql_results(expected, actual, COMPARISON_MODE_EXACT)
        assert not result["success"], "Expected failure with value mismatch, got success"
        assert any("Value mismatch" in diff for diff in result["differences"])

    def test_exact_match_extra_columns_with_missing_expected_column(self):
        """Test that missing expected columns are still caught even with extra columns."""
        expected = [{"customer_id": "C123", "payment_amount": 69.97}]
        actual = [
            {
                "customer_id": "C123",
                "extra_column": "extra_value",
            }  # Missing payment_amount
        ]
        result = evaluate_sql_results(expected, actual, COMPARISON_MODE_EXACT)
        assert not result["success"], "Expected failure with missing expected column, got success"
        assert any("Missing expected columns" in diff for diff in result["differences"])

    def test_flexible_match_extra_columns_ignored(self):
        """Test that extra columns in actual result are ignored in flexible match."""
        expected = [{"customer_name": "John Doe", "total_payment_amount": 305.85}]
        actual = [
            {
                "customer_name": "John Doe",
                "sum_amount": 305.85,
                "extra_column": "extra_value",
                "another_extra": 123,
            }
        ]
        result = evaluate_sql_results(
            expected,
            actual,
            COMPARISON_MODE_FLEXIBLE,
            grouping_columns=["customer_name"],
        )
        assert result["success"], (
            f"Expected success with extra columns ignored, got: {result['differences']}"
        )

    def test_flexible_match_extra_columns_grouped_aggregation(self):
        """Test that extra columns are ignored in grouped aggregation with flexible match."""
        expected = [
            {"customer_name": "John Doe", "total_payment_amount": 305.85},
            {"customer_name": "Jane Smith", "total_payment_amount": 150.50},
        ]
        actual = [
            {"customer_name": "John Doe", "sum_amount": 305.85, "extra_col1": "value1"},
            {
                "customer_name": "Jane Smith",
                "sum_amount": 150.50,
                "extra_col1": "value3",
            },
        ]
        result = evaluate_sql_results(
            expected,
            actual,
            COMPARISON_MODE_FLEXIBLE,
            grouping_columns=["customer_name"],
        )
        assert result["success"], (
            f"Expected success with extra columns ignored, got: {result['differences']}"
        )

    def test_flexible_match_extra_columns_with_grouping_mismatch(self):
        """Test that grouping column mismatches are still caught even with extra columns."""
        expected = [{"customer_name": "John Doe", "total_payment_amount": 305.85}]
        actual = [
            {
                "customer_name": "Jane Smith",
                "sum_amount": 305.85,
                "extra_column": "extra_value",
            }
        ]
        result = evaluate_sql_results(
            expected,
            actual,
            COMPARISON_MODE_FLEXIBLE,
            grouping_columns=["customer_name"],
        )
        assert not result["success"], "Expected failure with grouping column mismatch, got success"
        assert any("Grouping column" in diff for diff in result["differences"])

    def test_flexible_match_extra_columns_with_value_mismatch(self):
        """Test that aggregation value mismatches are still caught even with extra columns."""
        expected = [{"customer_name": "John Doe", "total_payment_amount": 305.85}]
        actual = [
            {
                "customer_name": "John Doe",
                "sum_amount": 300.00,
                "extra_column": "extra_value",
            }
        ]
        result = evaluate_sql_results(
            expected,
            actual,
            COMPARISON_MODE_FLEXIBLE,
            grouping_columns=["customer_name"],
        )
        assert not result["success"], "Expected failure with value mismatch, got success"
        assert any("Expected value 305.85 not found" in diff for diff in result["differences"])
