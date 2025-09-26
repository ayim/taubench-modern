import typing
from dataclasses import dataclass
from typing import Literal

if typing.TYPE_CHECKING:
    from agent_platform.core.data_frames.semantic_data_model_types import SemanticDataModel


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
class References:
    data_connection_ids: set[str]
    file_references: set[_FileReference]
    data_connection_id_to_logical_table_names: dict[str, set[str]]
    file_reference_to_logical_table_names: dict[_FileReference, set[str]]
    logical_table_name_to_connection_info: dict[str, DataConnectionInfo | FileConnectionInfo]
    errors: list[str]


def validate_semantic_model_payload_and_extract_references(  # noqa: C901, PLR0912, PLR0915
    semantic_data_model: "SemanticDataModel",
) -> References:
    """Validate the semantic model payload."""

    references = References(
        data_connection_ids=set(),
        file_references=set(),
        data_connection_id_to_logical_table_names=dict(),
        file_reference_to_logical_table_names=dict(),
        logical_table_name_to_connection_info=dict(),
        errors=[],
    )

    def add_error(error: str):
        references.errors.append(error)

    if not semantic_data_model.get("name"):
        add_error("'name' must be specified in the semantic data model.")
        return references

    if not semantic_data_model.get("tables"):
        add_error("'tables' must be specified in the semantic data model.")
        return references

    semantic_data_model_tables = semantic_data_model.get("tables", [])
    if not semantic_data_model_tables:
        add_error("'tables' must be specified (and not empty) in the semantic data model.")
        return references

    for index, table in enumerate(semantic_data_model_tables):
        logical_table_name = table.get("name")
        if not logical_table_name:
            add_error(f"'name' must be specified in a semantic data model table. Index: {index}")
            continue

        base_table = table.get("base_table")
        if not base_table:
            add_error(
                f"'base_table' must be specified in a semantic data model table"
                f" (table: {logical_table_name})."
            )
            continue

        base_table_table = base_table.get("table")
        if not base_table_table:
            add_error(
                f"'table' must be specified in a semantic data model base table"
                f" (table: {logical_table_name})."
            )
            continue

        base_table_data_connection_id = base_table.get("data_connection_id")
        if not base_table_data_connection_id:
            # We're dealing with a file reference
            base_table_file_reference = base_table.get("file_reference")
            if not base_table_file_reference:
                add_error(
                    f"Either 'data_connection_id' or 'file_reference' must be specified in a "
                    f"semantic data model base table (table: {logical_table_name})."
                )
                continue

            thread_id = base_table_file_reference.get("thread_id")
            file_ref = base_table_file_reference.get("file_ref")
            sheet_name = base_table_file_reference.get("sheet_name")

            if not thread_id:
                add_error(
                    f"'thread_id' must be specified in a semantic data model base table file "
                    f"reference (table: {logical_table_name})."
                )
                continue

            if not thread_id:
                add_error(
                    f"'thread_id' must be specified in a semantic data model base table file "
                    f"reference (table: {logical_table_name})."
                )
                continue

            if not file_ref:
                add_error(
                    f"'file_ref' must be specified in a semantic data model base table file "
                    f"reference (table: {logical_table_name})."
                )
                continue

            file_reference = _FileReference(
                thread_id=thread_id, file_ref=file_ref, sheet_name=sheet_name
            )
            references.file_references.add(file_reference)
            references.file_reference_to_logical_table_names.setdefault(file_reference, set()).add(
                logical_table_name
            )
            if references.logical_table_name_to_connection_info.get(logical_table_name):
                add_error(
                    f"Logical table name {logical_table_name} is referenced more than once in "
                    "the semantic data model."
                )
                continue

            references.logical_table_name_to_connection_info[logical_table_name] = (
                FileConnectionInfo(
                    kind="file",
                    thread_id=thread_id,
                    file_ref=file_ref,
                    sheet_name=sheet_name,
                    logical_table=logical_table_name,
                    real_table=base_table_table,
                )
            )
        else:
            # We're dealing with a data connection (fields as "usual").
            references.data_connection_ids.add(base_table_data_connection_id)
            references.data_connection_id_to_logical_table_names.setdefault(
                base_table_data_connection_id, set()
            ).add(logical_table_name)
            if references.logical_table_name_to_connection_info.get(logical_table_name):
                add_error(
                    f"Logical table name {logical_table_name} is referenced more than once in "
                    "the semantic data model."
                )
                continue

            references.logical_table_name_to_connection_info[logical_table_name] = (
                DataConnectionInfo(
                    kind="data_connection",
                    data_connection_id=base_table_data_connection_id,
                    database=base_table.get("database") or "",
                    schema=base_table.get("schema") or "",
                    logical_table=logical_table_name,
                    real_table=base_table_table,
                )
            )

    if not (references.data_connection_ids or references.file_references):
        add_error(
            """In the semantic data model passed, no data connections or file references were found
            (so, base_tables may not be properly specified)."""
        )
        return references

    return references
