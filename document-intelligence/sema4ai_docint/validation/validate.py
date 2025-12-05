import logging

from sema4ai.data import DataSource

from ..models import DataModel
from .models import ValidationResult, ValidationRule, ValidationSummary

logger = logging.getLogger(__name__)


def _generate_report(rule_statuses: list[ValidationResult]) -> ValidationSummary:
    """
    Generates a validation summary report based on rule statuses.

    Args:
        rule_statuses: List of validation results for each rule.
    Returns:
        A ValidationSummary object.
    """
    # Determine overall status
    passed_count = sum(1 for result in rule_statuses if result.status == "passed")
    failed_count = sum(1 for result in rule_statuses if result.status == "failed")
    error_count = sum(1 for result in rule_statuses if result.status == "error")
    overall_status = "passed" if failed_count == 0 and error_count == 0 else "failed"

    return ValidationSummary(
        overall_status=overall_status,
        results=rule_statuses,
        passed=passed_count,
        failed=failed_count,
        errors=error_count,
    )


def validate_document_extraction(
    document_id: str, data_source: DataSource, validation_rules: list[ValidationRule]
) -> ValidationSummary:
    """
    Validate a document based on the validation rules.
    Rules are SQL queries that are executed against the view of the document.

    Args:
        document_id: The ID of the document to validate
        data_source: Data source connection
        validation_rules: List of ValidationRule objects containing:
            - rule_name: Name of the validation rule
            - sql_query: SQL query to validate the document
            - rule_description: Description of what the rule validates

    Returns:
        A ValidationSummary object.
    """
    try:
        if not validation_rules:
            logger.warning(f"No validation rules provided for document ID: {document_id}")
            return ValidationSummary(
                overall_status="passed", passed=0, failed=0, errors=0, results=[]
            )

        rule_statuses = []
        for rule in validation_rules:
            try:
                # Run the validation query
                logger.info(
                    f"Running validation query: {rule.sql_query} with document_id: {document_id}"
                )
                validation_result = data_source.execute_sql(
                    rule.sql_query, params={"document_id": document_id}
                )

                # Verify we have a result with at least one row
                if not validation_result or (
                    ((table := validation_result.to_table()) and not table) or not table.rows
                ):
                    logger.warning(f"No result from validation query: {rule.sql_query}")
                    rule_statuses.append(
                        ValidationResult(
                            rule_name=rule.rule_name,
                            status="failed",
                            description=rule.rule_description,
                            error_message="No result from validation query",
                            sql_query=rule.sql_query,
                            context={"error": "Validation rule did not generate any rows"},
                        )
                    )
                    continue

                result_row = table.rows[0]

                # The first column should be the boolean validation result
                is_valid = str(result_row[0]).lower() == "true"

                # Collect all remaining column values as context for the caller to understand
                # the rule execution
                context = dict(zip(table.columns[1:], result_row[1:], strict=False))

                if is_valid:
                    rule_statuses.append(
                        ValidationResult(
                            rule_name=rule.rule_name,
                            status="passed",
                            description=rule.rule_description,
                            sql_query=rule.sql_query,
                            context=context,
                        )
                    )
                else:
                    rule_statuses.append(
                        ValidationResult(
                            rule_name=rule.rule_name,
                            status="failed",
                            description=rule.rule_description,
                            error_message="Validation query did not return true",
                            sql_query=rule.sql_query,
                            context=context,
                        )
                    )

            except Exception as e:
                logger.error(f"Error validating rule {rule.rule_name}: {e!s}", exc_info=True)
                rule_statuses.append(
                    ValidationResult(
                        rule_name=rule.rule_name,
                        status="error",
                        description=rule.rule_description,
                        error_message=str(e),
                        sql_query=rule.sql_query,
                        # Give some context back to the caller
                        context={"error": f"failed to execute the query: {str(e)[:200]}"},
                    )
                )

        # Generate report using the internal function
        summary = _generate_report(rule_statuses)
        logger.info(f"Validation summary: {summary}")
        return summary

    except Exception as e:
        logger.error(f"Error during document validation: {e!s}")
        raise


def gather_view_metadata_with_samples(data_model: DataModel, datasource: DataSource) -> list[dict]:
    # Gather view reference data
    view_reference_data = []
    for view in data_model.views:
        try:
            # Get sample data from the view which will also give us column information
            sample_data_query = f"""
            SELECT *
            FROM document_intelligence.{view["name"]}
            ORDER BY document_id
            LIMIT 5;
            """
            sample_data = datasource.execute_sql(sample_data_query)

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
                    "name": view["name"],
                    "columns": column_names,  # Just pass the column names
                    "sample_data": sample_data_list,
                }
            )
        except Exception as e:
            logger.warning(f"Could not gather reference data for view {view['name']}: {e!s}")
            # Continue with other views even if one fails
            continue
    return view_reference_data
