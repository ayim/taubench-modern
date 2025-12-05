from deepdiff import DeepDiff

# Comparison mode constants
COMPARISON_MODE_EXACT = "exact_match"
COMPARISON_MODE_FLEXIBLE = "flexible_match"


def evaluate_sql_results(
    expected_result: list[dict],
    actual_result: list[dict],
    comparison_mode: str = COMPARISON_MODE_EXACT,
    grouping_columns: list[str] | None = None,
) -> dict:
    """
    Compare results with simplified matching strategies.

    Args:
        expected_result: Expected result from test data
        actual_result: Actual result from SQL execution
        comparison_mode: "exact_match" or "flexible_match"
        grouping_columns: List of column names that must match exactly for grouped queries

    Returns:
        dict: {
            "success": bool,
            "differences": list[str],
            "comparison_stats": dict
        }
    """
    if comparison_mode == COMPARISON_MODE_EXACT:
        return compare_exact_match(expected_result, actual_result)
    else:  # flexible_match
        return compare_flexible_match(expected_result, actual_result, grouping_columns)


# TODO: Fix lint issues in this function
def compare_exact_match(expected_result: list[dict], actual_result: list[dict]) -> dict:  # noqa: C901, PLR0912
    """
    Compare exact structure including column names.
    Ignores extra columns in actual result, only checks expected columns.
    """
    differences = []

    # First check if row counts match
    if len(expected_result) != len(actual_result):
        differences.append(
            f"Row count mismatch: expected {len(expected_result)} rows, got "
            f"{len(actual_result)} rows"
        )
        return {
            "success": False,
            "differences": differences,
            "comparison_stats": {
                "expected_rows": len(expected_result),
                "actual_rows": len(actual_result),
            },
        }

    # If no expected rows, success
    if not expected_result:
        return {
            "success": True,
            "differences": [],
            "comparison_stats": {"expected_rows": 0, "actual_rows": 0},
        }

    # Get expected columns from first row
    expected_columns = set(expected_result[0].keys())

    # Check that all expected columns exist in actual result
    if actual_result:
        actual_columns = set(actual_result[0].keys())
        missing_columns = expected_columns - actual_columns
        if missing_columns:
            differences.append(f"Missing expected columns: {missing_columns}")
            return {
                "success": False,
                "differences": differences,
                "comparison_stats": {
                    "expected_rows": len(expected_result),
                    "actual_rows": len(actual_result),
                },
            }

    # Filter actual results to only include expected columns
    filtered_actual = []
    for row in actual_result:
        filtered_row = {col: row[col] for col in expected_columns}
        filtered_actual.append(filtered_row)

    # Now use DeepDiff for detailed comparison of filtered results
    diff = DeepDiff(expected_result, filtered_actual, ignore_order=True)

    if diff:
        for change_type, changes in diff.items():
            if change_type == "values_changed":
                for path, details in changes.items():
                    old_value = details.get("old_value")
                    new_value = details.get("new_value")
                    differences.append(
                        f"Value mismatch at {path}: expected {old_value}, got {new_value}"
                    )
            elif change_type == "dictionary_item_removed":
                for path in changes:
                    differences.append(f"Missing column: {path}")
            elif change_type == "iterable_item_added":
                for path in changes:
                    differences.append(f"Extra row found: {path}")
            elif change_type == "iterable_item_removed":
                for path in changes:
                    differences.append(f"Missing row: {path}")

    return {
        "success": len(differences) == 0,
        "differences": differences,
        "comparison_stats": {
            "expected_rows": len(expected_result),
            "actual_rows": len(actual_result),
        },
    }


