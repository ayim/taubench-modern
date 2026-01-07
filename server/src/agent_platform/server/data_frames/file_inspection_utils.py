"""Utilities for inspecting files and converting them to data connection inspection formats.

This module provides functions to inspect files (CSV, Excel) and convert them
into TableInfo and ColumnInfo objects that match the data connection inspection API format.
"""

from __future__ import annotations

import typing

if typing.TYPE_CHECKING:
    from typing import Any

    from agent_platform.core.payloads.data_connection import ColumnInfo, TableInfo
    from agent_platform.server.data_frames.data_reader import DataReaderSheet
else:
    from agent_platform.core.payloads.data_connection import ColumnInfo, TableInfo


def infer_data_type(sample_values: list[Any]) -> str:
    """Infer data type from sample values using pandas.api.types.infer_dtype.

    Args:
        sample_values: List of sample values from a column

    Returns:
        A string representing the inferred data type: "numeric", "boolean", "string", etc.
    """
    if not sample_values:
        return "string"

    # Filter out None values for type inference
    non_null_values = [v for v in sample_values if v is not None]

    if not non_null_values:
        return "string"

    # Import pandas inside the function to avoid heavy import at module level
    import pandas.api.types

    # Use pandas infer_dtype for more accurate type detection
    try:
        inferred = pandas.api.types.infer_dtype(non_null_values, skipna=True)
    except Exception:
        # If pandas fails for any reason, default to string
        return "string"

    # Map pandas inferred types to our data type strings
    # pandas.infer_dtype returns strings like: 'integer', 'floating', 'boolean',
    # 'string', 'datetime', 'date', 'time', 'timedelta', 'mixed', etc.
    if inferred in ("integer", "floating", "mixed-integer-float", "decimal"):
        return "numeric"
    elif inferred == "boolean":
        return "boolean"
    elif inferred in ("datetime", "date", "time", "timedelta"):
        return "string"  # Keep as string for now
    else:
        # For 'string', 'unicode', 'mixed', 'unknown', etc., default to string
        return "string"


def create_column_info(header: str, sample_rows: list[list[Any]], column_index: int) -> ColumnInfo:
    """Create ColumnInfo from header and sample data.

    Args:
        header: The column header/name
        sample_rows: List of sample rows (each row is a list of values)
        column_index: The index of the column in each row

    Returns:
        A ColumnInfo object with inferred data type and sample values
    """
    sample_values = [row[column_index] for row in sample_rows if column_index < len(row)] if sample_rows else []
    data_type = infer_data_type(sample_values)

    return ColumnInfo(
        name=header,
        data_type=data_type,
        sample_values=sample_values if sample_values else None,
        primary_key=None,
        unique=None,
        description=None,
        synonyms=None,
    )


def create_table_info(sheet: DataReaderSheet, file_name: str, has_multiple_sheets: bool) -> TableInfo:
    """Create TableInfo from a data reader sheet.

    For files, we use the database field to store the filename, providing natural grouping
    like 'sales_data.xlsx.Q1' and 'sales_data.xlsx.Q2'. This mirrors the database.table
    pattern used for actual database connections.

    Args:
        sheet: A DataReaderSheet object containing the sheet data
        file_name: The name of the file
        has_multiple_sheets: Whether the file has multiple sheets

    Returns:
        A TableInfo object representing the sheet as a table
    """
    sample_rows = sheet.list_sample_rows(5)
    columns = []

    for i, header in enumerate(sheet.column_headers):
        column_info = create_column_info(header, sample_rows, i)
        columns.append(column_info)

    # For single-sheet files (like CSV or single-sheet Excel), use the filename as table name
    # For multi-sheet Excel files, use the sheet name as table name
    if has_multiple_sheets and sheet.name:
        table_name = sheet.name
    else:
        table_name = file_name

    return TableInfo(
        name=table_name,
        database=file_name,  # Use filename as "database" for grouping
        schema=None,
        description=f"Data from file: {file_name}",
        columns=columns,
    )
