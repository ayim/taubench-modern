from typing import Any, Literal

from pydantic import BaseModel


class ValidationRule(BaseModel):
    """A validation rule for a use case.

    Attributes:
        rule_name: The name of the validation rule
        rule_description: A description of what the rule validates
        sql_query: The SQL query that validates the extracted data
    """

    rule_name: str
    rule_description: str
    sql_query: str


class ValidationResult(BaseModel):
    """Result of a single validation rule check.

    Attributes:
        rule_name: The name of the validation rule
        status: The status of the validation (passed/failed/error)
        description: Description of the validation result
        error_message: Optional error message if validation failed
        sql_query: The SQL query that was executed
        context: Metadata about the validation result
    """

    rule_name: str
    status: str
    description: str
    error_message: str | None = None
    sql_query: str
    context: dict[str, Any] | None = None


class ValidationSummary(BaseModel):
    """Summary of all validation results for a document.

    Attributes:
        overall_status: Overall status of all validations
        results: List of individual validation results
        passed: Number of passed validations
        failed: Number of failed validations
        errors: Number of validation errors
    """

    overall_status: Literal["passed", "failed"]
    results: list[ValidationResult]
    passed: int
    failed: int
    errors: int
