import json
from typing import Annotated, Any

from fastapi import APIRouter, Form, UploadFile
from sema4ai_docint.models import DocumentLayout, Mapping, MappingRow
from sema4ai_docint.models.data_model import DataModel
from sema4ai_docint.utils import normalize_name
from starlette.concurrency import run_in_threadpool
from structlog import get_logger

from agent_platform.core.document_intelligence import DocumentLayoutSummary
from agent_platform.core.errors.base import PlatformError, PlatformHTTPError
from agent_platform.core.errors.responses import ErrorCode
from agent_platform.core.payloads import DocumentLayoutPayload
from agent_platform.core.payloads.document_intelligence import GenerateLayoutResponsePayload
from agent_platform.server.api.dependencies import (
    AgentServerClientDependency,
    DocIntDatasourceDependency,
    FileManagerDependency,
    StorageDependency,
)

# Shared helpers from main module
from agent_platform.server.api.private_v2.document_intelligence.services import (
    _get_or_upload_file,
    _get_thread_or_404,
)
from agent_platform.server.auth import AuthedUser

logger = get_logger(__name__)


router = APIRouter()


@router.get("/layouts")
async def get_all_layouts(docint_ds: DocIntDatasourceDependency) -> list[DocumentLayoutSummary]:
    """Get all layouts from the Document Intelligence database."""
    document_layouts = DocumentLayout.find_all(docint_ds)
    layout_summaries = []
    for layout in document_layouts:
        layout_summaries.append(
            DocumentLayoutSummary(
                name=layout.name,
                data_model=layout.data_model,
                summary=layout.summary,
            )
        )
    return layout_summaries


@router.get("/layouts/{layout_name}")
async def get_layout(
    layout_name: str,
    data_model_name: str,
    docint_ds: DocIntDatasourceDependency,
) -> DocumentLayoutPayload:
    """Get a layout by name and data model from the Document Intelligence database."""
    try:
        # Normalize the names
        normalized_layout_name = normalize_name(layout_name)
        normalized_data_model_name = normalize_name(data_model_name)

        # Find the layout in the database
        document_layout = DocumentLayout.find_by_name(
            docint_ds, normalized_data_model_name, normalized_layout_name
        )

        if not document_layout:
            raise PlatformHTTPError(
                error_code=ErrorCode.NOT_FOUND,
                message=f"Layout '{normalized_layout_name}' not found for data "
                f"model '{normalized_data_model_name}'",
            )

        # Convert DocumentLayout to DocumentLayoutPayload
        return DocumentLayoutPayload.model_validate(document_layout)

    except PlatformHTTPError:
        raise
    except Exception as e:
        logger.error(
            "Error getting layout",
            error=str(e),
            layout_name=layout_name,
            data_model_name=data_model_name,
        )
        raise PlatformHTTPError(ErrorCode.UNEXPECTED, "Failed to get layout") from e


@router.post("/layouts")
async def upsert_layout(
    payload: DocumentLayoutPayload,
    docint_ds: DocIntDatasourceDependency,
):
    """Upsert a layout into the Document Intelligence database.

    Behavior:
    - If a layout with the same name and data model exists, update it
      (extraction schema, translation schema, summary, extraction config, prompt).
    - Otherwise, insert a new layout.
    """
    try:
        normalized = DocumentLayoutPayload.model_validate(payload)

        # Try to find existing layout (ensure required fields are present)
        if normalized.data_model_name is None:
            raise PlatformHTTPError(
                error_code=ErrorCode.BAD_REQUEST,
                message="data_model_name is required for document layout creation",
            )
        if normalized.name is None:
            raise PlatformHTTPError(
                error_code=ErrorCode.BAD_REQUEST,
                message="name is required for document layout creation",
            )

        existing = DocumentLayout.find_by_name(
            docint_ds, normalized.data_model_name, normalized.name
        )
        if existing:
            existing.extraction_schema = (
                normalized.extraction_schema.model_dump(mode="json", exclude_none=True)
                if normalized.extraction_schema
                else None
            )
            existing.translation_schema = normalized.wrap_translation_schema()
            existing.summary = normalized.summary
            existing.extraction_config = normalized.extraction_config
            existing.system_prompt = normalized.prompt
            existing.update(docint_ds)
        else:
            layout = normalized.to_document_layout()
            layout.insert(docint_ds)

        return {"ok": True}
    except PlatformHTTPError:
        raise
    except Exception as e:
        logger.error("Error upserting layout", error=str(e))
        raise PlatformError(ErrorCode.UNEXPECTED, f"Failed to upsert layout: {e!s}") from e


