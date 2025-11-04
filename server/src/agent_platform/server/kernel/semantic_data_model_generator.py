"""
Semantic data model generator for converting table/column information to semantic models.
"""

from __future__ import annotations

from typing import Any

from structlog import get_logger

from agent_platform.core.data_frames.semantic_data_model_types import (
    BaseTable,
    Dimension,
    Fact,
    FileReference,
    LogicalTable,
    SemanticDataModel,
    TimeDimension,
)
from agent_platform.core.payloads.semantic_data_model_payloads import (
    ColumnInfo,
    DataConnectionInfo,
    FileInfo,
    TableInfo,
)

logger = get_logger(__name__)


class SemanticDataModelGenerator:
    """Generator for creating semantic data models from table/column information."""

    async def generate_semantic_data_model(
        self,
        name: str,
        description: str | None,
        data_connections_info: list[DataConnectionInfo],
        files_info: list[FileInfo],
    ) -> SemanticDataModel:
        """Generate a semantic data model from data connections and files."""
        tables = []

        # Process data connections
        for data_connection_info in data_connections_info:
            for table_info in data_connection_info.tables_info:
                logical_table = self._create_logical_table_from_data_connection(
                    table_info, data_connection_info.data_connection_id
                )
                tables.append(logical_table)

        # Process files
        for file_info in files_info:
            for table_info in file_info.tables_info:
                logical_table = self._create_logical_table_from_file(
                    table_info, file_info.thread_id, file_info.file_ref, file_info.sheet_name
                )
                tables.append(logical_table)

        semantic_model: SemanticDataModel = {
            "name": name,
            "description": description,
            "tables": tables,
        }

        return semantic_model

    def _create_logical_table_from_data_connection(
        self, table_info: TableInfo, data_connection_id: str
    ) -> LogicalTable:
        """Create a logical table from a data connection table info."""
        base_table: BaseTable = {
            "data_connection_id": data_connection_id,
            "database": table_info.database,
            "schema": table_info.schema,
            "table": table_info.name,
        }

        return self._create_logical_table(table_info, base_table)

    def _create_logical_table_from_file(
        self, table_info: TableInfo, thread_id: str, file_ref: str, sheet_name: str | None
    ) -> LogicalTable:
        """Create a logical table from a file table info."""
        file_reference: FileReference = {
            "thread_id": thread_id,
            "file_ref": file_ref,
            "sheet_name": sheet_name,
        }

        base_table: BaseTable = {
            "file_reference": file_reference,
            "table": table_info.name,
        }

        return self._create_logical_table(table_info, base_table)

    def _create_logical_table(self, table_info: TableInfo, base_table: BaseTable) -> LogicalTable:
        """Create a logical table from table info and base table."""
        dimensions: list[Dimension] = []
        facts: list[Fact] = []
        time_dimensions: list[TimeDimension] = []

        for column in table_info.columns:
            if self._is_dimension_column(column):
                dimension = self._create_dimension(column)
                dimensions.append(dimension)
            elif self._is_time_column(column):
                time_dim = self._create_time_dimension(column)
                time_dimensions.append(time_dim)
            elif self._is_numeric_column(column):
                fact = self._create_fact(column)
                facts.append(fact)
            else:
                dimension = self._create_dimension(column)
                dimensions.append(dimension)

        logical_table: LogicalTable = {
            "name": table_info.name,
            "base_table": base_table,
            "description": table_info.description,
            "dimensions": dimensions,
            "facts": facts,
            "time_dimensions": time_dimensions,
        }

        return logical_table

    def _is_dimension_column(self, column: ColumnInfo) -> bool:
        """Check if a column is a dimension column based on its data type."""
        name_lower = column.name.lower()
        if name_lower.endswith("_id") or "name" in name_lower:
            return True
        return False

    def _is_time_column(self, column: ColumnInfo) -> bool:
        """Check if a column is a time column based on its data type."""
        time_types = {
            "timestamp",
            "datetime",
            "date",
            "time",
            "timestamptz",
            "timetz",
            "timestamp with time zone",
            "timestamp without time zone",
        }
        return column.data_type.lower() in time_types

    def _is_numeric_column(self, column: ColumnInfo) -> bool:
        """Check if a column is numeric based on its data type."""
        numeric_types = {
            "int",
            "integer",
            "bigint",
            "smallint",
            "tinyint",
            "float",
            "double",
            "real",
            "numeric",
            "decimal",
            "money",
            "currency",
        }
        return column.data_type.lower() in numeric_types

    def _create_dimension(self, column: ColumnInfo) -> Dimension:
        """Create a dimension from column info."""
        dimension: Dimension = {
            "name": column.name,
            "expr": column.name,
            "data_type": column.data_type,
        }

        if column.description:
            dimension["description"] = column.description
        if column.synonyms:
            dimension["synonyms"] = column.synonyms
        if column.sample_values:
            dimension["sample_values"] = self._get_sample_values(column.sample_values)

        return dimension

    def _create_fact(self, column: ColumnInfo) -> Fact:
        """Create a fact from column info."""
        fact: Fact = {
            "name": column.name,
            "expr": column.name,
            "data_type": column.data_type,
        }

        if column.description:
            fact["description"] = column.description
        if column.synonyms:
            fact["synonyms"] = column.synonyms
        if column.sample_values:
            fact["sample_values"] = self._get_sample_values(column.sample_values)

        return fact

    def _create_time_dimension(self, column: ColumnInfo) -> TimeDimension:
        """Create a time dimension from column info."""
        time_dimension: TimeDimension = {
            "name": column.name,
            "expr": column.name,
            "data_type": column.data_type,
        }

        if column.description:
            time_dimension["description"] = column.description
        if column.synonyms:
            time_dimension["synonyms"] = column.synonyms
        if column.sample_values:
            time_dimension["sample_values"] = self._get_sample_values(column.sample_values)

        return time_dimension

    def _get_sample_values(
        self, sample_values: list[Any] | None
    ) -> list[str | int | float | bool | None] | None:
        """Get sample values as strings."""
        from types import NoneType

        if sample_values is None:
            return None
        ret = []
        for value in sample_values:
            if isinstance(value, str | int | float | bool | NoneType):
                ret.append(value)
            else:
                ret.append(str(value))
        return ret
