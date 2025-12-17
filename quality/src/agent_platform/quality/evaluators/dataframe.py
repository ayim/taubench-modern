"""Dataframe golden comparison evaluator."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import httpx

from agent_platform.quality.dataframes import (
    DataFrameComparator,
    fetch_dataframe_data,
    fetch_thread_dataframes,
    load_dataframe_from_file,
)
from agent_platform.quality.evaluators.base import Evaluator
from agent_platform.quality.models import DataFrameGoldenComparisonEvaluation

if TYPE_CHECKING:
    from agent_platform.quality.models import TestResult


class DataFrameGoldenComparisonEvaluator(Evaluator[DataFrameGoldenComparisonEvaluation]):
    """Evaluator for comparing agent-produced dataframes against golden datasets.

    This evaluator:
    1. Fetches all dataframes produced in the thread
    2. Loads the golden dataset from the test directory filesystem
    3. Compares each produced dataframe against the golden set
    4. Passes if any dataframe matches (with configurable tolerance and ordering)

    Expected format in YAML:
        expected:
            golden_file: "golden_results.csv"  # File in test directory
            match_mode: "all_columns_sorted"  # or "ordered" or "keyed"
            keys: ["customer_id"]  # required if match_mode is "keyed"
            relative_tolerance: 0.01  # 1% tolerance for numeric columns
            strict_columns: false  # if true, require exact column match
    """

    def __init__(
        self,
        evaluation: DataFrameGoldenComparisonEvaluation,
        client: httpx.AsyncClient,
        server_url: str,
    ):
        """Initialize the dataframe golden comparison evaluator.

        Args:
            evaluation: The evaluation configuration.
            client: HTTP client for API calls.
            server_url: Base URL for the server.
        """
        super().__init__(evaluation, client, server_url)

    async def evaluate(
        self,
        *,
        thread_id: str | None = None,
        test_directory: Path | str | None = None,
        **kwargs,
    ) -> TestResult:
        """Execute the dataframe golden comparison evaluation.

        Args:
            thread_id: The thread ID being evaluated (required).
            test_directory: The test directory path (required).
            **kwargs: Additional unused kwargs for compatibility.

        Returns:
            TestResult with passed/failed status, actual values, and error details.
        """
        from agent_platform.quality.models import TestResult

        expected = self.evaluation.expected

        if thread_id is None:
            return TestResult(
                evaluation=self.evaluation,
                passed=False,
                actual_value=None,
                error="Thread ID is required for dataframe-golden-comparison evaluation",
            )

        if test_directory is None:
            return TestResult(
                evaluation=self.evaluation,
                passed=False,
                actual_value=None,
                error="Test directory is required for dataframe-golden-comparison evaluation",
            )

        # Load golden dataset from test directory filesystem
        try:
            golden_path = Path(test_directory) / expected.golden_file
            golden_df = load_dataframe_from_file(golden_path)
        except Exception as e:
            return TestResult(
                evaluation=self.evaluation,
                passed=False,
                actual_value=None,
                error=f"Failed to load golden file '{expected.golden_file}': {e!s}",
            )

        # Fetch all dataframes from the thread
        try:
            actual_dfs = await fetch_thread_dataframes(
                thread_id,
                client=self.client,
                server_url=self.server_url,
            )
        except Exception as e:
            return TestResult(
                evaluation=self.evaluation,
                passed=False,
                actual_value=None,
                error=f"Failed to fetch thread dataframes: {e!s}",
            )

        if not actual_dfs:
            return TestResult(
                evaluation=self.evaluation,
                passed=False,
                actual_value={"num_dataframes": 0},
                error="No dataframes found in thread",
            )

        # Create comparator with configured settings
        comparator = DataFrameComparator(
            match_mode=expected.match_mode,
            keys=expected.keys,
            relative_tolerance=expected.relative_tolerance,
            strict_columns=expected.strict_columns,
        )

        # Compare each actual dataframe against the golden set
        comparison_results = []
        for df_info in actual_dfs:
            try:
                actual_df = await fetch_dataframe_data(
                    thread_id,
                    df_info["name"],
                    client=self.client,
                    server_url=self.server_url,
                )
                match_result = comparator.compare(actual_df, golden_df)
                comparison_results.append(
                    {
                        "dataframe_name": df_info["name"],
                        "matched": match_result["matched"],
                        "explanation": match_result.get("explanation", ""),
                        "num_rows_actual": len(actual_df),
                        "num_rows_golden": len(golden_df),
                    },
                )
            except Exception as e:
                comparison_results.append(
                    {
                        "dataframe_name": df_info["name"],
                        "matched": False,
                        "explanation": f"Comparison error: {e!s}",
                    },
                )

        # Pass if any dataframe matched
        passed = any(result["matched"] for result in comparison_results)

        return TestResult(
            evaluation=self.evaluation,
            passed=passed,
            actual_value={
                "num_dataframes": len(actual_dfs),
                "comparison_results": comparison_results,
            },
            error=None if passed else "No dataframe matched the golden dataset",
        )
