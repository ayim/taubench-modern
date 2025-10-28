from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, Literal

from structlog import get_logger

from agent_platform.core.data_frames.semantic_data_model_types import ValidationMessage
from agent_platform.core.payloads.data_connection import (
    DataConnectionsInspectRequest,
    TableToInspect,
)
from agent_platform.server.api.private_v2.threads_data_frames import (
    inspect_file_as_data_frame,
)
from agent_platform.server.kernel.data_connection_inspector import (
    TABLE_VALIDATION_ERROR_KEY,
    DataConnectionInspector,
)
from agent_platform.server.storage.errors import DataConnectionNotFoundError

if TYPE_CHECKING:
    from structlog.stdlib import BoundLogger

    from agent_platform.core.data_connections.data_connections import DataConnection
    from agent_platform.core.data_frames.semantic_data_model_types import (
        Dimension,
        Fact,
        Metric,
        SemanticDataModel,
        TimeDimension,
    )
    from agent_platform.core.data_frames.semantic_data_model_validation import (
        References,
        _FileReference,
    )
    from agent_platform.core.files.files import UploadedFile
    from agent_platform.server.api.private_v2.threads_data_frames import (
        _DataFrameInspectionAPI,
    )
    from agent_platform.server.auth.handlers import AuthedUser
    from agent_platform.server.storage.base import BaseStorage

logger: BoundLogger = get_logger(__name__)


@dataclass
class ColumnToInspect:
    name: str
    expr: str


