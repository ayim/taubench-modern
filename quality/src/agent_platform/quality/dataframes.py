"""Dataframe utilities for comparison and retrieval."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    import httpx
    import pandas as pd


class DataFrameMatchMode(StrEnum):
    """Match modes for dataframe comparison."""

    ORDERED = "ordered"
    """Compare row-by-row in exact order (preserves ORDER BY from SQL)"""

    ALL_COLUMNS_SORTED = "all_columns_sorted"
    """Sort both dataframes by all columns before comparing"""

    KEYED = "keyed"
    """Sort both dataframes by specified key columns before comparing"""

    VALUES_ONLY = "values_only"
    """Compare row VALUE SETS only, ignoring column names (BIRD EX-style).
    Converts each row to a tuple of values and compares as sets.
    Two dataframes match if they have the same set of row value tuples."""


class ComparisonResult(BaseModel):
    """Result of comparing two dataframes.

    This model defines the contract between comparators and evaluators.
    Comparators return this model, and evaluators can add their own fields as needed.
    """

    matched: bool = Field(description="Whether the comparison passed the threshold")
    explanation: str = Field(description="Human-readable explanation of the result")
    num_rows_compared: int = Field(description="Number of rows in the compared dataframe")
    num_rows_reference: int = Field(description="Number of rows in the reference dataframe")


class DataFrameComparisonError(Exception):
    """Exception raised when dataframe comparison fails."""

    pass


class BaseDataFrameComparator(ABC):
    """Base class for dataframe comparison with shared utilities.

    This abstract base class provides common functionality for comparing dataframes,
    including column alignment, numeric tolerance handling, and value normalization.
    """

    def __init__(
        self,
        relative_tolerance: float = 0.01,
        strict_columns: bool = False,
    ):
        """Initialize the base comparator.

        Args:
            relative_tolerance: Relative tolerance for numeric column comparisons (e.g., 0.01 = 1%).
            strict_columns: If True, require exact column names and order, otherwise the compare dataframe
                can have a superset of columns compared to the reference dataframe.
        """
        self.relative_tolerance = relative_tolerance
        self.strict_columns = strict_columns

    @abstractmethod
    def compare(self, compare_df: pd.DataFrame, reference_df: pd.DataFrame) -> ComparisonResult:
        """Compare two dataframes with configured tolerance and ordering.

        This method must be implemented by subclasses to define specific comparison logic.

        Args:
            compare_df: The dataframe to compare against the reference.
            reference_df: The reference/baseline dataframe.

        Returns:
            ComparisonResult with match status, explanation, and optional metrics.
        """
        ...

    def _align_columns(
        self,
        compare_df: pd.DataFrame,
        reference_df: pd.DataFrame,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Align columns between compare and reference dataframes.

        Args:
            compare_df: Compare dataframe.
            reference_df: Reference dataframe.

        Returns:
            Tuple of (aligned_compare_df, reference_df).

        Raises:
            DataFrameComparisonError: If column alignment or row count validation fails.
        """
        # Normalize column names (strip whitespace, lowercase for comparison)
        compare_df = compare_df.copy()
        reference_df = reference_df.copy()

        # Create mapping of normalized names to original names
        compare_cols = {col.strip().lower(): col for col in compare_df.columns}
        reference_cols = {col.strip().lower(): col for col in reference_df.columns}

        # Check column compatibility -- note, this does not check for type equivalence, only name equivalence.
        if self.strict_columns:
            if set(compare_cols.keys()) != set(reference_cols.keys()):
                missing = set(reference_cols.keys()) - set(compare_cols.keys())
                extra = set(compare_cols.keys()) - set(reference_cols.keys())
                raise DataFrameComparisonError(f"Column mismatch: missing={list(missing)}, extra={list(extra)}")
        else:
            # Check that reference columns are present in compare
            missing = set(reference_cols.keys()) - set(compare_cols.keys())
            if missing:
                raise DataFrameComparisonError(f"Missing required columns: {list(missing)}")

        # Rename columns to match (use reference column names)
        col_rename: dict[str, str] = {}
        for norm_name, reference_col in reference_cols.items():
            if norm_name in compare_cols:
                col_rename[compare_cols[norm_name]] = reference_col

        compare_df_aligned = compare_df[list(col_rename.keys())].rename(columns=col_rename)  # type: ignore[call-overload]

        # Check row counts
        if len(compare_df_aligned) != len(reference_df):
            raise DataFrameComparisonError(
                f"Row count mismatch: compare={len(compare_df_aligned)}, reference={len(reference_df)}"
            )

        return compare_df_aligned, reference_df

    def _compare_aligned(self, compare_df: pd.DataFrame, reference_df: pd.DataFrame) -> ComparisonResult:
        """Compare two aligned (same order) dataframes with tolerance.

        Args:
            compare_df: Compare dataframe.
            reference_df: Reference dataframe.

        Returns:
            ComparisonResult with match status and explanation.
        """
        import numpy as np
        import pandas as pd

        mismatches = []

        for col in reference_df.columns:
            compare_col = compare_df[col]
            reference_col = reference_df[col]

            # Check if column is numeric or can be converted to numeric
            # If reference is numeric and compare might be numeric strings, try numeric comparison
            reference_is_numeric = pd.api.types.is_numeric_dtype(reference_col)
            compare_is_numeric = pd.api.types.is_numeric_dtype(compare_col)

            # Try to detect if compare column contains numeric strings
            compare_can_be_numeric = False
            if not compare_is_numeric and reference_is_numeric:
                try:
                    # Try converting a sample to see if it's numeric
                    pd.to_numeric(compare_col.head(5), errors="coerce")
                    compare_can_be_numeric = True
                except Exception:
                    pass

            if (reference_is_numeric and compare_is_numeric) or (reference_is_numeric and compare_can_be_numeric):
                # Numeric comparison with relative tolerance
                # Use numpy.isclose for element-wise comparison
                # Convert compare to numeric if it's a string column with numeric values
                compare_as_numeric = pd.to_numeric(compare_col, errors="coerce")
                compare_numeric = pd.Series(compare_as_numeric).fillna(0).astype(float)
                reference_numeric = reference_col.fillna(0).astype(float)

                mask = ~np.isclose(
                    compare_numeric,
                    reference_numeric,
                    rtol=self.relative_tolerance,
                    atol=1e-9,
                    equal_nan=True,
                )

                if mask.any():
                    # mask is a numpy array, so we need to count True values
                    num_mismatches = int(mask.sum())
                    mismatches.append(
                        f"Column '{col}' has {num_mismatches} mismatched numeric values",
                    )
            else:
                # String/object comparison (exact match, case-insensitive for strings)
                compare_str = compare_col.astype(str).str.strip().str.lower()
                reference_str = reference_col.astype(str).str.strip().str.lower()

                mask = compare_str != reference_str
                if mask.any():
                    # mask is a pandas Series, so we can use sum()
                    num_mismatches = int(mask.sum())
                    mismatches.append(f"Column '{col}' has {num_mismatches} mismatched values")

        if mismatches:
            return ComparisonResult(
                matched=False,
                explanation="; ".join(mismatches),
                num_rows_compared=len(compare_df),
                num_rows_reference=len(reference_df),
            )

        return ComparisonResult(
            matched=True,
            explanation="All rows and columns matched",
            num_rows_compared=len(compare_df),
            num_rows_reference=len(reference_df),
        )