@router.put("/layouts/{layout_name}")
async def update_layout(
    layout_name: str,
    data_model_name: str,
    payload: DocumentLayoutPayload,
    docint_ds: DocIntDatasourceDependency,
):
    """Partially update an existing layout in the Document Intelligence database.

    This is a traditional PUT endpoint that requires the layout to already exist,
    unlike the upsert endpoint which creates if it doesn't exist. It only updates
    the fields in the payload which are not null.
    """
    try:
        normalized_payload = DocumentLayoutPayload.model_validate(payload)

        # Find the existing layout
        existing_layout = DocumentLayout.find_by_name(docint_ds, data_model_name, layout_name)
        if existing_layout is None:
            raise PlatformHTTPError(
                error_code=ErrorCode.NOT_FOUND,
                message=f"Layout '{layout_name}' not found for data model '{data_model_name}'",
            )

        # Update the existing layout
        if normalized_payload.extraction_schema is not None:
            existing_layout.extraction_schema = (
                normalized_payload.extraction_schema.model_dump(mode="json", exclude_none=True)
                if normalized_payload.extraction_schema
                else None
            )
        if normalized_payload.translation_schema is not None:
            existing_layout.translation_schema = normalized_payload.wrap_translation_schema()
        if normalized_payload.summary is not None:
            existing_layout.summary = normalized_payload.summary
        if normalized_payload.extraction_config is not None:
            existing_layout.extraction_config = normalized_payload.extraction_config
        if normalized_payload.prompt is not None:
            existing_layout.system_prompt = normalized_payload.prompt

        existing_layout.update(docint_ds)

        return {"ok": True}
    except PlatformHTTPError:
        raise
    except Exception as e:
        logger.error(
            "Error updating layout",
            error=str(e),
            layout_name=layout_name,
            data_model_name=data_model_name,
        )
        raise PlatformHTTPError(ErrorCode.UNEXPECTED, "Layout update failed unexpectedly") from e


@router.delete("/layouts/{layout_name}")
async def delete_layout(
    layout_name: str,
    data_model_name: str,
    docint_ds: DocIntDatasourceDependency,
):
    """Delete a layout from the Document Intelligence database."""
    try:
        # Normalize the names
        normalized_layout_name = normalize_name(layout_name)
        normalized_data_model_name = normalize_name(data_model_name)

        # Find the layout
        layout = DocumentLayout.find_by_name(
            docint_ds, normalized_data_model_name, normalized_layout_name
        )
        if layout is None:
            raise PlatformHTTPError(
                error_code=ErrorCode.NOT_FOUND,
                message=f"Layout '{layout_name}' not found for data model '{data_model_name}'",
            )

        # Delete the layout
        deleted = layout.delete(docint_ds)
        if not deleted:
            raise PlatformHTTPError(ErrorCode.UNEXPECTED, "Failed to delete layout")

        return {"ok": True}
    except PlatformHTTPError:
        raise
    except Exception as e:
        logger.error(
            "Error deleting layout",
            error=str(e),
            layout_name=layout_name,
            data_model_name=data_model_name,
        )
        raise PlatformHTTPError(ErrorCode.UNEXPECTED, f"Failed to delete layout: {e!s}") from e


