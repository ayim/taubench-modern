from unittest.mock import Mock

import pytest
from sema4ai.actions import Row
from sema4ai.data import DataSource, ResultSet

from sema4ai_docint.validation.models import ValidationResult, ValidationRule
from sema4ai_docint.validation.validate import (
    _generate_report,
    validate_document_extraction,
)


@pytest.fixture
def mock_data_source():
    return Mock(spec=DataSource)


@pytest.fixture
def sample_validation_rules():
    return [
        ValidationRule(
            rule_name="test_rule_1",
            sql_query=(
                "SELECT COUNT(*) > 0 as is_valid, COUNT(*) as count "
                "FROM documents WHERE document_id = $document_id"
            ),
            rule_description="Check if document exists",
        ),
        ValidationRule(
            rule_name="test_rule_2",
            sql_query=(
                "SELECT field_value IS NOT NULL as is_valid, field_value as actual_value "
                "FROM documents WHERE document_id = $document_id"
            ),
            rule_description="Check if required field is not null",
        ),
    ]


def test_generate_report_all_passed():
    rule_statuses = [
        ValidationResult(
            rule_name="rule1",
            status="passed",
            description="test1",
            sql_query="SELECT true as is_valid",
            context={"is_valid": True},
        ),
        ValidationResult(
            rule_name="rule2",
            status="passed",
            description="test2",
            sql_query="SELECT true as is_valid",
            context={"is_valid": True},
        ),
    ]

    summary = _generate_report(rule_statuses)

    assert summary.overall_status == "passed"
    assert summary.passed == 2
    assert summary.failed == 0
    assert summary.errors == 0
    assert len(summary.results) == 2


def test_generate_report_with_failures():
    rule_statuses = [
        ValidationResult(
            rule_name="rule1",
            status="passed",
            description="test1",
            sql_query="SELECT true as is_valid",
            context={"is_valid": True, "reason": "valid"},
        ),
        ValidationResult(
            rule_name="rule2",
            status="failed",
            description="test2",
            error_message="Failed validation",
            sql_query="SELECT false as is_valid, 'invalid' as reason",
            context={"is_valid": False, "reason": "invalid"},
        ),
        ValidationResult(
            rule_name="rule3",
            status="error",
            description="test3",
            error_message="Error occurred",
            sql_query="SELECT * FROM invalid_table",
            context=None,
        ),
    ]

    summary = _generate_report(rule_statuses)

    assert summary.overall_status == "failed"
    assert summary.passed == 1
    assert summary.failed == 1
    assert summary.errors == 1
    assert len(summary.results) == 3


def test_validate_document_extraction_success(mock_data_source, sample_validation_rules):
    document_id = "test_doc_123"

    # Mock the database response for both rules
    mock_data_source.execute_sql.side_effect = [
        ResultSet(
            columns=["is_valid", "count"],
            rows=[
                Row([True, 1]),
            ],
        ),
        ResultSet(
            columns=["is_valid", "actual_value"],
            rows=[
                Row([True, "test_value"]),
            ],
        ),
    ]

    result = validate_document_extraction(
        document_id=document_id,
        data_source=mock_data_source,
        validation_rules=sample_validation_rules,
    )

    assert result.overall_status == "passed"
    assert result.passed == 2
    assert result.failed == 0
    assert result.errors == 0
    assert len(result.results) == 2

    # Verify SQL execution calls
    assert mock_data_source.execute_sql.call_count == 2
    mock_data_source.execute_sql.assert_any_call(
        sample_validation_rules[0].sql_query, params={"document_id": document_id}
    )


def test_validate_document_extraction_with_failures(mock_data_source, sample_validation_rules):
    document_id = "test_doc_123"

    # Mock the database response - first rule passes, second fails
    mock_data_source.execute_sql.side_effect = [
        ResultSet(
            columns=["is_valid", "count"],
            rows=[
                Row([True, 1]),
            ],
        ),
        ResultSet(
            columns=["is_valid", "actual_value"],
            rows=[Row([False, "something helpful"])],
        ),
    ]

    result = validate_document_extraction(
        document_id=document_id,
        data_source=mock_data_source,
        validation_rules=sample_validation_rules,
    )

    assert result.overall_status == "failed"
    assert result.passed == 1
    assert result.failed == 1
    assert result.errors == 0
    assert len(result.results) == 2

    # Verify the failed result contains the query and result
    failed_result = next(r for r in result.results if r.status == "failed")
    assert failed_result.sql_query == sample_validation_rules[1].sql_query
    assert failed_result.context == {"actual_value": "something helpful"}


def test_validate_document_extraction_with_error(mock_data_source, sample_validation_rules):
    document_id = "test_doc_123"

    # Mock the database to raise an exception for each rule
    mock_data_source.execute_sql.side_effect = [
        Exception("Database error"),  # First rule fails
        Exception("Database error"),  # Second rule fails
    ]

    summary = validate_document_extraction(
        document_id=document_id,
        data_source=mock_data_source,
        validation_rules=sample_validation_rules,
    )

    assert summary.overall_status == "failed"
    assert summary.errors == 2
    assert len(summary.results) == 2
    assert all(r.status == "error" for r in summary.results)
    assert all(
        r.context and "error" in r.context and "Database error" in r.context["error"]
        for r in summary.results
    ), f"Context: {summary.results}"
    assert all(r.error_message == "Database error" for r in summary.results)

    # Verify each rule's SQL query was captured
    assert summary.results[0].sql_query == sample_validation_rules[0].sql_query
    assert summary.results[1].sql_query == sample_validation_rules[1].sql_query


def test_validate_document_extraction_no_rules():
    document_id = "test_doc_123"
    mock_data_source = Mock(spec=DataSource)

    result = validate_document_extraction(
        document_id=document_id, data_source=mock_data_source, validation_rules=[]
    )

    assert result.overall_status == "passed"
    assert result.passed == 0
    assert result.failed == 0
    assert result.errors == 0
    assert len(result.results) == 0

    # Verify no SQL was executed
    mock_data_source.execute_sql.assert_not_called()


def test_validate_document_extraction_empty_result(mock_data_source, sample_validation_rules):
    document_id = "test_doc_123"

    # Mock empty result from database for each rule
    mock_data_source.execute_sql.side_effect = [
        ResultSet(
            columns=["is_valid", "count"],
            rows=[],
        ),
        ResultSet(
            columns=["is_valid", "actual_value"],
            rows=[],
        ),
    ]

    result = validate_document_extraction(
        document_id=document_id,
        data_source=mock_data_source,
        validation_rules=sample_validation_rules,
    )

    assert result.overall_status == "failed"
    assert result.failed == 2
    assert len(result.results) == 2
    assert all(
        r.status == "failed" and r.error_message == "No result from validation query"
        for r in result.results
    )
    assert all(
        r.context and "error" in r.context and "generate any rows" in r.context["error"]
        for r in result.results
    ), f"Context: {result.results}"

    # Verify each rule's SQL query was captured
    assert result.results[0].sql_query == sample_validation_rules[0].sql_query
    assert result.results[1].sql_query == sample_validation_rules[1].sql_query