class OrderedComparator(BaseDataFrameComparator):
    """Compare dataframes row-by-row in exact order.

    This comparator preserves the ORDER BY from SQL queries and compares
    rows in their exact original order.
    """

    def compare(self, compare_df: pd.DataFrame, reference_df: pd.DataFrame) -> ComparisonResult:
        """Compare two dataframes row-by-row in exact order.

        Args:
            compare_df: The dataframe to compare against the reference.
            reference_df: The reference/baseline dataframe.

        Returns:
            ComparisonResult with match status and explanation.
        """
        try:
            compare_df_aligned, reference_df = self._align_columns(compare_df, reference_df)
            return self._compare_aligned(compare_df_aligned, reference_df)
        except DataFrameComparisonError as e:
            return ComparisonResult(
                matched=False,
                explanation=str(e),
                num_rows_compared=len(compare_df),
                num_rows_reference=len(reference_df),
            )


class AllColumnsSortedComparator(BaseDataFrameComparator):
    """Compare dataframes after sorting by all columns.

    This comparator sorts both dataframes by all columns before comparison,
    useful when order is not guaranteed but all column values matter.
    """

    def compare(self, compare_df: pd.DataFrame, reference_df: pd.DataFrame) -> ComparisonResult:
        """Compare two dataframes after sorting by all columns.

        Args:
            compare_df: The dataframe to compare against the reference.
            reference_df: The reference/baseline dataframe.

        Returns:
            ComparisonResult with match status and explanation.
        """
        try:
            compare_df_aligned, reference_df = self._align_columns(compare_df, reference_df)

            # Sort both dataframes by all columns before comparing
            compare_sorted = compare_df_aligned.sort_values(by=list(compare_df_aligned.columns)).reset_index(drop=True)
            reference_sorted = reference_df.sort_values(by=list(reference_df.columns)).reset_index(drop=True)

            return self._compare_aligned(compare_sorted, reference_sorted)

        except DataFrameComparisonError as e:
            return ComparisonResult(
                matched=False,
                explanation=str(e),
                num_rows_compared=len(compare_df),
                num_rows_reference=len(reference_df),
            )
        except Exception as e:
            return ComparisonResult(
                matched=False,
                explanation=f"All columns sorted comparison error: {e!s}",
                num_rows_compared=len(compare_df),
                num_rows_reference=len(reference_df),
            )


