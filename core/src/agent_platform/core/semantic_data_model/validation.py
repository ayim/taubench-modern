# ruff: noqa: E501
import typing
from dataclasses import dataclass
from typing import Literal

from agent_platform.core.semantic_data_model.types import ValidationMessage

if typing.TYPE_CHECKING:
    from agent_platform.core.semantic_data_model.types import SemanticDataModel


_ThreadId = str
_FileRef = str


@dataclass(frozen=True, slots=True, unsafe_hash=True)
class _FileReference:
    thread_id: _ThreadId
    file_ref: _FileRef
    sheet_name: str | None


@dataclass(slots=True)
class DataConnectionInfo:
    kind: Literal["data_connection"]
    data_connection_id: str
    database: str
    schema: str
    logical_table: str
    real_table: str


@dataclass(slots=True)
class FileConnectionInfo:
    kind: Literal["file"]
    thread_id: str
    file_ref: str
    sheet_name: str | None
    logical_table: str
    real_table: str


@dataclass(slots=True)
class DataFrameConnectionInfo:
    kind: Literal["data_frame"]
    data_frame_name: str


@dataclass(slots=True, frozen=True, unsafe_hash=True)
class EmptyFileReference:
    logical_table_name: str
    sheet_name: str | None
    base_table_table: str


@dataclass(slots=True)
class References:
    data_connection_ids: set[str]
    data_frame_names: set[str]
    file_references: set[_FileReference]
    data_connection_id_to_logical_table_names: dict[str, set[str]]
    file_reference_to_logical_table_names: dict[_FileReference, set[str]]
    logical_table_name_to_connection_info: dict[str, DataConnectionInfo | FileConnectionInfo | DataFrameConnectionInfo]
    errors: list[str]
    _structured_errors: list[ValidationMessage]
    tables_with_unresolved_file_references: set[EmptyFileReference]
    semantic_data_model_with_errors: "SemanticDataModel | None"