class SemanticDataModelValidator:
    """
    This class is responsible for validating a semantic data model against available files and
    data connections in a thread.

    If references can be resolved, further validation will be performed to ensure that the
    tables and columns defined in the semantic data model are actually present in the referenced
    files or data connections.

    If any of these references are not resolvable, this class will return a list of errors
    indicating the references that could not be resolved.
    """

    COLUMN_GROUPS: ClassVar[list[Literal["dimensions", "facts", "time_dimensions", "metrics"]]] = [
        "dimensions",
        "facts",
        "time_dimensions",
        "metrics",
    ]

    def __init__(
        self,
        semantic_data_model: SemanticDataModel,
        # Thread ID could be optional if we allowed for validation of only data connections or files
        thread_id: str,
        storage: BaseStorage,
        user: AuthedUser,
    ):
        self.semantic_data_model = semantic_data_model
        self._validated_semantic_data_model: SemanticDataModel | None = None
        self.thread_id = thread_id
        self.storage = storage
        self.user = user
        self._errors: list[ValidationMessage] = []
        self._validation_ran: bool = False
        self._is_valid: bool = False
        self._data_connections_by_id: dict[str, DataConnection] = {}
        self._references: References | None = None
        self._uploaded_files_by_ref: dict[str, UploadedFile] = {}

    def _get_references(self) -> References:
        from agent_platform.core.data_frames.semantic_data_model_validation import (
            validate_semantic_model_payload_and_extract_references,
        )

        return validate_semantic_model_payload_and_extract_references(self.semantic_data_model)

    @property
    def references(self) -> References:
        if self._references is None:
            self._references = self._get_references()
        return self._references

    def _add_validation_message(  # noqa: C901
        self,
        message: str,
        level: Literal["error", "warning"],
        *,
        logical_table_name: str | None = None,
        logical_column_name: str | None = None,
    ):
        """Adds a validation message with the specified level. It applies it to the
        semantic data model to the `errors` field depending on the additional arguments:

        - If `logical_table_name` is provided, it applies to the logical table with the given name.
        - If `logical_column_name` is provided, you must also provide `logical_table_name` and then
        it applies it to the dimension, time_dimencion, fact, or metric with the given name.
        - If neither `logical_table_name` nor `logical_column_name` are provided, it applies it
        to the semantic data model itself.
        """
        if level not in ["error", "warning"]:
            raise ValueError(f"Invalid level: {level}")
        if logical_column_name is not None and logical_table_name is None:
            raise ValueError(
                "`logical_table_name` is required when `logical_column_name` is provided"
            )
        validation_message = ValidationMessage(message=message, level=level)
        self._errors.append(validation_message)

        from copy import deepcopy

        if self._validated_semantic_data_model is None:
            semantic_data_model_with_errors = self.references.semantic_data_model_with_errors
            if self.references.errors and semantic_data_model_with_errors is not None:
                self._validated_semantic_data_model = semantic_data_model_with_errors
            else:
                self._validated_semantic_data_model = deepcopy(self.semantic_data_model)

        assert self._validated_semantic_data_model is not None  # Set above, never None here

        if logical_table_name is None and logical_column_name is None:
            self._validated_semantic_data_model.setdefault("errors", []).append(validation_message)  # type: ignore
            return

        # We'll be adding the message in tables somewhere
        tables = self._validated_semantic_data_model.get("tables") or []

        if logical_column_name is not None:
            table = next((t for t in tables if t.get("name") == logical_table_name), None)
            if not table:
                raise ValueError(
                    f"Logical table {logical_table_name} not found in semantic data model"
                )
            for group in self.COLUMN_GROUPS:
                columns: list[Dimension | TimeDimension | Fact | Metric] = table.get(group, [])
                column = next((c for c in columns if c.get("name") == logical_column_name), None)
                if column:
                    column.setdefault("errors", []).append(validation_message)  # type: ignore
                    return

            # Only raise if we checked all groups and never found it
            raise ValueError(
                f"Logical column {logical_column_name} not found in logical "
                f"table {logical_table_name}"
            )

        if logical_table_name is not None:
            table = next((t for t in tables if t.get("name") == logical_table_name), None)
            if not table:
                raise ValueError(
                    f"Logical table {logical_table_name} not found in semantic data model"
                )
            table.setdefault("errors", []).append(validation_message)  # type: ignore

    def _add_error(
        self,
        msg: str,
        *,
        logical_table_name: str | None = None,
        logical_column_name: str | None = None,
    ):
        self._add_validation_message(
            msg,
            "error",
            logical_table_name=logical_table_name,
            logical_column_name=logical_column_name,
        )

    def _add_warning(
        self,
        msg: str,
        *,
        logical_table_name: str | None = None,
        logical_column_name: str | None = None,
    ):
        self._add_validation_message(
            msg,
            "warning",
            logical_table_name=logical_table_name,
            logical_column_name=logical_column_name,
        )

    @property
    def errors(self) -> list[ValidationMessage]:
        """
        The list of validation messages found during validation, returns an empty list
        if validation was successful.

        If validation has not been run yet, raises a ValueError.
        """
        if not self._validation_ran:
            raise ValueError("Validation has not been run yet")
        return self._errors

    @property
    def is_valid(self) -> bool:
        """
        Whether the semantic data model is valid, returns True if validation was successful,
        False otherwise.

        If validation has not been run yet, raises a ValueError.
        """
        if not self._validation_ran:
            raise ValueError("Validation has not been run yet")
        return self._is_valid

    @property
    def semantic_data_model_with_errors(self) -> SemanticDataModel:
        """
        The semantic data model with errors attached to it, returns the original semantic data model
        if validation was successful.

        If validation has not been run yet, raises a ValueError.
        """
        if not self._validation_ran:
            raise ValueError("Validation has not been run yet")
        if self._validated_semantic_data_model is not None:
            return self._validated_semantic_data_model
        return self.semantic_data_model

    async def _get_data_connection(self, data_connection_id: str) -> DataConnection | None:
        if data_connection_id in self._data_connections_by_id:
            return self._data_connections_by_id[data_connection_id]
        try:
            data_connection = await self.storage.get_data_connection(data_connection_id)
        except DataConnectionNotFoundError:
            logical_table_names = self.references.data_connection_id_to_logical_table_names[
                data_connection_id
            ]
            for logical_table_name in logical_table_names:
                self._add_error(
                    f"Data connection {data_connection_id} not found for logical table "
                    f"name {logical_table_name}",
                    logical_table_name=logical_table_name,
                )
            return None
        self._data_connections_by_id[data_connection_id] = data_connection
        return data_connection

    def _get_logical_table_name_from_real_table_name(self, real_table_name: str) -> str:
        """Get the logical table name from the real table name."""
        tables = self.semantic_data_model.get("tables", [])
        assert tables is not None  # validated through references
        table = next(
            (t for t in tables if t.get("base_table", {}).get("table") == real_table_name),
            None,
        )
        assert table is not None  # validated through references
        logical_table_name = table.get("name")
        assert logical_table_name is not None  # validated through references
        return logical_table_name

    def _get_logical_column_name_from_real_column_expr(
        self, real_table_name: str, column_expr: str
    ) -> str:
        """Get the logical column name from the real table name and column expression."""
        logical_table_name = self._get_logical_table_name_from_real_table_name(real_table_name)

        tables = self.semantic_data_model.get("tables", [])
        assert tables is not None  # validated through references
        table = next((t for t in tables if t.get("name") == logical_table_name), None)
        assert table is not None  # validated through references

        for group in self.COLUMN_GROUPS:
            columns = table.get(group) or []
            for column in columns:
                if column.get("expr") == column_expr:
                    logical_column_name = column.get("name")
                    assert logical_column_name is not None  # validated through references
                    return logical_column_name

        raise ValueError(
            f"Column with expr '{column_expr}' not found in table '{logical_table_name}'"
        )

    def _get_columns_to_validate(self, logical_table_name: str) -> list[ColumnToInspect]:
        columns_to_validate: list[ColumnToInspect] = []
        logical_tables = self.semantic_data_model.get("tables", [])
        if not logical_tables:
            return []
        logical_table = next(
            (t for t in logical_tables if t.get("name") == logical_table_name), None
        )
        if not logical_table:
            return []

        for group in self.COLUMN_GROUPS:
            columns_info = logical_table.get(group) or []
            for item in columns_info:
                columns_to_validate.append(
                    ColumnToInspect(
                        name=item.get("name"),
                        expr=item.get("expr"),
                    )
                )

        return columns_to_validate

    def _get_tables_with_data_connection_to_validate(
        self, data_connection_id: str
    ) -> list[TableToInspect]:
        tables_to_validate: list[TableToInspect] = []
        logical_table_names = self.references.data_connection_id_to_logical_table_names[
            data_connection_id
        ]
        for logical_table_name in logical_table_names:
            connection_info = self.references.logical_table_name_to_connection_info[
                logical_table_name
            ]
            assert connection_info.kind == "data_connection"  # validated through references
            columns_to_validate = self._get_columns_to_validate(logical_table_name)
            tables_to_validate.append(
                TableToInspect(
                    name=connection_info.real_table,
                    database=connection_info.database,
                    schema=connection_info.schema,
                    # We use expressions because we are using the real database schema.
                    columns_to_inspect=[c.expr for c in columns_to_validate],
                )
            )
        return tables_to_validate

    async def _validate_logical_tables_with_data_connection(self, data_connection_id: str):
        data_connection = await self._get_data_connection(data_connection_id)
        if not data_connection:
            return False

        request = DataConnectionsInspectRequest(
            tables_to_inspect=self._get_tables_with_data_connection_to_validate(data_connection_id),
            inspect_columns=True,
            n_sample_rows=0,
        )
        inspector = DataConnectionInspector(data_connection, request)
        try:
            errors = await inspector.validate_tables_exist()
        except Exception as e:
            self._add_error(
                f"Tables in data connection {data_connection.name} "
                f"could not be validated due to an error: {e}",
            )
            return

        for real_table_name, error in errors.items():
            logical_table_name = self._get_logical_table_name_from_real_table_name(real_table_name)
            self._add_error(error, logical_table_name=logical_table_name)

        # Now we validate the columns
        try:
            errors = await inspector.validate_column_expressions()
        except Exception as e:
            self._add_error(
                f"Columns in data connection {data_connection.name} "
                f"could not be validated due to an error: {e}",
            )
            return

        for real_table_name, column_errors in errors.items():
            # Get logical table name once for this table
            logical_table_name = self._get_logical_table_name_from_real_table_name(real_table_name)

            for real_column_expr, error in column_errors.items():
                if real_column_expr == TABLE_VALIDATION_ERROR_KEY:
                    self._add_error(error, logical_table_name=logical_table_name)
                    continue
                logical_column_name = self._get_logical_column_name_from_real_column_expr(
                    real_table_name, real_column_expr
                )
                self._add_error(
                    error,
                    logical_table_name=logical_table_name,
                    logical_column_name=logical_column_name,
                )

    async def _get_uploaded_file(self, file_ref: str) -> UploadedFile | None:
        if file_ref in self._uploaded_files_by_ref:
            return self._uploaded_files_by_ref[file_ref]
        thread = await self.storage.get_thread(self.user.user_id, self.thread_id)
        uploaded_file = await self.storage.get_file_by_ref(thread, file_ref, self.user.user_id)
        if not uploaded_file:
            return None
        self._uploaded_files_by_ref[file_ref] = uploaded_file
        return uploaded_file

    async def _validate_logical_tables_with_file_reference(  # noqa: C901
        self,
        file_reference: _FileReference,
    ):
        uploaded_file = await self._get_uploaded_file(file_reference.file_ref)
        if not uploaded_file:
            for logical_table_name in self.references.file_reference_to_logical_table_names[
                file_reference
            ]:
                self._add_error(
                    f"File {file_reference.file_ref} not found in thread {self.thread_id}",
                    logical_table_name=logical_table_name,
                )
            return

        try:
            inspected_data_frames: list[_DataFrameInspectionAPI] = await inspect_file_as_data_frame(
                user=self.user,
                tid=self.thread_id,
                storage=self.storage,
                num_samples=0,  # No samples are needed, just metadata!
                sheet_name=None,  # inspect all sheets
                file_id=uploaded_file.file_id,
                file_ref=uploaded_file.file_ref,
            )
        except Exception as e:
            for logical_table_name in self.references.file_reference_to_logical_table_names[
                file_reference
            ]:
                self._add_error(
                    f"File {file_reference.file_ref} could not be inspected due to an error: {e}",
                    logical_table_name=logical_table_name,
                )
            return

        # Validate each logical table that references this file
        for logical_table_name in self.references.file_reference_to_logical_table_names[
            file_reference
        ]:
            # Find the matching inspected data frame based on sheet name
            matching_inspected_df = None
            expected_sheet_name = file_reference.sheet_name

            for inspected_df in inspected_data_frames:
                # Match sheet name logic (similar to collector)
                if len(inspected_data_frames) == 1:
                    # Single sheet, matches by default
                    matching_inspected_df = inspected_df
                    break
                elif expected_sheet_name is None or inspected_df.sheet_name == expected_sheet_name:
                    matching_inspected_df = inspected_df
                    break

            if not matching_inspected_df:
                sheet_info = f" (sheet: {expected_sheet_name})" if expected_sheet_name else ""
                self._add_error(
                    f"Sheet not found in file {file_reference.file_ref}{sheet_info}",
                    logical_table_name=logical_table_name,
                )
                continue

            # Validate columns exist in the inspected data frame
            columns_to_validate = self._get_columns_to_validate(logical_table_name)
            inspected_columns = set(x.lower() for x in (matching_inspected_df.column_headers or []))

            for column in columns_to_validate:
                # Column expr should match a column in the inspected data frame
                column_expr_lower = column.expr.lower()
                if column_expr_lower not in inspected_columns:
                    self._add_error(
                        f"Column '{column.expr}' not found in file {file_reference.file_ref}",
                        logical_table_name=logical_table_name,
                        logical_column_name=column.name,
                    )

    async def validate(self) -> SemanticDataModel:
        """
        Validate the semantic data model against available files and data connections in a thread,
        and return the semantic data model with errors attached to it, if any. If there are no
        errors, returns the original semantic data model.
        """

        self._validation_ran = True
        self._is_valid = False

        # We see if there are already errors in the semantic data model
        if self.references.errors:
            for error in self.references.errors:
                # The initial validator does not use ValidationMessage, so we convert it to one.
                self._errors.append(ValidationMessage(message=error, level="error"))

            # We set the semantic data model with errors if there are any errors
            semantic_data_model_with_errors = self.references.semantic_data_model_with_errors
            if semantic_data_model_with_errors is not None:
                self._validated_semantic_data_model = semantic_data_model_with_errors

        # We add unresolved file references as warnings
        if self.references.tables_with_unresolved_file_references:
            for unresolved_file_reference in self.references.tables_with_unresolved_file_references:
                self._add_warning(
                    f"Logical table name {unresolved_file_reference.logical_table_name} has an "
                    f"unresolved file reference.",
                    logical_table_name=unresolved_file_reference.logical_table_name,
                )

        # We validate all other file references
        for file_reference in self.references.file_references:
            await self._validate_logical_tables_with_file_reference(file_reference)

        # We validate all data connections
        for data_connection_id in self.references.data_connection_ids:
            await self._validate_logical_tables_with_data_connection(data_connection_id)

        # Only count errors (not warnings) when determining validity
        has_errors = any(e["level"] == "error" for e in self._errors)
        self._is_valid = not has_errors
        self._validation_ran = True
        return self.semantic_data_model_with_errors