def compare_flexible_match(
    expected_result: list[dict],
    actual_result: list[dict],
    grouping_columns: list[str] | None = None,
) -> dict:
    """
    Compare results with flexible column names for aggregations.

    Args:
        expected_result: Expected result (grouping columns first, then aggregation columns)
        actual_result: Actual result
        grouping_columns: List of column names that must match exactly (e.g., ["customer_name"])
    """
    if not expected_result and not actual_result:
        return {
            "success": True,
            "differences": [],
            "comparison_stats": {"expected_rows": 0, "actual_rows": 0},
        }

    if not expected_result or not actual_result:
        return {
            "success": False,
            "differences": ["Row count mismatch"],
            "comparison_stats": {
                "expected_rows": len(expected_result),
                "actual_rows": len(actual_result),
            },
        }

    differences = []

    # Step 1: Check row counts match
    if len(expected_result) != len(actual_result):
        differences.append(
            f"Row count mismatch: expected {len(expected_result)} rows, got "
            f"{len(actual_result)} rows"
        )
        return {
            "success": False,
            "differences": differences,
            "comparison_stats": {
                "expected_rows": len(expected_result),
                "actual_rows": len(actual_result),
            },
        }

    # Step 2: Verify expected grouping columns exist and match
    if grouping_columns:
        for group_col in grouping_columns:
            if group_col not in actual_result[0]:
                differences.append(
                    f"Expected grouping column '{group_col}' not found in actual result"
                )

        if differences:
            return {
                "success": False,
                "differences": differences,
                "comparison_stats": {},
            }

    # Step 3: Sort by expected grouping columns or all columns to ensure consistent order
    if grouping_columns:
        expected_sorted = sorted(
            expected_result, key=lambda x: tuple(x[col] for col in grouping_columns)
        )
        actual_sorted = sorted(
            actual_result, key=lambda x: tuple(x[col] for col in grouping_columns)
        )
    else:
        # Sort by all column values to ensure consistent ordering for non-grouped queries
        expected_sorted = sorted(expected_result, key=lambda x: tuple(sorted(x.items())))
        actual_sorted = sorted(actual_result, key=lambda x: tuple(sorted(x.items())))

    # Step 4: Compare row by row (now safe since we know row counts match and rows are aligned)
    for i, (expected_row, actual_row) in enumerate(
        zip(expected_sorted, actual_sorted, strict=False)
    ):
        row_differences = compare_row_flexible(
            expected_row, actual_row, grouping_columns, row_index=i
        )
        differences.extend(row_differences)

    return {
        "success": len(differences) == 0,
        "differences": differences,
        "comparison_stats": {
            "expected_rows": len(expected_result),
            "actual_rows": len(actual_result),
        },
    }


def compare_row_flexible(
    expected_row: dict, actual_row: dict, grouping_columns: list[str], row_index: int
) -> list[str]:
    """Compare a single row with flexible aggregation column names using value-based matching."""
    differences = []

    # Check expected grouping columns match exactly
    if grouping_columns:
        for group_col in grouping_columns:
            if expected_row[group_col] != actual_row[group_col]:
                differences.append(
                    f"Row {row_index}: Grouping column '{group_col}' mismatch - expected "
                    f"'{expected_row[group_col]}', got '{actual_row[group_col]}'"
                )

    # For non-grouping columns, match by value (ignore column names and positions)
    if grouping_columns:
        # Get expected non-grouping values (aggregation columns)
        expected_values = [v for k, v in expected_row.items() if k not in grouping_columns]

        # Get actual non-grouping values (ignore column names)
        actual_values = [v for k, v in actual_row.items() if k not in grouping_columns]
    else:
        # If no grouping columns, compare all values by value
        expected_values = list(expected_row.values())
        actual_values = list(actual_row.values())

    # Match each expected value to any actual value
    for expected_val in expected_values:
        if expected_val not in actual_values:
            differences.append(
                f"Row {row_index}: Expected value {expected_val} not found in actual result"
            )
        else:
            # Remove matched value to avoid double-counting
            actual_values.remove(expected_val)

    # Note: Extra values in actual result are ignored (not reported as differences)
    # This maintains compatibility with the existing behavior where extra columns are tolerated

    return differences