def validate_semantic_model_payload_and_extract_references(
    semantic_data_model: "SemanticDataModel",
) -> References:
    """Validate the semantic model payload."""
    from agent_platform.core.semantic_data_model.types import (
        SemanticDataModel,
        ValidationMessageKind,
        ValidationMessageLevel,
    )

    references = References(
        data_connection_ids=set(),
        file_references=set(),
        data_frame_names=set(),
        data_connection_id_to_logical_table_names=dict(),
        file_reference_to_logical_table_names=dict(),
        logical_table_name_to_connection_info=dict(),
        errors=[],
        _structured_errors=[],
        tables_with_unresolved_file_references=set(),
        semantic_data_model_with_errors=None,
    )
    # We work on a dict copy so we can add errors as we walk the tree.
    # Convert Pydantic model to dict for manipulation
    sdm_dict: dict = semantic_data_model.model_dump()

    def add_error(error: ValidationMessage):
        references._structured_errors.append(error)
        references.errors.append(error["message"])

    def append_error_to_dict(d: dict, error: ValidationMessage):
        """Append error to dict, handling None from model_dump()."""
        if d.get("errors") is None:
            d["errors"] = []
        d["errors"].append(error)

    if not sdm_dict.get("name"):
        error = ValidationMessage(
            message="'name' must be specified in the semantic data model.",
            level=ValidationMessageLevel.ERROR,
            kind=ValidationMessageKind.SEMANTIC_MODEL_MISSING_REQUIRED_FIELD,
        )
        add_error(error)
        append_error_to_dict(sdm_dict, error)
        references.semantic_data_model_with_errors = SemanticDataModel.model_validate(sdm_dict)
        return references

    # Allow SDMs with schemas but no tables - only error if both are missing/None
    tables_missing = "tables" not in sdm_dict or sdm_dict.get("tables") is None
    schemas_missing = "schemas" not in sdm_dict or sdm_dict.get("schemas") is None
    if tables_missing and schemas_missing:
        error = ValidationMessage(
            message="'tables' or 'schemas' must be specified in the semantic data model.",
            level=ValidationMessageLevel.ERROR,
            kind=ValidationMessageKind.SEMANTIC_MODEL_MISSING_REQUIRED_FIELD,
        )
        add_error(error)
        append_error_to_dict(sdm_dict, error)
        references.semantic_data_model_with_errors = SemanticDataModel.model_validate(sdm_dict)
        return references

    semantic_data_model_tables = sdm_dict.get("tables", [])
    semantic_data_model_schemas = sdm_dict.get("schemas", [])
    # Allow SDMs with schemas but no tables (schema-based SDMs)
    if not semantic_data_model_tables and not semantic_data_model_schemas:
        error = ValidationMessage(
            message="'tables' or 'schemas' must be specified (and not empty) in the semantic data model.",
            level=ValidationMessageLevel.ERROR,
            kind=ValidationMessageKind.SEMANTIC_MODEL_MISSING_REQUIRED_FIELD,
        )
        add_error(error)
        append_error_to_dict(sdm_dict, error)
        references.semantic_data_model_with_errors = SemanticDataModel.model_validate(sdm_dict)
        return references

    for index, table in enumerate(semantic_data_model_tables):
        logical_table_name = table.get("name")
        if not logical_table_name:
            error = ValidationMessage(
                message=f"'name' must be specified in a semantic data model table. Index: {index}",
                level=ValidationMessageLevel.ERROR,
                kind=ValidationMessageKind.SEMANTIC_MODEL_MISSING_REQUIRED_FIELD,
            )
            add_error(error)
            append_error_to_dict(table, error)
            continue

        base_table = table.get("base_table")
        if not base_table:
            error = ValidationMessage(
                message=(
                    f"'base_table' must be specified in a semantic data model table (table: {logical_table_name})."
                ),
                level=ValidationMessageLevel.ERROR,
                kind=ValidationMessageKind.SEMANTIC_MODEL_MISSING_REQUIRED_FIELD,
            )
            add_error(error)
            append_error_to_dict(table, error)
            continue

        base_table_table = base_table.get("table")
        if not base_table_table:
            error = ValidationMessage(
                message=(
                    f"'table' must be specified in a semantic data model base table (table: {logical_table_name})."
                ),
                level=ValidationMessageLevel.ERROR,
                kind=ValidationMessageKind.SEMANTIC_MODEL_MISSING_REQUIRED_FIELD,
            )
            add_error(error)
            append_error_to_dict(table, error)
            continue

        base_table_data_connection_id = base_table.get("data_connection_id")
        if not base_table_data_connection_id:
            # Check if there's an unresolved data_connection_name
            # This happens when an SDM is imported from a package but the referenced
            # data connection does not exist in the current environment
            unresolved_connection_name = base_table.get("data_connection_name")
            if unresolved_connection_name:
                error = ValidationMessage(
                    message=(
                        f"Data connection '{unresolved_connection_name}' not found for table "
                        f"'{logical_table_name}'. Please create the data connection in this "
                        "environment or update the semantic data model configuration."
                    ),
                    level=ValidationMessageLevel.ERROR,
                    kind=ValidationMessageKind.MISSING_DATA_CONNECTION,
                )
                add_error(error)
                append_error_to_dict(table, error)
                continue

            # We're dealing with a file reference or data frame
            base_table_file_reference = base_table.get("file_reference")
            if base_table_file_reference:
                thread_id = base_table_file_reference.get("thread_id")
                file_ref = base_table_file_reference.get("file_ref")
                sheet_name = base_table_file_reference.get("sheet_name")

                if file_ref and thread_id:
                    file_reference = _FileReference(thread_id=thread_id, file_ref=file_ref, sheet_name=sheet_name)
                    references.file_references.add(file_reference)
                    references.file_reference_to_logical_table_names.setdefault(file_reference, set()).add(
                        logical_table_name
                    )
                    if references.logical_table_name_to_connection_info.get(logical_table_name):
                        msg = (
                            f"Logical table name {logical_table_name} is referenced more than once in "
                            "the semantic data model."
                        )
                        error = ValidationMessage(
                            message=msg,
                            level=ValidationMessageLevel.ERROR,
                            kind=ValidationMessageKind.SEMANTIC_MODEL_DUPLICATE_TABLE,
                        )
                        add_error(error)
                        append_error_to_dict(table, error)
                        continue

                    references.logical_table_name_to_connection_info[logical_table_name] = FileConnectionInfo(
                        kind="file",
                        thread_id=thread_id,
                        file_ref=file_ref,
                        sheet_name=sheet_name,
                        logical_table=logical_table_name,
                        real_table=base_table_table,
                    )

                else:
                    # We have a file reference but it's empty
                    references.tables_with_unresolved_file_references.add(
                        EmptyFileReference(
                            logical_table_name=logical_table_name,
                            sheet_name=sheet_name,
                            base_table_table=base_table_table,
                        )
                    )

            else:
                # We're dealing with a data frame reference
                references.data_frame_names.add(base_table_table)

                if references.logical_table_name_to_connection_info.get(logical_table_name):
                    error = ValidationMessage(
                        message=(
                            f"Logical table name {logical_table_name} is referenced more than once "
                            "in the semantic data model."
                        ),
                        level=ValidationMessageLevel.ERROR,
                        kind=ValidationMessageKind.SEMANTIC_MODEL_DUPLICATE_TABLE,
                    )
                    add_error(error)
                    append_error_to_dict(table, error)
                    continue

                references.logical_table_name_to_connection_info[logical_table_name] = DataFrameConnectionInfo(
                    kind="data_frame",
                    data_frame_name=base_table_table,
                )

        else:
            # We're dealing with a data connection (fields as "usual").
            references.data_connection_ids.add(base_table_data_connection_id)
            references.data_connection_id_to_logical_table_names.setdefault(base_table_data_connection_id, set()).add(
                logical_table_name
            )
            if references.logical_table_name_to_connection_info.get(logical_table_name):
                error = ValidationMessage(
                    message=(
                        f"Logical table name {logical_table_name} is referenced more than once "
                        "in the semantic data model."
                    ),
                    level=ValidationMessageLevel.ERROR,
                    kind=ValidationMessageKind.SEMANTIC_MODEL_DUPLICATE_TABLE,
                )
                add_error(error)
                append_error_to_dict(table, error)
                continue

            references.logical_table_name_to_connection_info[logical_table_name] = DataConnectionInfo(
                kind="data_connection",
                data_connection_id=base_table_data_connection_id,
                database=base_table.get("database") or "",
                schema=base_table.get("schema") or "",
                logical_table=logical_table_name,
                real_table=base_table_table,
            )

    # Set the semantic data model with errors if any were found
    if references.errors:
        references.semantic_data_model_with_errors = SemanticDataModel.model_validate(sdm_dict)

    return references
