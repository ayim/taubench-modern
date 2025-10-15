import json
from typing import Annotated

from fastapi import APIRouter, Form, UploadFile
from sema4ai_docint.models.data_model import DataModel
from sema4ai_docint.utils import normalize_name
from starlette.concurrency import run_in_threadpool

from agent_platform.core.document_intelligence.data_models import (
    CreateDataModelRequest,
    DataModelResponse,
    DataModelSummary,
    GenerateDataModelResponse,
    GenerateDescriptionResponse,
    UpdateDataModelRequest,
    summary_from_model,
)
from agent_platform.core.errors import ErrorCode, PlatformHTTPError
from agent_platform.core.files import UploadedFile
from agent_platform.core.payloads.document_intelligence import (
    ModifySchemaRequestPayload,
    ModifySchemaResponsePayload,
)
from agent_platform.server.api.dependencies import (
    AgentServerClientDependency,
    DIDependency,
    DocIntDatasourceDependency,
    FileManagerDependency,
    StorageDependency,
)
from agent_platform.server.api.private_v2.document_intelligence.services import (
    _get_or_upload_file,
    _get_thread_or_404,
)
from agent_platform.server.auth import AuthedUser

router = APIRouter()


@router.get("/data-models")
async def list_data_models(docint_ds: DocIntDatasourceDependency) -> list[DataModelSummary]:
    try:
        models = DataModel.find_all(docint_ds)
        return [summary_from_model(m) for m in models]
    except PlatformHTTPError:
        raise
    except Exception as e:
        raise PlatformHTTPError(ErrorCode.UNEXPECTED, f"Failed to list data models: {e!s}") from e


@router.post("/data-models", status_code=201)
async def create_data_model(
    payload: CreateDataModelRequest,
    docint_ds: DocIntDatasourceDependency,
    di_service: DIDependency,
) -> DataModelResponse:
    try:
        existing = DataModel.find_by_name(docint_ds, payload.data_model.name)
        if existing is not None:
            raise PlatformHTTPError(
                ErrorCode.CONFLICT, f"Data model already exists: {payload.data_model.name}"
            )

        result = await run_in_threadpool(
            di_service.data_model.create_from_schema,
            normalize_name(payload.data_model.name),
            payload.data_model.description,
            json.dumps(payload.data_model.model_schema),
        )
        model = DataModel.find_by_name(docint_ds, result["name"])
        if model is None:
            raise PlatformHTTPError(
                ErrorCode.UNEXPECTED, f"Data model not found: {payload.data_model.name}"
            )
        return DataModelResponse(data_model=model)
    except PlatformHTTPError:
        raise
    except Exception as e:
        raise PlatformHTTPError(ErrorCode.UNEXPECTED, f"Failed to create data model: {e!s}") from e


@router.get("/data-models/{model_name}")
async def get_data_model(
    model_name: str, docint_ds: DocIntDatasourceDependency
) -> DataModelResponse:
    try:
        model = DataModel.find_by_name(docint_ds, model_name)
        if model is None:
            raise PlatformHTTPError(ErrorCode.NOT_FOUND, f"Data model not found: {model_name}")
        return DataModelResponse(data_model=model)
    except PlatformHTTPError:
        raise
    except Exception as e:
        raise PlatformHTTPError(ErrorCode.UNEXPECTED, f"Failed to get data model: {e!s}") from e


@router.put("/data-models/{model_name}")
async def update_data_model(
    model_name: str, payload: UpdateDataModelRequest, docint_ds: DocIntDatasourceDependency
) -> dict[str, bool]:
    try:
        existing = DataModel.find_by_name(docint_ds, model_name)
        if existing is None:
            raise PlatformHTTPError(ErrorCode.NOT_FOUND, f"Data model not found: {model_name}")

        if payload.data_model.description:
            existing.description = payload.data_model.description
        if payload.data_model.model_schema:
            existing.model_schema = payload.data_model.model_schema
        if payload.data_model.views:
            existing.views = payload.data_model.views
        if payload.data_model.quality_checks:
            existing.quality_checks = payload.data_model.quality_checks
        if payload.data_model.prompt:
            existing.prompt = payload.data_model.prompt
        if payload.data_model.summary:
            existing.summary = payload.data_model.summary

        existing.update(docint_ds)
        return {"ok": True}
    except PlatformHTTPError:
        raise
    except Exception as e:
        raise PlatformHTTPError(ErrorCode.UNEXPECTED, f"Failed to update data model: {e!s}") from e


