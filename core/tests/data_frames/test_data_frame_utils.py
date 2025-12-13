import pytest

from agent_platform.core.data_frames.data_frame_utils import (
    VERIFIED_QUERY_NAME_MAX_LENGTH,
    VerifiedQueryNameError,
    data_frame_name_to_verified_query_name,
    validate_verified_query_name,
)


class TestValidateVerifiedQueryName:
    """Tests for the validate_verified_query_name function."""

    def test_valid_name_simple(self):
        """Test valid simple names."""
        assert validate_verified_query_name("Test Query") == "Test Query"
        assert validate_verified_query_name("My Report") == "My Report"
        assert validate_verified_query_name("Sales2024") == "Sales2024"

    def test_valid_name_with_spaces(self):
        """Test valid names with multiple spaces between words."""
        assert validate_verified_query_name("Quarter Windows Status") == "Quarter Windows Status"
        assert (
            validate_verified_query_name("Date windows for last calendar quarter")
            == "Date windows for last calendar quarter"
        )

    def test_valid_name_trims_whitespace(self):
        """Test that leading/trailing whitespace is trimmed."""
        assert validate_verified_query_name("  Test Query  ") == "Test Query"
        assert validate_verified_query_name("\tQuery Name\n") == "Query Name"

    def test_valid_name_alphanumeric_only(self):
        """Test valid names with only alphanumeric characters."""
        assert validate_verified_query_name("TestQuery123") == "TestQuery123"
        assert validate_verified_query_name("query42") == "query42"

    def test_empty_name_raises_error(self):
        """Test that empty names raise an error."""
        with pytest.raises(VerifiedQueryNameError, match="cannot be empty"):
            validate_verified_query_name("")

    def test_whitespace_only_raises_error(self):
        """Test that whitespace-only names raise an error."""
        with pytest.raises(VerifiedQueryNameError, match="cannot be empty"):
            validate_verified_query_name("   ")
        with pytest.raises(VerifiedQueryNameError, match="cannot be empty"):
            validate_verified_query_name("\t\n")

    def test_name_too_long_raises_error(self):
        """Test that names longer than the max length raise an error."""
        long_name = "a" * (VERIFIED_QUERY_NAME_MAX_LENGTH + 1)
        with pytest.raises(
            VerifiedQueryNameError,
            match=f"{VERIFIED_QUERY_NAME_MAX_LENGTH} characters or less",
        ):
            validate_verified_query_name(long_name)

    def test_name_at_max_length_is_valid(self):
        """Test that names exactly at max length are valid."""
        max_name = "a" * VERIFIED_QUERY_NAME_MAX_LENGTH
        assert validate_verified_query_name(max_name) == max_name

    def test_special_characters_raise_error(self):
        """Test that special characters raise an error."""
        with pytest.raises(VerifiedQueryNameError, match="only contain letters, numbers, and spaces"):
            validate_verified_query_name("Test_Query")  # underscore

        with pytest.raises(VerifiedQueryNameError, match="only contain letters, numbers, and spaces"):
            validate_verified_query_name("Test-Query")  # hyphen

        with pytest.raises(VerifiedQueryNameError, match="only contain letters, numbers, and spaces"):
            validate_verified_query_name("Test.Query")  # period

        with pytest.raises(VerifiedQueryNameError, match="only contain letters, numbers, and spaces"):
            validate_verified_query_name("Test@Query")  # at sign

        with pytest.raises(VerifiedQueryNameError, match="only contain letters, numbers, and spaces"):
            validate_verified_query_name("Test/Query")  # slash

    def test_punctuation_raises_error(self):
        """Test that punctuation characters raise an error."""
        with pytest.raises(VerifiedQueryNameError, match="only contain letters, numbers, and spaces"):
            validate_verified_query_name("What is the status?")  # question mark

        with pytest.raises(VerifiedQueryNameError, match="only contain letters, numbers, and spaces"):
            validate_verified_query_name("Sales Report!")  # exclamation

        with pytest.raises(VerifiedQueryNameError, match="only contain letters, numbers, and spaces"):
            validate_verified_query_name("Q1, Q2 Status")  # comma

    def test_unicode_letters_are_valid(self):
        """Test that unicode letters are valid."""
        # Unicode letters are allowed by isalnum()
        assert validate_verified_query_name("Café Report") == "Café Report"
        assert validate_verified_query_name("Relatório de Vendas") == "Relatório de Vendas"

    def test_emoji_raises_error(self):
        """Test that emojis raise an error."""
        with pytest.raises(VerifiedQueryNameError, match="only contain letters, numbers, and spaces"):
            validate_verified_query_name("Test 📊 Query")


class TestDataFrameNameToVerifiedQueryName:
    """Tests for the data_frame_name_to_verified_query_name function."""

    def test_converts_underscores_to_spaces(self):
        """Test that underscores are converted to spaces."""
        assert data_frame_name_to_verified_query_name("active_oakland_schools") == "Active Oakland Schools"
        assert data_frame_name_to_verified_query_name("my_data_frame") == "My Data Frame"

    def test_applies_title_case(self):
        """Test that title case is applied."""
        assert data_frame_name_to_verified_query_name("test") == "Test"
        assert data_frame_name_to_verified_query_name("UPPERCASE") == "Uppercase"

    def test_single_word(self):
        """Test single word names."""
        assert data_frame_name_to_verified_query_name("schools") == "Schools"
        assert data_frame_name_to_verified_query_name("Report") == "Report"

    def test_multiple_underscores(self):
        """Test names with multiple consecutive underscores."""
        assert data_frame_name_to_verified_query_name("test__name") == "Test  Name"

    def test_numbers_preserved(self):
        """Test that numbers are preserved."""
        assert data_frame_name_to_verified_query_name("sales_2024_q1") == "Sales 2024 Q1"
        assert data_frame_name_to_verified_query_name("report123") == "Report123"
