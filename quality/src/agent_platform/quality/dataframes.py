"""Dataframe utilities for comparison and retrieval."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

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


class DataFrameComparator:
    """Compare two dataframes with configurable tolerance and ordering.

    This class encapsulates the logic for comparing dataframes with different
    match modes (keyed vs unordered), numeric tolerances, and column requirements.
    """

    def __init__(
        self,
        match_mode: DataFrameMatchMode | str = DataFrameMatchMode.ALL_COLUMNS_SORTED,
        keys: list[str] | None = None,
        relative_tolerance: float = 0.01,
        strict_columns: bool = False,
    ):
        """Initialize the dataframe comparator.

        Args:
            match_mode: How to match rows (use DataFrameMatchMode enum or string):
                - ORDERED: Compare row-by-row in exact order (preserves ORDER BY from SQL)
                - ALL_COLUMNS_SORTED: Sort both dataframes by all columns before comparing
                - KEYED: Sort both dataframes by specified key columns before comparing
            keys: List of key columns for keyed matching (required if match_mode is KEYED).
            relative_tolerance: Relative tolerance for numeric column comparisons (e.g., 0.01 = 1%).
            strict_columns: If True, require exact column names and order, otherwise the compare dataframe
                can have a superset of columns compared to the reference dataframe.
        """
        self.match_mode = DataFrameMatchMode(match_mode) if isinstance(match_mode, str) else match_mode
        self.keys = keys
        self.relative_tolerance = relative_tolerance
        self.strict_columns = strict_columns

    def compare(self, compare_df: pd.DataFrame, reference_df: pd.DataFrame) -> dict[str, bool | str]:
        """Compare two dataframes with configured tolerance and ordering.

        Args:
            compare_df: The dataframe to compare against the reference.
            reference_df: The reference/baseline dataframe.

        Returns:
            Dictionary with 'matched' (bool) and 'explanation' (str).
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
                return {
                    "matched": False,
                    "explanation": (f"Column mismatch: missing={list(missing)}, extra={list(extra)}"),
                }
        else:
            # Check that reference columns are present in compare
            missing = set(reference_cols.keys()) - set(compare_cols.keys())
            if missing:
                return {
                    "matched": False,
                    "explanation": f"Missing required columns: {list(missing)}",
                }

        # Rename columns to match (use reference column names)
        col_rename: dict[str, str] = {}
        for norm_name, reference_col in reference_cols.items():
            if norm_name in compare_cols:
                col_rename[compare_cols[norm_name]] = reference_col

        compare_df_aligned = compare_df[list(col_rename.keys())].rename(columns=col_rename)  # type: ignore[call-overload]

        # Check row counts
        if len(compare_df_aligned) != len(reference_df):
            return {
                "matched": False,
                "explanation": (
                    f"Row count mismatch: compare={len(compare_df_aligned)}, reference={len(reference_df)}"
                ),
            }

        # Compare based on match_mode using match-case
        match self.match_mode:
            case DataFrameMatchMode.ORDERED:
                # Compare row-by-row in exact order
                return self._compare_aligned(compare_df_aligned, reference_df)
            case DataFrameMatchMode.KEYED:
                # Sort by specified key columns
                return self._compare_keyed(compare_df_aligned, reference_df)
            case DataFrameMatchMode.ALL_COLUMNS_SORTED:
                # Sort by all columns
                return self._compare_all_columns_sorted(compare_df_aligned, reference_df)
            case _:
                return {
                    "matched": False,
                    "explanation": f"Unknown match_mode: {self.match_mode}",
                }

    def _compare_keyed(self, compare_df: pd.DataFrame, reference_df: pd.DataFrame) -> dict[str, bool | str]:
        """Compare dataframes by sorting on key columns.

        Args:
            compare_df: Compare dataframe (columns already aligned).
            reference_df: Reference dataframe.

        Returns:
            Dictionary with 'matched' and 'explanation'.
        """
        try:
            # Verify keys exist
            if self.keys is None:
                return {"matched": False, "explanation": "Keys are None"}

            for key in self.keys:
                if key not in compare_df.columns or key not in reference_df.columns:
                    return {
                        "matched": False,
                        "explanation": f"Key column '{key}' not found in dataframes",
                    }

            # Sort both dataframes by keys
            compare_sorted = compare_df.sort_values(by=self.keys).reset_index(drop=True)
            reference_sorted = reference_df.sort_values(by=self.keys).reset_index(drop=True)

            # Compare row by row
            return self._compare_aligned(compare_sorted, reference_sorted)

        except Exception as e:
            return {"matched": False, "explanation": f"Keyed comparison error: {e!s}"}

    def _compare_all_columns_sorted(
        self,
        compare_df: pd.DataFrame,
        reference_df: pd.DataFrame,
    ) -> dict[str, bool | str]:
        """Compare dataframes by sorting on all columns.

        Args:
            compare_df: Compare dataframe (columns already aligned).
            reference_df: Reference dataframe.

        Returns:
            Dictionary with 'matched' and 'explanation'.
        """
        try:
            # Sort both dataframes by all columns before comparing
            compare_sorted = compare_df.sort_values(by=list(compare_df.columns)).reset_index(drop=True)
            reference_sorted = reference_df.sort_values(by=list(reference_df.columns)).reset_index(drop=True)

            return self._compare_aligned(compare_sorted, reference_sorted)

        except Exception as e:
            return {"matched": False, "explanation": f"All columns sorted comparison error: {e!s}"}

    def _compare_aligned(self, compare_df: pd.DataFrame, reference_df: pd.DataFrame) -> dict[str, bool | str]:
        """Compare two aligned (same order) dataframes with tolerance.

        Args:
            compare_df: Compare dataframe.
            reference_df: Reference dataframe.

        Returns:
            Dictionary with 'matched' and 'explanation'.
        """
        import numpy as np
        import pandas as pd

        try:
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
                return {"matched": False, "explanation": "; ".join(mismatches)}

            return {"matched": True, "explanation": "All rows and columns matched"}

        except Exception as e:
            return {"matched": False, "explanation": f"Aligned comparison error: {e!s}"}


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
        return pd.read_csv(file_path)
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