class KeyedComparator(BaseDataFrameComparator):
    """Compare dataframes after sorting by specified key columns.

    This comparator sorts both dataframes by a set of key columns before comparison,
    useful when the order matters but only specific columns determine it.
    """

    def __init__(
        self,
        relative_tolerance: float = 0.01,
        strict_columns: bool = False,
        keys: list[str] | None = None,
    ):
        """Initialize the keyed comparator.

        Args:
            relative_tolerance: Relative tolerance for numeric column comparisons (e.g., 0.01 = 1%).
            strict_columns: If True, require exact column names and order.
            keys: List of key columns for sorting before comparison.
        """
        super().__init__(relative_tolerance=relative_tolerance, strict_columns=strict_columns)
        self.keys = keys if keys is not None else []

    def compare(self, compare_df: pd.DataFrame, reference_df: pd.DataFrame) -> ComparisonResult:
        """Compare two dataframes after sorting by key columns.

        Args:
            compare_df: The dataframe to compare against the reference.
            reference_df: The reference/baseline dataframe.

        Returns:
            ComparisonResult with match status and explanation.
        """
        try:
            compare_df_aligned, reference_df = self._align_columns(compare_df, reference_df)

            # Verify keys exist
            for key in self.keys:
                if key not in compare_df_aligned.columns or key not in reference_df.columns:
                    raise DataFrameComparisonError(f"Key column '{key}' not found in dataframes")

            # Sort both dataframes by keys
            compare_sorted = compare_df_aligned.sort_values(by=self.keys).reset_index(drop=True)
            reference_sorted = reference_df.sort_values(by=self.keys).reset_index(drop=True)

            # Compare row by row
            return self._compare_aligned(compare_sorted, reference_sorted)

        except DataFrameComparisonError as e:
            return ComparisonResult(
                matched=False,
                explanation=str(e),
                num_rows_compared=len(compare_df),
                num_rows_reference=len(reference_df),
            )
        except Exception as e:
            return ComparisonResult(
                matched=False,
                explanation=f"Keyed comparison error: {e!s}",
                num_rows_compared=len(compare_df),
                num_rows_reference=len(reference_df),
            )