@router.delete("/data-models/{model_name}")
async def delete_data_model(
    model_name: str, docint_ds: DocIntDatasourceDependency
) -> dict[str, bool]:
    try:
        model = DataModel.find_by_name(docint_ds, model_name)
        if model is None:
            raise PlatformHTTPError(ErrorCode.NOT_FOUND, f"Data model not found: {model_name}")

        deleted = model.delete(docint_ds)
        if not deleted:
            raise PlatformHTTPError(ErrorCode.UNEXPECTED, "Failed to delete data model")
        return {"ok": True}
    except PlatformHTTPError:
        raise
    except Exception as e:
        raise PlatformHTTPError(ErrorCode.UNEXPECTED, f"Failed to delete data model: {e!s}") from e


@router.post("/data-models/generate")
async def generate_data_model_from_document(  # noqa: PLR0913
    file: UploadFile | str,
    thread_id: str,
    user: AuthedUser,
    storage: StorageDependency,
    file_manager: FileManagerDependency,
    agent_server_client: AgentServerClientDependency,
    instructions: Annotated[str | None, Form(...)] = None,
) -> GenerateDataModelResponse:
    """Generate a data model from a document."""

    thread = await _get_thread_or_404(storage, user.user_id, thread_id)

    uploaded_file, new_file = await _get_or_upload_file(
        file,
        thread=thread,
        user_id=user.user_id,
        storage=storage,
        file_manager=file_manager,
    )

    try:
        schema = await run_in_threadpool(
            agent_server_client.generate_schema,
            uploaded_file.file_ref,
            user_prompt=instructions,
        )
    except Exception as e:
        raise PlatformHTTPError(ErrorCode.UNEXPECTED, "Failed to generate data model") from e

    if new_file:
        return GenerateDataModelResponse(
            model_schema=schema,
            uploaded_file=uploaded_file,
        )
    else:
        return GenerateDataModelResponse(
            model_schema=schema,
        )


@router.post("/data-models/generate-description")
async def generate_data_model_description(
    thread_id: str,
    file_ref: str,
    user: AuthedUser,
    storage: StorageDependency,
    agent_server_client: AgentServerClientDependency,
) -> GenerateDescriptionResponse:
    """Generate a data model description from a document."""
    try:
        thread = await storage.get_thread(user.user_id, thread_id)
        if not thread:
            raise PlatformHTTPError(ErrorCode.NOT_FOUND, f"Thread {thread_id} not found")
        file = await storage.get_file_by_ref(thread, file_ref, user.user_id)
        if not file:
            raise PlatformHTTPError(ErrorCode.NOT_FOUND, f"File {file} not found")

        response = await run_in_threadpool(
            agent_server_client.summarize,
            file.file_ref,
        )
        return GenerateDescriptionResponse.model_validate(response)
    except PlatformHTTPError:
        raise
    except ValueError as e:
        raise PlatformHTTPError(
            ErrorCode.UNEXPECTED, f"Failed to generate data model description: {e!s}"
        ) from e


@router.post("/data-models/modify")
async def generate_schema_modifications(  # noqa: PLR0913
    payload: ModifySchemaRequestPayload,
    thread_id: str,
    user: AuthedUser,
    storage: StorageDependency,
    file_manager: FileManagerDependency,
    di_service: DIDependency,
) -> ModifySchemaResponsePayload:
    """Modify a schema based on provided instructions.

    Returns the modified schema.
    """
    thread = await _get_thread_or_404(storage, user.user_id, thread_id)

    file: UploadedFile | None = None
    if payload.file_name:
        file, _ = await _get_or_upload_file(
            payload.file_name,
            thread=thread,
            user_id=user.user_id,
            storage=storage,
            file_manager=file_manager,
        )

    try:
        updated_schema = await run_in_threadpool(
            di_service.data_model.modify_schema,
            payload.schema,
            payload.instructions,
            file.file_ref if file else None,
        )
        return ModifySchemaResponsePayload(schema=updated_schema)
    except Exception as e:
        raise PlatformHTTPError(
            error_code=ErrorCode.UNEXPECTED,
            message=f"Failed to modify schema: {e!s}",
        ) from e
