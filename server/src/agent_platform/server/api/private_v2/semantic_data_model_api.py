"""API endpoints for semantic data models."""

import typing
from typing import TypedDict

from fastapi import APIRouter
from structlog import get_logger

from agent_platform.core.errors.base import PlatformHTTPError
from agent_platform.core.errors.responses import ErrorCode
from agent_platform.core.payloads import (
    GenerateSemanticDataModelPayload,
    GenerateSemanticDataModelResponse,
    SemanticDataModelWithAssociations,
    SetSemanticDataModelPayload,
)
from agent_platform.server.api.dependencies import StorageDependency
from agent_platform.server.auth import AuthedUser

router = APIRouter()
logger = get_logger(__name__)


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
    from agent_platform.core.data_frames.semantic_data_model_types import SemanticDataModel
    from agent_platform.core.data_frames.semantic_data_model_validation import (
        validate_semantic_model_payload_and_extract_references,
    )

    # Convert file_references from list of dicts to list of tuples
    semantic_data_model = typing.cast(SemanticDataModel, payload.semantic_model)

    try:
        references = validate_semantic_model_payload_and_extract_references(semantic_data_model)
        if references.errors:
            raise PlatformHTTPError(
                error_code=ErrorCode.BAD_REQUEST,
                message="The semantic data model is invalid: \n" + "\n".join(references.errors),
            )

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
    except PlatformHTTPError as e:
        raise e
    except ValueError as e:
        raise PlatformHTTPError(error_code=ErrorCode.NOT_FOUND, message=str(e)) from e
    except Exception as e:
        logger.error("Error setting semantic data model", error=str(e))
        raise PlatformHTTPError(
            error_code=ErrorCode.UNEXPECTED, message="Error setting semantic data model"
        ) from e


@router.post("/")
async def create_semantic_data_model(
    payload: SetSemanticDataModelPayload,
    user: AuthedUser,
    storage: StorageDependency,
) -> _SetSemanticDataModelResult:
    """Create a new semantic data model.
    Returns the ID of the created semantic data model as well as the
    data connection IDs and file references that were used to create the semantic data model."""
    from agent_platform.core.data_frames.semantic_data_model_types import SemanticDataModel
    from agent_platform.core.data_frames.semantic_data_model_validation import (
        validate_semantic_model_payload_and_extract_references,
    )

    # Convert file_references from list of dicts to list of tuples
    semantic_data_model = typing.cast(SemanticDataModel, payload.semantic_model)

    try:
        references = validate_semantic_model_payload_and_extract_references(semantic_data_model)
        if references.errors:
            raise PlatformHTTPError(
                error_code=ErrorCode.BAD_REQUEST,
                message="The semantic data model is invalid: \n" + "\n".join(references.errors),
            )

        # Convert file_references from list of dicts to list of tuples
        file_references = [(ref.thread_id, ref.file_ref) for ref in references.file_references]

        # Create the semantic data model (ID will be generated)
        model_id = await storage.set_semantic_data_model(
            semantic_data_model_id=None,
            semantic_model=semantic_data_model,
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
    except PlatformHTTPError as e:
        raise e
    except Exception as e:
        logger.error("Error creating semantic data model", error=str(e))
        raise PlatformHTTPError(
            error_code=ErrorCode.UNEXPECTED, message="Error creating semantic data model"
        ) from e


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
        raise PlatformHTTPError(error_code=ErrorCode.NOT_FOUND, message=str(e)) from e
    except Exception as e:
        logger.error("Error getting semantic data model", error=str(e))
        raise PlatformHTTPError(
            error_code=ErrorCode.UNEXPECTED, message="Error getting semantic data model"
        ) from e


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
        raise PlatformHTTPError(error_code=ErrorCode.NOT_FOUND, message=str(e)) from e
    except Exception as e:
        logger.error("Error deleting semantic data model", error=str(e))
        raise PlatformHTTPError(
            error_code=ErrorCode.UNEXPECTED, message="Error deleting semantic data model"
        ) from e


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

        if payload.agent_id:
            await generator.enhance_semantic_data_model(
                semantic_model, user=user, storage=storage, agent_id=payload.agent_id
            )
        else:
            logger.critical(
                "No agent ID provided when generating semantic data model, "
                "LLM improvement is not possible! This will become an error in the future."
            )

        logger.info(
            "Successfully generated semantic data model",
            model_name=payload.name,
            user_id=user.user_id,
        )

        return GenerateSemanticDataModelResponse(semantic_model=semantic_model)
    except Exception as e:
        logger.error("Error generating semantic data model", error=str(e))
        raise PlatformHTTPError(
            error_code=ErrorCode.UNEXPECTED, message="Error generating semantic data model"
        ) from e


@router.get("/", response_model=list[SemanticDataModelWithAssociations])
async def list_semantic_data_models(
    user: AuthedUser,
    storage: StorageDependency,
    agent_id: str | None = None,
    thread_id: str | None = None,
) -> list[SemanticDataModelWithAssociations]:
    """List semantic data models with optional filtering by agent_id or thread_id."""
    from agent_platform.core.data_frames.semantic_data_model_types import SemanticDataModel
    from agent_platform.core.data_frames.semantic_data_model_validation import (
        validate_semantic_model_payload_and_extract_references,
    )
    from agent_platform.server.storage.base import BaseStorage

    try:
        semantic_data_models_info = await storage.list_semantic_data_models(
            agent_id=agent_id, thread_id=thread_id
        )

        # Convert the results to SemanticDataModelWithAssociations objects
        semantic_data_models_with_associations = []
        semantic_data_model_info: BaseStorage.SemanticDataModelInfo
        for semantic_data_model_info in semantic_data_models_info:
            # Convert file references to FileReference objects
            from agent_platform.core.payloads import FileReference

            # Note: lots of 'str' to convert UUIDs to strings

            semantic_data_model_id = str(semantic_data_model_info["semantic_data_model_id"])
            semantic_data_model = typing.cast(
                SemanticDataModel, semantic_data_model_info["semantic_data_model"]
            )

            references = validate_semantic_model_payload_and_extract_references(semantic_data_model)
            file_references = [
                FileReference(
                    thread_id=str(ref.thread_id),
                    file_ref=ref.file_ref,
                    sheet_name=ref.sheet_name,
                )
                for ref in references.file_references
            ]

            semantic_data_models_with_associations.append(
                SemanticDataModelWithAssociations(
                    semantic_data_model_id=semantic_data_model_id,
                    semantic_data_model=semantic_data_model,
                    agent_ids=list(
                        str(agent_id) for agent_id in semantic_data_model_info["agent_ids"]
                    ),
                    thread_ids=list(
                        str(thread_id) for thread_id in semantic_data_model_info["thread_ids"]
                    ),
                    data_connection_ids=list(
                        str(data_connection_id)
                        for data_connection_id in references.data_connection_ids
                    ),
                    file_references=file_references,
                    errors_in_semantic_data_model=references.errors,
                )
            )

        return semantic_data_models_with_associations
    except Exception as e:
        logger.error("Error listing semantic data models", error=str(e))
        raise PlatformHTTPError(
            error_code=ErrorCode.UNEXPECTED, message="Error listing semantic data models"
        ) from e