class ValuesOnlyComparator(BaseDataFrameComparator):
    """Compare dataframes by value sets only, ignoring column names (BIRD EX-style).

    This comparator converts each row to a tuple of normalized values and compares
    the resulting sets. Two dataframes match if they have the same set of row tuples,
    regardless of column names or row order.
    """

    def compare(self, compare_df: pd.DataFrame, reference_df: pd.DataFrame) -> ComparisonResult:
        """Compare two dataframes by value sets only.

        Args:
            compare_df: The dataframe to compare against the reference.
            reference_df: The reference/baseline dataframe.

        Returns:
            ComparisonResult with match status and explanation.
        """
        try:
            # Convert any NaN values to a string that will (hopefully) not match any other value.
            compare_df = compare_df.copy().fillna("__S4NULL__")
            reference_df = reference_df.copy().fillna("__S4NULL__")

            compare_cols = list(compare_df.columns)
            reference_cols = list(reference_df.columns)

            # Convert the dataframes to multisets (bags) of tuples to preserve duplicate counts.
            from collections import Counter

            compare_bag = Counter(map(tuple, compare_df.values))
            reference_bag = Counter(map(tuple, reference_df.values))

            if compare_bag == reference_bag:
                return ComparisonResult(
                    matched=True,
                    explanation=f"Values match ({len(compare_df)} rows, {len(compare_bag)} unique)",
                    num_rows_compared=len(compare_df),
                    num_rows_reference=len(reference_df),
                )

            # Convert to sets for detailed diagnostic comparison below
            compare_set = set(compare_bag.keys())
            reference_set = set(reference_bag.keys())

            # Build detailed diagnostic information
            details = []

            # Check for column count mismatch (common issue)
            if len(compare_cols) != len(reference_cols):
                details.append(
                    f"Column count mismatch: result has {len(compare_cols)} columns "
                    f"({compare_cols}), golden has {len(reference_cols)} columns ({reference_cols})"
                )

            # Calculate row differences
            missing_from_compare = reference_set - compare_set
            extra_in_compare = compare_set - reference_set

            if missing_from_compare:
                details.append(f"{len(missing_from_compare)} rows missing from result")
            if extra_in_compare:
                details.append(f"{len(extra_in_compare)} extra rows in result")

            # Check for duplicate count mismatches (sets match but counts differ)
            if not missing_from_compare and not extra_in_compare:
                # Same unique rows, but different duplicate counts
                count_diffs = []
                for row in compare_set:
                    compare_count = compare_bag[row]
                    reference_count = reference_bag[row]
                    if compare_count != reference_count:
                        count_diffs.append((row, compare_count, reference_count))
                if count_diffs:
                    details.append(
                        f"{len(count_diffs)} rows have different duplicate counts "
                        f"(result has {len(compare_df)} rows, reference has {len(reference_df)} rows)"
                    )
                    # Show a sample
                    sample = count_diffs[:2]
                    for row, cmp_cnt, ref_cnt in sample:
                        details.append(f"  Row {row}: result has {cmp_cnt}x, reference has {ref_cnt}x")

            # Add sample tuples for debugging (only if column counts match, otherwise too confusing)
            if len(compare_cols) == len(reference_cols) and (missing_from_compare or extra_in_compare):
                if missing_from_compare:
                    sample_missing = list(missing_from_compare)[:2]
                    details.append(f"Sample missing: {sample_missing}")
                if extra_in_compare:
                    sample_extra = list(extra_in_compare)[:2]
                    details.append(f"Sample extra: {sample_extra}")

            return ComparisonResult(
                matched=False,
                explanation=f"Value set mismatch: {'; '.join(details)}",
                num_rows_compared=len(compare_df),
                num_rows_reference=len(reference_df),
            )

        except Exception as e:
            return ComparisonResult(
                matched=False,
                explanation=f"Values-only comparison error: {e!s}",
                num_rows_compared=len(compare_df),
                num_rows_reference=len(reference_df),
            )


