"""
Semantic data model generator for converting table/column information to semantic models.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from structlog import get_logger

from agent_platform.core.data_frames.semantic_data_model_types import (
    BaseTable,
    Dimension,
    Fact,
    FileReference,
    InputDataConnectionSnapshot,
    LogicalTable,
    SemanticDataModel,
    SemanticDataModelMetadata,
    TimeDimension,
)
from agent_platform.core.payloads.semantic_data_model_payloads import (
    ColumnInfo,
    DataConnectionInfo,
    FileInfo,
    TableInfo,
)

if TYPE_CHECKING:
    from agent_platform.core.data_frames.semantic_data_model_types import (
        DataConnectionSnapshotMetadata,
        FileSnapshotMetadata,
    )
    from agent_platform.server.storage import BaseStorage


logger = get_logger(__name__)


class SemanticDataModelGenerator:
    """Generator for creating semantic data models from table/column information."""

    def __init__(self, storage: BaseStorage | None = None):
        self.storage: BaseStorage | None = storage

    async def generate_semantic_data_model(
        self,
        name: str,
        description: str | None,
        data_connections_info: list[DataConnectionInfo],
        files_info: list[FileInfo],
        include_metadata: bool = True,
    ) -> SemanticDataModel:
        """Generate a semantic data model from data connections and files.

        Args:
            name: Name of the semantic data model
            description: Description of the semantic data model
            data_connections_info: List of data connection information
            files_info: List of file information
            include_metadata: Whether to include metadata snapshot (default: True)

        Returns:
            SemanticDataModel with optional metadata
        """
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

        # Generate metadata snapshot if requested
        if include_metadata:
            metadata = await self._create_metadata_snapshot(data_connections_info, files_info)
            if metadata:
                semantic_model["metadata"] = metadata

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
        if sample_values is None:
            return None
        ret = []
        for value in sample_values:
            if value is None or isinstance(value, str | int | float | bool):
                ret.append(value)
            else:
                ret.append(str(value))
        return ret

    async def _create_metadata_snapshot(
        self,
        data_connections_info: list[DataConnectionInfo],
        files_info: list[FileInfo],
    ) -> SemanticDataModelMetadata | None:
        """Create metadata container with inspection snapshots.

        Builds the metadata object containing inspection results and provenance information.
        Only creates metadata if inspection request/response data is provided in the input.

        Args:
            data_connections_info: Data connection info with optional
                inspect_request/inspect_response
            files_info: File info with optional inspect_response

        Returns:
            SemanticDataModelMetadata with snapshots, or None if inspection data is unavailable

        Note:
            Currently creates a snapshot for only the first data source (either first data
            connection or first file). Future versions may support multiple snapshots when
            SDMs span multiple data sources.
        """

        # For now, we create a snapshot for the first data source (either data connection or file)
        # Structure supports multiple snapshots for future use when SDMs can span multiple sources

        snapshots: list[InputDataConnectionSnapshot] = []

        if data_connections_info:
            # Create snapshot for data connection (currently only first one)
            dc_info = data_connections_info[0]
            # Only create snapshot if we have the inspection request/response
            if dc_info.inspect_request and dc_info.inspect_response:
                snapshot = await self._create_data_connection_snapshot(dc_info)
                snapshots.append(snapshot)
        elif files_info:
            # Create snapshot for file (currently only first one)
            file_info = files_info[0]
            # Only create snapshot if we have the inspection response
            if file_info.inspect_response:
                snapshot = self._create_file_snapshot(file_info)
                snapshots.append(snapshot)

        if snapshots:
            metadata: SemanticDataModelMetadata = {
                "input_data_connection_snapshots": snapshots,
            }
            return metadata

        return None

    async def _create_data_connection_snapshot(
        self,
        data_connection_info: DataConnectionInfo,
    ) -> InputDataConnectionSnapshot:
        """Create inspection snapshot for a data connection.

        Combines the inspection API response with provenance metadata (connection ID, name,
        and original request parameters) to create a complete snapshot.

        Args:
            data_connection_info: Must include inspect_request and inspect_response

        Returns:
            InputDataConnectionSnapshot ready to store in SDM metadata

        Raises:
            ValueError: If storage is not available or if inspect_request/response are missing
        """

        if not self.storage:
            raise ValueError("Storage is required to create data connection snapshot metadata")

        if not data_connection_info.inspect_response or not data_connection_info.inspect_request:
            raise ValueError(
                "Inspect response and request are required to create data "
                "connection snapshot metadata"
            )

        data_connection = await self.storage.get_data_connection(
            data_connection_info.data_connection_id
        )

        # Build request metadata
        request_metadata: DataConnectionSnapshotMetadata = {
            "data_connection_id": data_connection.id,
            "data_connection_name": data_connection.name,
            "data_connection_inspect_request": data_connection_info.inspect_request,
        }

        snapshot: InputDataConnectionSnapshot = {
            "kind": "data_connection",
            "inspection_result": data_connection_info.inspect_response,
            "inspection_request_info": request_metadata,
            "inspected_at": data_connection_info.inspect_response.inspected_at
            or datetime.now(UTC).isoformat(),
        }

        return snapshot

    def _create_file_snapshot(self, file_info: FileInfo) -> InputDataConnectionSnapshot:
        """Create inspection snapshot for a file.

        Combines the inspection API response with provenance metadata (file reference:
        thread_id, file_ref, sheet_name) to create a complete snapshot.

        Args:
            file_info: Must include inspect_response

        Returns:
            InputDataConnectionSnapshot ready to store in SDM metadata

        Raises:
            ValueError: If inspect_response is missing
        """

        if not file_info.inspect_response:
            raise ValueError("Inspect response is required to create file snapshot metadata")

        # Build file reference for provenance
        file_reference: FileReference = {
            "thread_id": file_info.thread_id,
            "file_ref": file_info.file_ref,
            "sheet_name": file_info.sheet_name,
        }

        # Build request metadata
        request_metadata: FileSnapshotMetadata = {"file_reference": file_reference}

        snapshot: InputDataConnectionSnapshot = {
            "kind": "file",
            "inspection_result": file_info.inspect_response,
            "inspection_request_info": request_metadata,
            "inspected_at": file_info.inspect_response.inspected_at
            or datetime.now(UTC).isoformat(),
        }

        return snapshot
