import json
from typing import Any

from fastapi import APIRouter, UploadFile
from sema4ai_docint.models.data_model import DataModel
from sema4ai_docint.utils import normalize_name
from starlette.concurrency import run_in_threadpool

from agent_platform.core.document_intelligence.data_models import (
    CreateDataModelRequest,
    UpdateDataModelRequest,
    model_to_spec_dict,
    summary_from_model,
)
from agent_platform.core.errors.base import PlatformHTTPError
from agent_platform.core.errors.responses import ErrorCode
from agent_platform.core.payloads.upload_file import UploadFilePayload
from agent_platform.server.api.dependencies import (
    AgentServerClientDependency,
    DIDependency,
    DocIntDatasourceDependency,
    FileManagerDependency,
    StorageDependency,
)
from agent_platform.server.auth import AuthedUser

router = APIRouter()


@router.get("/data-models")
async def list_data_models(docint_ds: DocIntDatasourceDependency):
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
) -> dict[str, Any]:
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
            json.dumps(payload.data_model.schema),
        )
        model = DataModel.find_by_name(docint_ds, result["name"])
        if model is None:
            raise PlatformHTTPError(
                ErrorCode.UNEXPECTED, f"Data model not found: {payload.data_model.name}"
            )
        return {"data_model": model_to_spec_dict(model)}
    except PlatformHTTPError:
        raise
    except Exception as e:
        raise PlatformHTTPError(ErrorCode.UNEXPECTED, f"Failed to create data model: {e!s}") from e


@router.get("/data-models/{model_name}")
async def get_data_model(model_name: str, docint_ds: DocIntDatasourceDependency):
    try:
        model = DataModel.find_by_name(docint_ds, model_name)
        if model is None:
            raise PlatformHTTPError(ErrorCode.NOT_FOUND, f"Data model not found: {model_name}")
        return {"data_model": model_to_spec_dict(model)}
    except PlatformHTTPError:
        raise
    except Exception as e:
        raise PlatformHTTPError(ErrorCode.UNEXPECTED, f"Failed to get data model: {e!s}") from e


@router.put("/data-models/{model_name}")
async def update_data_model(
    model_name: str, payload: UpdateDataModelRequest, docint_ds: DocIntDatasourceDependency
):
    try:
        existing = DataModel.find_by_name(docint_ds, model_name)
        if existing is None:
            raise PlatformHTTPError(ErrorCode.NOT_FOUND, f"Data model not found: {model_name}")

        if payload.data_model.description:
            existing.description = payload.data_model.description
        if payload.data_model.schema:
            existing.model_schema = payload.data_model.schema
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
async def delete_data_model(model_name: str, docint_ds: DocIntDatasourceDependency):
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
    docint_ds: DocIntDatasourceDependency,
    agent_server_client: AgentServerClientDependency,
):
    """Generate a data model from a document."""

    thread = await storage.get_thread(user.user_id, thread_id)
    if not thread:
        raise PlatformHTTPError(
            error_code=ErrorCode.NOT_FOUND,
            message=f"Thread {thread_id} not found",
        )

    new_file = False
    if isinstance(file, str):
        stored_file = await storage.get_file_by_ref(thread, file, user.user_id)
        if not stored_file:
            raise PlatformHTTPError(
                error_code=ErrorCode.NOT_FOUND,
                message=f"File {file} not found (storage)",
            )
        updated_file = await file_manager.refresh_file_paths([stored_file])
        if not updated_file:
            raise PlatformHTTPError(
                error_code=ErrorCode.NOT_FOUND,
                message=f"File {file} not found (refresh)",
            )
        uploaded_file = updated_file[0]
    else:
        upload_request = UploadFilePayload(file=file)
        stored_files = await file_manager.upload([upload_request], thread, user.user_id)
        uploaded_file = stored_files[0]
        new_file = True

    schema = await run_in_threadpool(
        agent_server_client.generate_schema,
        uploaded_file.file_ref,
    )

    if new_file:
        return {
            "model_schema": schema,
            "uploaded_file": uploaded_file,
        }
    else:
        return {
            "model_schema": schema,
        }