async def _generate_translation_rules(
    extraction_schema: dict[str, Any],
    data_model_schema: dict[str, Any],
    agent_server_client: AgentServerClientDependency,
):
    """Generate translation rules for a layout."""
    mapping_rules_text = await run_in_threadpool(
        agent_server_client.create_mapping,
        json.dumps(data_model_schema),
        json.dumps(extraction_schema),
    )
    mapping_rules = json.loads(mapping_rules_text)
    if not isinstance(mapping_rules, list):
        raise PlatformHTTPError(
            error_code=ErrorCode.UNEXPECTED,
            message="Generated mapping rules are not a list, please try again or provide "
            "a different data model or layout",
        )

    return Mapping(rules=[MappingRow(**rule) for rule in mapping_rules])


async def _generate_layout_name(
    file_name: str,
    agent_server_client: AgentServerClientDependency,
):
    """Generate a layout name for a document."""

    def _sync_generate_layout_name(file_ref: str, client: AgentServerClientDependency):
        images = [img.get("value") for img in client._file_to_images(file_ref)]
        images = [img for img in images if img is not None]
        if len(images) == 0:
            raise ValueError("No images found in the document")

        layout_name = client.generate_document_layout_name(images, file_ref)
        return normalize_name(layout_name)

    try:
        return await run_in_threadpool(_sync_generate_layout_name, file_name, agent_server_client)
    except ValueError as e:
        # Raised if the document is not an image, so the message should be end-user friendly
        raise PlatformHTTPError(
            error_code=ErrorCode.BAD_REQUEST,
            message=f"Failed to generate layout name: {e!s}.",
        ) from e


@router.post("/layouts/generate")
async def generate_layout_from_file(  # noqa: PLR0913
    file: UploadFile | str,  # a direct upload or a file ref
    data_model_name: str,
    thread_id: str,
    user: AuthedUser,
    storage: StorageDependency,
    file_manager: FileManagerDependency,
    docint_ds: DocIntDatasourceDependency,
    agent_server_client: AgentServerClientDependency,
    instructions: Annotated[str | None, Form(...)] = None,
) -> GenerateLayoutResponsePayload:
    """Generate a layout from a document."""
    thread = await _get_thread_or_404(storage, user.user_id, thread_id)

    uploaded_file, new_file = await _get_or_upload_file(
        file,
        thread=thread,
        user_id=user.user_id,
        storage=storage,
        file_manager=file_manager,
    )

    # get data model' schema
    data_model = DataModel.find_by_name(docint_ds, normalize_name(data_model_name))
    if not data_model:
        raise PlatformHTTPError(
            error_code=ErrorCode.NOT_FOUND,
            message=f"Data model {data_model_name} not found",
        )
    model_schema_json = json.dumps(data_model.model_schema, indent=2)

    # generate extraction schema
    try:
        extraction_schema = await run_in_threadpool(
            agent_server_client.generate_schema,
            uploaded_file.file_ref,
            model_schema_json,
            user_prompt=instructions,
        )
    except Exception as e:
        raise PlatformHTTPError(
            error_code=ErrorCode.UNEXPECTED,
            message="The generated layout schema is not valid. Please try again or provide "
            "a different data model or layout.",
        ) from e

    # Generate Layout name
    layout_name = await _generate_layout_name(uploaded_file.file_ref, agent_server_client)

    # Generate summary for the layout
    summary = await run_in_threadpool(
        agent_server_client.summarize_with_args,
        {
            "Layout name": layout_name,
            "Data model name": data_model.name,
            "Layout schema": extraction_schema,
        },
    )

    # Generate translation rules
    translation_rules = await _generate_translation_rules(
        extraction_schema,
        data_model.model_schema,
        agent_server_client,
    )

    # Generate layout
    layout = DocumentLayoutPayload.model_validate(
        {
            "name": layout_name,
            "data_model_name": data_model.name,
            "summary": summary,
            "extraction_schema": extraction_schema,
            "translation_schema": translation_rules,
            # We don't generate some fields OOTB.
            "extraction_config": None,
            "prompt": None,
            # These fields are only set when being persisted into the database.
            "created_at": None,
            "updated_at": None,
        }
    )

    return GenerateLayoutResponsePayload(
        layout=layout,
        file=uploaded_file if new_file else None,
    )
