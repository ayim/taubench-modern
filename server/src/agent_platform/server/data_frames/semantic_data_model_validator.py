from __future__ import annotations

from dataclasses import dataclass, field
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
    from pydantic import ValidationError
    from structlog.stdlib import BoundLogger

    from agent_platform.core.data_connections.data_connections import DataConnection
    from agent_platform.core.data_frames.semantic_data_model_types import (
        SemanticDataModel,
        VerifiedQuery,
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


def create_partial_verified_query_with_errors(
    verified_query_dict: dict,
    pydantic_error: ValidationError,
) -> VerifiedQuery:
    """Create a partial VerifiedQuery model from a dict with Pydantic validation errors.

    This function converts Pydantic ValidationError into structured ValidationMessages
    and attaches them to the appropriate error fields in a partial VerifiedQuery model.

    Used when retrieving verified queries from storage that fail validation due to
    schema changes or data corruption.

    Args:
        verified_query_dict: The original verified query data as a dict
        pydantic_error: The Pydantic ValidationError from model_validate()

    Returns:
        A partial VerifiedQuery model constructed with model_construct() that contains
        the original data plus validation errors attached to the appropriate error fields.
    """
    from agent_platform.core.data_frames.semantic_data_model_types import (
        ValidationMessageKind,
        ValidationMessageLevel,
        VerifiedQuery,
    )

    # Use model_construct to create partial model without validation
    verified_query = VerifiedQuery.model_construct(**verified_query_dict)

    # Initialize error lists if not already set
    if not verified_query.name_errors:
        verified_query.name_errors = []
    if not verified_query.nlq_errors:
        verified_query.nlq_errors = []
    if not verified_query.sql_errors:
        verified_query.sql_errors = []
    if not verified_query.parameter_errors:
        verified_query.parameter_errors = []

    # Convert Pydantic errors to ValidationMessages
    for error in pydantic_error.errors():
        field_path = error.get("loc", ())
        error_msg = error.get("msg", "")

        if not field_path:
            continue

        field_name = field_path[0] if field_path else ""

        # Route Pydantic validation errors to appropriate error list
        match field_name:
            case "name":
                verified_query.name_errors.append(
                    ValidationMessage(
                        message=error_msg,
                        level=ValidationMessageLevel.ERROR,
                        kind=ValidationMessageKind.VERIFIED_QUERY_MISSING_NAME_FIELD,
                    )
                )
            case "nlq":
                verified_query.nlq_errors.append(
                    ValidationMessage(
                        message=error_msg,
                        level=ValidationMessageLevel.ERROR,
                        kind=ValidationMessageKind.VERIFIED_QUERY_MISSING_NLQ_FIELD,
                    )
                )
            case "sql":
                verified_query.sql_errors.append(
                    ValidationMessage(
                        message=error_msg,
                        level=ValidationMessageLevel.ERROR,
                        kind=ValidationMessageKind.VERIFIED_QUERY_SQL_VALIDATION_FAILED,
                    )
                )
            case "parameters":
                # Try to get parameter name and field name from error location
                param_name = None
                param_field_name = None
                if len(field_path) >= 3:
                    # Error path like ("parameters", 0, "data_type")
                    param_index = field_path[1]
                    param_field_name = field_path[2]
                    if isinstance(param_index, int) and verified_query.parameters:
                        if param_index < len(verified_query.parameters):
                            param = verified_query.parameters[param_index]
                            if hasattr(param, "name"):
                                param_name = param.name
                            elif isinstance(param, dict):
                                param_name = param.get("name")

                # Enhance message with parameter name and field name if available
                if param_name and param_field_name:
                    enhanced_msg = f"Parameter '{param_name}', field '{param_field_name}': {error_msg}"
                elif param_name:
                    enhanced_msg = f"Parameter '{param_name}': {error_msg}"
                else:
                    enhanced_msg = error_msg

                verified_query.parameter_errors.append(
                    ValidationMessage(
                        message=enhanced_msg,
                        level=ValidationMessageLevel.ERROR,
                        kind=ValidationMessageKind.VERIFIED_QUERY_PARAMETERS_VALIDATION_FAILED,
                    )
                )
            case "verified_at" | "verified_by":
                # These are metadata fields, put errors in sql_errors as general errors
                verified_query.sql_errors.append(
                    ValidationMessage(
                        message=f"Field '{field_name}': {error_msg}",
                        level=ValidationMessageLevel.ERROR,
                        kind=ValidationMessageKind.VALIDATION_EXECUTION_ERROR,
                    )
                )
            case _:
                # Unknown field, put in sql_errors as general error
                verified_query.sql_errors.append(
                    ValidationMessage(
                        message=f"Field '{field_name}': {error_msg}",
                        level=ValidationMessageLevel.ERROR,
                        kind=ValidationMessageKind.VALIDATION_EXECUTION_ERROR,
                    )
                )

    return verified_query


@dataclass
class ColumnToInspect:
    name: str
    expr: str


@dataclass
class _LocatedValidationMessage:
    """A validation message with its location in the SDM."""

    message: ValidationMessage
    logical_table_name: str | None = None
    logical_column_name: str | None = None


@dataclass
class ValidationResult:
    """Result of contextual validation of a SemanticDataModel.

    This class holds the validation results and can lazily build the SDM with
    errors attached at the appropriate locations.
    """

    semantic_data_model: SemanticDataModel
    """The original, unmodified semantic data model."""

    _located_messages: list[_LocatedValidationMessage] = field(default_factory=list)
    """Internal list of validation messages with location metadata."""

    _sdm_with_errors: SemanticDataModel | None = field(default=None, repr=False)
    """Cached SDM with errors attached (built lazily)."""

    @property
    def errors(self) -> list[ValidationMessage]:
        """List of error-level validation messages."""
        from agent_platform.core.data_frames.semantic_data_model_types import ValidationMessageLevel

        return [m.message for m in self._located_messages if m.message.get("level") == ValidationMessageLevel.ERROR]

    @property
    def warnings(self) -> list[ValidationMessage]:
        """List of warning-level validation messages."""
        from agent_platform.core.data_frames.semantic_data_model_types import ValidationMessageLevel

        return [m.message for m in self._located_messages if m.message.get("level") == ValidationMessageLevel.WARNING]

    @property
    def is_valid(self) -> bool:
        """Returns True if there are no errors (warnings don't affect validity)."""
        return len(self.errors) == 0

    def semantic_data_model_with_errors(self) -> SemanticDataModel:
        """Build and return the SDM with errors/warnings attached at appropriate locations.

        The result is cached, so subsequent calls return the same instance.
        If there are no messages, returns the original SDM.
        """
        from agent_platform.core.data_frames.semantic_data_model_types import SemanticDataModel

        if self._sdm_with_errors is not None:
            return self._sdm_with_errors

        if not self._located_messages:
            self._sdm_with_errors = self.semantic_data_model
            return self._sdm_with_errors

        # Convert to dict for manipulation
        sdm_dict = self.semantic_data_model.model_dump()

        for located_msg in self._located_messages:
            self._attach_message_to_dict(
                sdm_dict,
                located_msg.message,
                located_msg.logical_table_name,
                located_msg.logical_column_name,
            )

        self._sdm_with_errors = SemanticDataModel.model_validate(sdm_dict)
        return self._sdm_with_errors

    @staticmethod
    def _append_error_to_dict(d: dict, error: ValidationMessage):
        """Append error to dict, handling None from model_dump()."""
        if d.get("errors") is None:
            d["errors"] = []
        d["errors"].append(error)

    @staticmethod
    def _attach_message_to_dict(
        sdm_dict: dict,
        validation_message: ValidationMessage,
        logical_table_name: str | None,
        logical_column_name: str | None,
    ):
        """Attach a validation message to the SDM dict at the appropriate location."""
        column_groups = ["dimensions", "facts", "time_dimensions", "metrics"]

        if logical_table_name is None and logical_column_name is None:
            ValidationResult._append_error_to_dict(sdm_dict, validation_message)
            return

        tables = sdm_dict.get("tables") or []

        if logical_column_name is not None:
            table = next((t for t in tables if t.get("name") == logical_table_name), None)
            if not table:
                raise ValueError(f"Logical table {logical_table_name} not found in semantic data model")
            for group in column_groups:
                columns = table.get(group) or []
                column = next((c for c in columns if c.get("name") == logical_column_name), None)
                if column:
                    ValidationResult._append_error_to_dict(column, validation_message)
                    return
            raise ValueError(f"Logical column {logical_column_name} not found in logical table {logical_table_name}")

        if logical_table_name is not None:
            table = next((t for t in tables if t.get("name") == logical_table_name), None)
            if not table:
                raise ValueError(f"Logical table {logical_table_name} not found in semantic data model")
            ValidationResult._append_error_to_dict(table, validation_message)


class SemanticDataModelValidator:
    """Validates a SemanticDataModel against external resources (contextual validation).

    This validator performs CONTEXTUAL validation only:
    - Do referenced data connections exist and can we connect?
    - Do referenced files exist in the thread?
    - Do the columns defined in the SDM exist in the actual data sources?

    Prerequisites (caller's responsibility):
    - The SemanticDataModel must have passed Pydantic schema validation
    - The SemanticDataModel must have passed structural validation via
      validate_semantic_model_payload_and_extract_references()
    - The References must be extracted and passed to __init__

    This validator does NOT check:
    - Whether required fields are present (structural validation)
    - Whether table names are unique (structural validation)
    - Whether the JSON schema is correct (Pydantic validation)
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
        references: References,
        thread_id: str | None,
        storage: BaseStorage,
        user: AuthedUser,
    ):
        self.semantic_data_model = semantic_data_model
        self._references = references
        self.thread_id = thread_id
        self.storage = storage
        self.user = user
        self._located_messages: list[_LocatedValidationMessage] = []
        self._data_connections_by_id: dict[str, DataConnection] = {}
        self._uploaded_files_by_ref: dict[str, UploadedFile] = {}

    @property
    def references(self) -> References:
        return self._references

    def _add_validation_message(
        self,
        validation_message: ValidationMessage,
        *,
        logical_table_name: str | None = None,
        logical_column_name: str | None = None,
    ):
        """Add a validation message with location metadata.

        - If `logical_table_name` is provided, the message is associated with that table.
        - If `logical_column_name` is provided, you must also provide `logical_table_name`
          and the message is associated with that column.
        - If neither is provided, the message is associated with the SDM root.
        """
        if logical_column_name is not None and logical_table_name is None:
            raise ValueError("`logical_table_name` is required when `logical_column_name` is provided")

        self._located_messages.append(
            _LocatedValidationMessage(
                message=validation_message,
                logical_table_name=logical_table_name,
                logical_column_name=logical_column_name,
            )
        )

    async def _get_data_connection(self, data_connection_id: str) -> DataConnection | None:
        from agent_platform.core.data_frames.semantic_data_model_types import (
            ValidationMessageKind,
            ValidationMessageLevel,
        )

        if data_connection_id in self._data_connections_by_id:
            return self._data_connections_by_id[data_connection_id]
        try:
            data_connection = await self.storage.get_data_connection(data_connection_id)
        except DataConnectionNotFoundError:
            logical_table_names = self.references.data_connection_id_to_logical_table_names[data_connection_id]
            for logical_table_name in logical_table_names:
                validation_message = ValidationMessage(
                    message=f"Data connection {data_connection_id} not found for logical table "
                    f"name {logical_table_name}",
                    level=ValidationMessageLevel.ERROR,
                    kind=ValidationMessageKind.DATA_CONNECTION_NOT_FOUND,
                )
                self._add_validation_message(validation_message, logical_table_name=logical_table_name)
            return None
        self._data_connections_by_id[data_connection_id] = data_connection
        return data_connection

    def _get_logical_table_name_from_real_table_name(self, real_table_name: str) -> str:
        """Get the logical table name from the real table name."""
        tables = self.semantic_data_model.tables or []
        assert tables is not None  # validated through references
        table = next(
            (t for t in tables if t.get("base_table", {}).get("table") == real_table_name),
            None,
        )
        assert table is not None  # validated through references
        logical_table_name = table.get("name")
        assert logical_table_name is not None  # validated through references
        return logical_table_name

    def _get_logical_column_name_from_real_column_expr(self, real_table_name: str, column_expr: str) -> str:
        """Get the logical column name from the real table name and column expression."""
        logical_table_name = self._get_logical_table_name_from_real_table_name(real_table_name)

        tables = self.semantic_data_model.tables or []
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

        raise ValueError(f"Column with expr '{column_expr}' not found in table '{logical_table_name}'")

    def _get_columns_to_validate(self, logical_table_name: str) -> list[ColumnToInspect]:
        columns_to_validate: list[ColumnToInspect] = []
        logical_tables = self.semantic_data_model.tables or []
        if not logical_tables:
            return []
        logical_table = next((t for t in logical_tables if t.get("name") == logical_table_name), None)
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

    def _get_tables_with_data_connection_to_validate(self, data_connection_id: str) -> list[TableToInspect]:
        tables_to_validate: list[TableToInspect] = []
        logical_table_names = self.references.data_connection_id_to_logical_table_names[data_connection_id]
        for logical_table_name in logical_table_names:
            connection_info = self.references.logical_table_name_to_connection_info[logical_table_name]
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
        from agent_platform.core.data_frames.semantic_data_model_types import (
            ValidationMessageKind,
            ValidationMessageLevel,
        )

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
            validation_message = ValidationMessage(
                message=f"Tables in data connection {data_connection.name} could not be validated due to an error: {e}",
                level=ValidationMessageLevel.ERROR,
                kind=ValidationMessageKind.DATA_CONNECTION_CONNECTION_FAILED,
            )
            self._add_validation_message(validation_message)
            return

        for real_table_name, error in errors.items():
            logical_table_name = self._get_logical_table_name_from_real_table_name(real_table_name)
            self._add_validation_message(error, logical_table_name=logical_table_name)

        # Now we validate the columns
        try:
            errors = await inspector.validate_column_expressions()
        except Exception as e:
            validation_message = ValidationMessage(
                message=f"Columns in data connection {data_connection.name} "
                f"could not be validated due to an error: {e}",
                level=ValidationMessageLevel.ERROR,
                kind=ValidationMessageKind.DATA_CONNECTION_CONNECTION_FAILED,
            )
            self._add_validation_message(validation_message)
            return

        for real_table_name, column_errors in errors.items():
            # Get logical table name once for this table
            logical_table_name = self._get_logical_table_name_from_real_table_name(real_table_name)

            for real_column_expr, error in column_errors.items():
                if real_column_expr == TABLE_VALIDATION_ERROR_KEY:
                    # Table-level error from column validation
                    self._add_validation_message(error, logical_table_name=logical_table_name)
                    continue
                logical_column_name = self._get_logical_column_name_from_real_column_expr(
                    real_table_name, real_column_expr
                )
                self._add_validation_message(
                    error,
                    logical_table_name=logical_table_name,
                    logical_column_name=logical_column_name,
                )

    def _add_validation_message_for_file_reference(
        self,
        file_reference: _FileReference,
        validation_message: ValidationMessage,
    ):
        """Add a validation message for a file reference to all logical tables that reference it."""
        logical_table_names = self.references.file_reference_to_logical_table_names[file_reference]
        for logical_table_name in logical_table_names:
            self._add_validation_message(validation_message, logical_table_name=logical_table_name)

    async def _get_uploaded_file(self, file_ref: str) -> UploadedFile | None:
        if self.thread_id is None:
            # We cannot retrieve file without thread context.
            return None

        if file_ref in self._uploaded_files_by_ref:
            return self._uploaded_files_by_ref[file_ref]

        thread = await self.storage.get_thread(self.user.user_id, self.thread_id)
        uploaded_file = await self.storage.get_file_by_ref(thread, file_ref, self.user.user_id)
        if not uploaded_file:
            return None
        self._uploaded_files_by_ref[file_ref] = uploaded_file
        return uploaded_file

    async def _validate_logical_tables_with_file_reference(
        self,
        file_reference: _FileReference,
    ):
        from agent_platform.core.data_frames.semantic_data_model_types import (
            ValidationMessageKind,
            ValidationMessageLevel,
        )

        uploaded_file = await self._get_uploaded_file(file_reference.file_ref)
        if not uploaded_file:
            if self.thread_id is None:
                validation_message = ValidationMessage(
                    message=f"File {file_reference.file_ref} cannot be resolved and validated without thread ID",
                    level=ValidationMessageLevel.WARNING,
                    kind=ValidationMessageKind.FILE_MISSING_THREAD_CONTEXT,
                )
                self._add_validation_message_for_file_reference(file_reference, validation_message)
            else:
                validation_message = ValidationMessage(
                    message=f"File {file_reference.file_ref} not found in thread {self.thread_id}",
                    level=ValidationMessageLevel.WARNING,
                    kind=ValidationMessageKind.FILE_NOT_FOUND,
                )
                self._add_validation_message_for_file_reference(file_reference, validation_message)
            return
        assert self.thread_id is not None  # it must be because we got an uploaded file above
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
            validation_message = ValidationMessage(
                message=f"File {file_reference.file_ref} could not be inspected due to an error: {e}",
                level=ValidationMessageLevel.ERROR,
                kind=ValidationMessageKind.FILE_INSPECTION_ERROR,
            )
            self._add_validation_message_for_file_reference(file_reference, validation_message)
            return

        # Validate each logical table that references this file
        for logical_table_name in self.references.file_reference_to_logical_table_names[file_reference]:
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
                validation_message = ValidationMessage(
                    message=f"Sheet not found in file {file_reference.file_ref}{sheet_info}",
                    level=ValidationMessageLevel.ERROR,
                    kind=ValidationMessageKind.FILE_SHEET_MISSING,
                )
                self._add_validation_message(validation_message, logical_table_name=logical_table_name)
                continue

            # Validate columns exist in the inspected data frame
            columns_to_validate = self._get_columns_to_validate(logical_table_name)
            inspected_columns = set(x.lower() for x in (matching_inspected_df.column_headers or []))

            for column in columns_to_validate:
                # Column expr should match a column in the inspected data frame
                column_expr_lower = column.expr.lower()
                if column_expr_lower not in inspected_columns:
                    validation_message = ValidationMessage(
                        message=f"Column '{column.expr}' not found in file {file_reference.file_ref}",
                        level=ValidationMessageLevel.ERROR,
                        kind=ValidationMessageKind.FILE_COLUMN_MISSING,
                    )
                    self._add_validation_message(
                        validation_message,
                        logical_table_name=logical_table_name,
                        logical_column_name=column.name,
                    )

    async def validate(self) -> ValidationResult:
        """Validate the semantic data model against external resources.

        Performs contextual validation: checks that referenced data connections
        and files exist and are accessible, and that columns exist in the data sources.

        Returns a ValidationResult containing:
        - The original semantic data model
        - Lists of errors and warnings
        - A method to get the SDM with errors attached
        """
        from agent_platform.core.data_frames.semantic_data_model_types import (
            ValidationMessageKind,
            ValidationMessageLevel,
        )

        # Add warnings for unresolved file references
        if self.references.tables_with_unresolved_file_references:
            for unresolved_file_reference in self.references.tables_with_unresolved_file_references:
                validation_message = ValidationMessage(
                    message=f"Logical table name {unresolved_file_reference.logical_table_name} "
                    f"has an unresolved file reference.",
                    level=ValidationMessageLevel.WARNING,
                    kind=ValidationMessageKind.FILE_REFERENCE_UNRESOLVED,
                )
                self._add_validation_message(
                    validation_message,
                    logical_table_name=unresolved_file_reference.logical_table_name,
                )

        # Validate all file references
        for file_reference in self.references.file_references:
            await self._validate_logical_tables_with_file_reference(file_reference)

        # Validate all data connections
        for data_connection_id in self.references.data_connection_ids:
            await self._validate_logical_tables_with_data_connection(data_connection_id)

        return ValidationResult(
            semantic_data_model=self.semantic_data_model,
            _located_messages=self._located_messages,
        )
