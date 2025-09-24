"""API endpoints for semantic data models."""

import typing
from dataclasses import dataclass
from typing import TypedDict

from fastapi import APIRouter, HTTPException
from structlog import get_logger

from agent_platform.core.payloads import (
    GenerateSemanticDataModelPayload,
    GenerateSemanticDataModelResponse,
    SetSemanticDataModelPayload,
)
from agent_platform.server.api.dependencies import StorageDependency
from agent_platform.server.auth import AuthedUser

router = APIRouter()
logger = get_logger(__name__)


_ThreadId = str
_FileRef = str


@dataclass(frozen=True, slots=True, unsafe_hash=True)
class _FileReference:
    thread_id: _ThreadId
    file_ref: _FileRef


@dataclass(slots=True)
class References:
    data_connection_ids: set[str]
    file_references: set[_FileReference]


def _validate_semantic_model_payload(payload: SetSemanticDataModelPayload) -> References:
    """Validate the semantic model payload."""
    from agent_platform.core.data_frames.semantic_data_model_types import SemanticDataModel

    semantic_data_model = typing.cast(SemanticDataModel, payload.semantic_model)
    assert semantic_data_model.get("name"), "'name' must be specified in the semantic data model."

    assert semantic_data_model.get("tables"), (
        "'tables' must be specified in the semantic data model."
    )

    references = References(data_connection_ids=set(), file_references=set())
    semantic_data_model_tables = semantic_data_model.get("tables", [])
    assert semantic_data_model_tables, (
        "'tables' must be specified (and not empty) in the semantic data model."
    )

    for index, table in enumerate(semantic_data_model_tables):
        table_name = table.get("name")
        assert table_name, (
            f"'name' must be specified in a semantic data model table. Index: {index}"
        )
        base_table = table.get("base_table")
        assert base_table, (
            f"'base_table' must be specified in a semantic data model table (table: {table_name})."
        )

        base_table_data_connection_id = base_table.get("data_connection_id")
        if not base_table_data_connection_id:
            # We're dealing with a file reference
            base_table_file_reference = base_table.get("file_reference")
            assert base_table_file_reference, (
                f"Either 'data_connection_id' or 'file_reference' must be specified in a semantic "
                f"data model base table (table: {table_name})."
            )
            thread_id = base_table_file_reference.get("thread_id")
            file_ref = base_table_file_reference.get("file_ref")
            _sheet_name = base_table_file_reference.get("sheet_name")

            assert thread_id, (
                f"'thread_id' must be specified in a semantic data model base table file reference"
                f" (table: {table_name})."
            )
            assert file_ref, (
                f"'file_ref' must be specified in a semantic data model base table file reference"
                f"(table: {table_name})."
            )
            references.file_references.add(_FileReference(thread_id=thread_id, file_ref=file_ref))
        else:
            # We're dealing with a data connection (fields as "usual").
            references.data_connection_ids.add(base_table_data_connection_id)

        # table is required for all use cases (for data connections and file references)
        base_table_table = base_table.get("table")
        assert base_table_table, (
            f"'table' must be specified in a semantic data model base table (table: {table_name})."
        )

    assert (
        references.data_connection_ids or references.file_references
    ), """In the semantic data model passed, no data connections or file references were found
        (so, base_tables may not be properly specified)."""

    return references


class _SetSemanticDataModeFileReference(TypedDict):
    thread_id: str
    file_ref: str


class _SetSemanticDataModelResult(TypedDict):
    semantic_data_model_id: str
    data_connection_ids: list[str]
    file_references: list[_SetSemanticDataModeFileReference]


@router.put("/{semantic_data_model_id}")
async def set_semantic_data_model(
    semantic_data_model_id: str,
    payload: SetSemanticDataModelPayload,
    user: AuthedUser,
    storage: StorageDependency,
) -> _SetSemanticDataModelResult:
    """Set a semantic data mode.
    Returns the ID of the semantic data model (the same one passed in) as well as the
    data connection IDs and file references that were used to set the semantic data model."""
    try:
        references = _validate_semantic_model_payload(payload)
        # Convert file_references from list of dicts to list of tuples
        file_references = [(ref.thread_id, ref.file_ref) for ref in references.file_references]

        # Set the semantic data model
        model_id: str = await storage.set_semantic_data_model(
            semantic_data_model_id=semantic_data_model_id,
            semantic_model=payload.semantic_model,
            data_connection_ids=list(references.data_connection_ids),
            file_references=file_references,
        )

        # Return the ID of the semantic data model (same one passed in)
        assert model_id == semantic_data_model_id
        return _SetSemanticDataModelResult(
            semantic_data_model_id=model_id,
            data_connection_ids=list(references.data_connection_ids),
            file_references=list(
                {"thread_id": ref.thread_id, "file_ref": ref.file_ref}
                for ref in references.file_references
            ),
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        logger.error("Error setting semantic data model", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.post("/")
async def create_semantic_data_model(
    payload: SetSemanticDataModelPayload,
    user: AuthedUser,
    storage: StorageDependency,
) -> _SetSemanticDataModelResult:
    """Create a new semantic data model.
    Returns the ID of the created semantic data model as well as the
    data connection IDs and file references that were used to create the semantic data model."""
    try:
        # Convert file_references from list of dicts to list of tuples
        references = _validate_semantic_model_payload(payload)
        # Convert file_references from list of dicts to list of tuples
        file_references = [(ref.thread_id, ref.file_ref) for ref in references.file_references]

        # Create the semantic data model (ID will be generated)
        model_id = await storage.set_semantic_data_model(
            semantic_data_model_id=None,
            semantic_model=payload.semantic_model,
            data_connection_ids=list(references.data_connection_ids),
            file_references=file_references,
        )

        # Return the ID of the created semantic data model
        return _SetSemanticDataModelResult(
            semantic_data_model_id=model_id,
            data_connection_ids=list(references.data_connection_ids),
            file_references=list(
                {"thread_id": ref.thread_id, "file_ref": ref.file_ref}
                for ref in references.file_references
            ),
        )
    except Exception as e:
        logger.error("Error creating semantic data model", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get("/{semantic_data_model_id}")
async def get_semantic_data_model(
    semantic_data_model_id: str,
    user: AuthedUser,
    storage: StorageDependency,
) -> dict:
    """Get a semantic data model by ID."""
    try:
        return await storage.get_semantic_data_model(semantic_data_model_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        logger.error("Error getting semantic data model", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.delete("/{semantic_data_model_id}")
async def delete_semantic_data_model(
    semantic_data_model_id: str,
    user: AuthedUser,
    storage: StorageDependency,
) -> None:
    """Delete a semantic data model by ID."""
    try:
        await storage.delete_semantic_data_model(semantic_data_model_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        logger.error("Error deleting semantic data model", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.post("/generate")
async def generate_semantic_data_model(
    payload: GenerateSemanticDataModelPayload,
    user: AuthedUser,
    storage: StorageDependency,
) -> GenerateSemanticDataModelResponse:
    """Generate a semantic data model from data connections and files."""
    try:
        from agent_platform.server.kernel.semantic_data_model_generator import (
            SemanticDataModelGenerator,
        )

        generator = SemanticDataModelGenerator()
        semantic_model = await generator.generate_semantic_data_model(
            name=payload.name,
            description=payload.description,
            data_connections_info=payload.data_connections_info,
            files_info=payload.files_info,
        )

        logger.info(
            "Successfully generated semantic data model",
            model_name=payload.name,
            user_id=user.user_id,
        )

        return GenerateSemanticDataModelResponse(semantic_model=semantic_model)
    except Exception as e:
        logger.error("Error generating semantic data model", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error") from e
