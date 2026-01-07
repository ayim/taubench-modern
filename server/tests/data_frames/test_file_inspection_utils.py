"""Unit tests for file inspection utilities.

This module tests the infer_data_type function and related utilities
for inspecting files and converting them to data connection inspection formats.
"""

from agent_platform.server.data_frames.file_inspection_utils import infer_data_type


class TestInferDataType:
    """Test cases for the infer_data_type function."""

    def test_infer_data_type_numeric_integers(self):
        """Test that integer values are correctly identified as numeric."""
        assert infer_data_type([-1, 0, 1, 2, 3]) == "numeric"

    def test_infer_data_type_numeric_floats(self):
        """Test that float values are correctly identified as numeric."""
        assert infer_data_type([1.5, 2.5, 3.5]) == "numeric"
        assert infer_data_type([0.0, -1.5, 100.99]) == "numeric"

    def test_infer_data_type_numeric_mixed_int_float(self):
        """Test that mixed integer and float values are correctly identified as numeric."""
        assert infer_data_type([1, 2.5, 3]) == "numeric"
        assert infer_data_type([0, 1.5, 2]) == "numeric"

    def test_infer_data_type_boolean(self):
        """Test that boolean values are correctly identified."""
        assert infer_data_type([True, False, True]) == "boolean"
        assert infer_data_type([False]) == "boolean"
        assert infer_data_type([True]) == "boolean"

    def test_infer_data_type_string(self):
        """Test that string values are correctly identified."""
        assert infer_data_type(["a", "b", "c", "world"]) == "string"
        assert infer_data_type(["123"]) == "string"  # String representation of number
        assert infer_data_type(["True"]) == "string"  # String representation of boolean

    def test_infer_data_type_empty_list(self):
        """Test that empty list defaults to string."""
        assert infer_data_type([]) == "string"

    def test_infer_data_type_all_none(self):
        """Test that list with all None values defaults to string."""
        assert infer_data_type([None, None, None]) == "string"

    def test_infer_data_type_mixed_with_none(self):
        """Test that None values are filtered out and type is inferred from non-None values."""
        assert infer_data_type([None, 1, 2, None]) == "numeric"
        assert infer_data_type([None, True, False, None]) == "boolean"
        assert infer_data_type([None, "a", "b", None]) == "string"

    def test_infer_data_type_mixed_types_defaults_to_string(self):
        """Test that mixed incompatible types default to string."""
        # Mixed string and number should default to string (pandas will infer as 'mixed')
        assert infer_data_type(["a", 1, "b"]) == "string"
        # Mixed string and boolean should default to string
        assert infer_data_type(["a", True, "b"]) == "string"
        # Mixed number and boolean - pandas might infer as mixed, defaults to string
        assert infer_data_type([1, True, 2]) == "string"

    def test_infer_data_type_datetime_values(self):
        """Test that datetime-like values are treated as string (for now)."""
        # Note: pandas.infer_dtype can detect datetime, but we map it to string
        from datetime import date, datetime

        assert infer_data_type([datetime(2024, 1, 1), datetime(2024, 1, 2)]) == "string"
        assert infer_data_type([date(2024, 1, 1), date(2024, 1, 2)]) == "string"

    def test_infer_data_type_decimal_values(self):
        """Test that decimal values are identified as numeric."""
        from decimal import Decimal

        assert infer_data_type([Decimal("1.5"), Decimal("2.5")]) == "numeric"

    def test_infer_data_type_large_numbers(self):
        """Test that large numbers are correctly identified as numeric."""
        assert infer_data_type([1000000, 2000000, 3000000]) == "numeric"
        assert infer_data_type([1e10, 2e10, 3e10]) == "numeric"

    def test_infer_data_type_negative_numbers(self):
        """Test that negative numbers are correctly identified as numeric."""
        assert infer_data_type([-1, -2, -3]) == "numeric"
        assert infer_data_type([-1.5, -2.5, -3.5]) == "numeric"
        assert infer_data_type([0, -1, 1]) == "numeric"