def create_comparator(
    match_mode: DataFrameMatchMode | str,
    *,
    keys: list[str] | None = None,
    relative_tolerance: float = 0.01,
    strict_columns: bool = False,
) -> BaseDataFrameComparator:
    """Create the appropriate dataframe comparator based on match mode.

    Args:
        match_mode: How to match rows (use DataFrameMatchMode enum or string):
            - ORDERED: Compare row-by-row in exact order (preserves ORDER BY from SQL)
            - ALL_COLUMNS_SORTED: Sort both dataframes by all columns before comparing
            - KEYED: Sort both dataframes by specified key columns before comparing
            - VALUES_ONLY: Compare row value sets only, ignoring column names (BIRD EX-style)
        keys: List of key columns for keyed matching (required if match_mode is KEYED).
        relative_tolerance: Relative tolerance for numeric column comparisons (e.g., 0.01 = 1%).
        strict_columns: If True, require exact column names and order, otherwise the compare dataframe
            can have a superset of columns compared to the reference dataframe.

    Returns:
        A specific comparator implementation.

    Raises:
        ValueError: If match_mode is KEYED but keys are not provided, or if match_mode is unknown.
    """
    mode = DataFrameMatchMode(match_mode) if isinstance(match_mode, str) else match_mode

    match mode:
        case DataFrameMatchMode.ORDERED:
            return OrderedComparator(
                relative_tolerance=relative_tolerance,
                strict_columns=strict_columns,
            )
        case DataFrameMatchMode.ALL_COLUMNS_SORTED:
            return AllColumnsSortedComparator(
                relative_tolerance=relative_tolerance,
                strict_columns=strict_columns,
            )
        case DataFrameMatchMode.KEYED:
            if keys is None:
                raise ValueError("Keys must be provided for KEYED match mode")
            return KeyedComparator(
                relative_tolerance=relative_tolerance,
                strict_columns=strict_columns,
                keys=keys,
            )
        case DataFrameMatchMode.VALUES_ONLY:
            return ValuesOnlyComparator(
                relative_tolerance=relative_tolerance,
                strict_columns=strict_columns,
            )
        case _:
            raise ValueError(f"Unknown match_mode: {mode}")


async def fetch_thread_dataframes(
    thread_id: str,
    client: httpx.AsyncClient,
    server_url: str = "http://localhost:8000",
) -> list[dict]:
    """Fetch list of dataframes in a thread.

    Args:
        thread_id: The thread ID.
        client: HTTP client for making requests.
        server_url: Base URL of the server. Defaults to "http://localhost:8000".

    Returns:
        List of dataframe metadata dictionaries.
    """
    url = f"{server_url}/api/v2/threads/{thread_id}/data-frames"

    response = await client.get(url, params={"num_samples": 0})
    response.raise_for_status()
    return response.json()


async def fetch_dataframe_data(
    thread_id: str,
    dataframe_name: str,
    client: httpx.AsyncClient,
    server_url: str = "http://localhost:8000",
) -> pd.DataFrame:
    """Fetch full data for a specific dataframe.

    Args:
        thread_id: The thread ID.
        dataframe_name: The name of the dataframe to fetch.
        client: HTTP client for making requests.
        server_url: Base URL of the server. Defaults to "http://localhost:8000".

    Returns:
        A pandas DataFrame containing the dataframe data.
    """
    import pandas as pd

    url = f"{server_url}/api/v2/threads/{thread_id}/data-frames/{dataframe_name}"
    params = {
        "offset": 0,
        "limit": -1,
        "output_format": "json",
    }

    response = await client.get(url, params=params)
    response.raise_for_status()
    data = response.json()

    df = pd.DataFrame(data)

    # Infer proper data types (convert string numbers to actual numbers)
    return df.infer_objects(copy=False).convert_dtypes()


def load_dataframe_from_file(file_path: Path) -> pd.DataFrame:
    """Load dataframe from filesystem based on file extension.

    Args:
        file_path: Path to the dataframe file.

    Returns:
        A pandas DataFrame containing the data.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        ValueError: If the file format is not supported.
    """
    import pandas as pd

    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    # Parse based on file extension
    file_lower = file_path.name.lower()
    if file_lower.endswith(".csv"):
        # Do not implicitly convert any string values to NaN other than NaN itself.
        return pd.read_csv(
            file_path,
            keep_default_na=False,
            na_values=[
                "",
                "#N/A",
                "#N/A N/A",
                "#NA",
                "-1.#IND",
                "-1.#QNAN",
                "-NaN",
                "-nan",
                "1.#IND",
                "1.#QNAN",
                "<NA>",
                "N/A",
                "NA",
                "NULL",
                "NaN",
                # 'None',       # Skip "None" as this exists in the data set as a valid string.
                "n/a",
                "nan",
                "null",
            ],
        )
    elif file_lower.endswith((".xlsx", ".xls")):
        return pd.read_excel(file_path)
    elif file_lower.endswith(".json"):
        return pd.read_json(file_path)
    elif file_lower.endswith(".parquet"):
        return pd.read_parquet(file_path)
    elif file_lower.endswith(".tsv"):
        return pd.read_csv(file_path, sep="\t")
    else:
        raise ValueError(f"Unsupported file format: {file_path}")
