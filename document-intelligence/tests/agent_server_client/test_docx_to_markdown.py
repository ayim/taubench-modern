"""
Tests for docx_to_markdown functionality using parameterized test data.
"""

from pathlib import Path

import pytest

from sema4ai_docint.agent_server_client.docx_to_markdown import docx_to_markdown_txt


def get_test_cases():
    """Get all test cases from the test-data/docx_to_markdown directory."""
    test_data_dir = Path(__file__).parent / "test-data" / "docx_to_markdown"
    test_cases = []

    if test_data_dir.exists():
        for test_case_dir in test_data_dir.iterdir():
            if test_case_dir.is_dir():
                # Check if both required files exist
                docx_file = test_case_dir / "data.docx"
                markdown_file = test_case_dir / "markdown.txt"

                if docx_file.exists() and markdown_file.exists():
                    test_cases.append(test_case_dir.name)

    return test_cases


class TestDocxToMarkdown:
    """Test class for docx_to_markdown functionality."""

    @pytest.mark.parametrize("test_case", get_test_cases())
    def test_docx_to_markdown_conversion(self, test_case):
        """Test docx to markdown conversion for the specified test case."""

        # Load test case data
        test_case_dir = Path(__file__).parent / "test-data" / "docx_to_markdown" / test_case
        docx_file = test_case_dir / "data.docx"
        expected_markdown_file = test_case_dir / "markdown.txt"

        # Verify files exist
        assert docx_file.exists(), f"DOCX file not found: {docx_file}"
        assert expected_markdown_file.exists(), (
            f"Expected markdown file not found: {expected_markdown_file}"
        )

        # Load expected markdown content
        with open(expected_markdown_file, encoding="utf-8") as f:
            expected_markdown = f.read().strip()

        # Convert DOCX to markdown
        actual_markdown = docx_to_markdown_txt(str(docx_file))
        print(actual_markdown)
        actual_markdown = actual_markdown.strip()

        # Compare results
        assert actual_markdown == expected_markdown, (
            f"Markdown conversion mismatch for {test_case}:\n"
            f"Expected:\n{expected_markdown}\n\n"
            f"Actual:\n{actual_markdown}"
        )

    def test_file_not_found(self):
        """Test that FileNotFoundError is raised for non-existent files."""
        with pytest.raises(FileNotFoundError):
            docx_to_markdown_txt("non_existent_file.docx")

    def test_empty_test_cases_directory(self):
        """Test that the test framework handles empty test cases directory gracefully."""
        test_cases = get_test_cases()
        # This test just ensures get_test_cases() doesn't crash
        assert isinstance(test_cases, list)
