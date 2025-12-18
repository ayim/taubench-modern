import json
from collections.abc import AsyncGenerator
from typing import TypeVar

from fastapi import Request
from starlette.datastructures import UploadFile

from agent_platform.core.agent_package.handler.action_package import ActionPackageHandler
from agent_platform.core.agent_package.handler.agent_package import AgentPackageHandler
from agent_platform.core.errors.base import PlatformHTTPError
from agent_platform.core.errors.responses import ErrorCode
from agent_platform.core.payloads.action_package import ActionPackagePayload
from agent_platform.core.payloads.agent_package import AgentPackagePayload

T = TypeVar("T")

PACKAGE_FILE_FIELD_NAME = "package_zip_file"


def create_binary_zip_openapi_extra(schema_ref: str) -> dict:
    """
    Create OpenAPI extra configuration for endpoints that accept JSON,
    multipart/form-data, or binary ZIP.
    """
    return {
        "requestBody": {
            "content": {
                "application/json": {"schema": {"$ref": f"#/components/schemas/{schema_ref}"}},
                "multipart/form-data": {
                    "schema": {
                        "allOf": [
                            {"$ref": f"#/components/schemas/{schema_ref}"},
                            {
                                "type": "object",
                                "properties": {
                                    "package_zip_file": {
                                        "type": "string",
                                        "format": "binary",
                                        "description": "ZIP file",
                                    }
                                },
                                "required": [f"{PACKAGE_FILE_FIELD_NAME}"],
                            },
                        ]
                    },
                    "encoding": {"package_zip_file": {"contentType": "application/zip"}},
                    "description": (
                        f"Multipart form with all {schema_ref} fields plus ZIP file under the 'package_zip_file' field"
                    ),
                },
            }
        }
    }


async def _extract_multipart_zip_and_data(request: Request) -> tuple[UploadFile, dict]:
    """
    Extract ZIP content and form data from multipart/form-data request.
    Expects a file field named 'package_zip_file' and other fields matching the payload schema.
    """
    form = await request.form()
    package_zip_item = form.get(PACKAGE_FILE_FIELD_NAME)

    # Please note that for this check to work, the code needs to check for
    # starlette's UploadFile specifically, as request.form() is a starlette implementation.
    if package_zip_item is None or not isinstance(package_zip_item, UploadFile):
        raise PlatformHTTPError(ErrorCode.BAD_REQUEST, message="Package ZIP file is required")

    # Extract all other form fields as data for the payload
    form_data = {}
    for key, value in form.items():
        if key != "package_zip_file":
            form_data[key] = value

    return package_zip_item, form_data


async def _request_body_to_json(request: Request) -> dict:
    body = await request.body()

    if not body:
        raise PlatformHTTPError(ErrorCode.BAD_REQUEST, message="Empty request body")

    try:
        json_data = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise PlatformHTTPError(ErrorCode.BAD_REQUEST, message=f"Invalid JSON in request body: {exc}") from exc

    return json_data


async def _iter_upload_file_chunks(
    upload_file: UploadFile,
) -> AsyncGenerator[bytes, None]:
    """
    Yield the contents of a FastAPI/Starlette UploadFile as an async generator of bytes.

    Args:
        upload_file: The incoming UploadFile.

    Yields:
        Bytes chunks until EOF.
    """
    await upload_file.seek(0)

    while True:
        # Streaming in 8 KB chunks.
        chunk = await upload_file.read(8 * 1024)
        if not chunk:
            break
        yield chunk


def _form_data_field_to_dict(value: str | None) -> dict | None:
    """
    Parses a stringified JSON form data field into a dict.
    Returns None if the field is not a valid JSON string representing a dictionary.
    """
    if value is None:
        return None

    try:
        serialized = json.loads(value)
        return serialized if isinstance(serialized, dict) else None
    except Exception:
        return None


def _form_data_field_to_list[T](value: str | None, expected_element_type: type[T]) -> list[T] | None:
    if value is None:
        return []

    try:
        serialized = json.loads(value)

        if not isinstance(serialized, list):
            return []

        if len(serialized) == 0:
            return []

        result: list[T] = [x for x in serialized if isinstance(x, expected_element_type)]

        return result
    except Exception:
        return []


def _get_agent_package_payload_from_form_data(form_data: dict) -> AgentPackagePayload:
    # Collecting all possible stringified JSON fields from form data.
    model_raw: str | None = form_data.get("model", None)
    action_servers_raw: str | None = form_data.get("action_servers", None)
    mcp_servers_raw: str | None = form_data.get("mcp_servers", None)
    mcp_server_ids_raw: str | None = form_data.get("mcp_server_ids", None)
    platform_params_ids_raw: str | None = form_data.get("platform_params_ids", None)
    langsmith_raw: str | None = form_data.get("langsmith", None)

    form_data["action_servers"] = _form_data_field_to_list(action_servers_raw, dict)
    form_data["mcp_servers"] = _form_data_field_to_list(mcp_servers_raw, dict)
    form_data["mcp_server_ids"] = _form_data_field_to_list(mcp_server_ids_raw, str)
    form_data["platform_params_ids"] = _form_data_field_to_list(platform_params_ids_raw, str)
    form_data["langsmith"] = _form_data_field_to_dict(langsmith_raw)
    form_data["model"] = _form_data_field_to_dict(model_raw)

    # Providing defaults for ZIP content (user-provided values override them if exist)
    form_data = {"name": "Uploaded Package", "description": "Package uploaded as ZIP file", **form_data}

    return AgentPackagePayload.model_validate(form_data)


async def parse_agent_package_payload(request: Request) -> tuple[AgentPackagePayload, AgentPackageHandler]:
    """
    Handles application/json and multipart/form-data.
    Returns a tuple of (AgentPackagePayload, AgentPackageHandler).
    """
    content_type = request.headers.get("content-type", "").lower()

    if content_type.startswith("application/json"):
        body_json = await _request_body_to_json(request)
        payload = AgentPackagePayload.model_validate(body_json)

        if payload.agent_package_base64:
            handler = await AgentPackageHandler.from_base64(payload.agent_package_base64)
        elif payload.agent_package_url:
            handler = await AgentPackageHandler.from_url(payload.agent_package_url)
        else:
            raise PlatformHTTPError(
                ErrorCode.BAD_REQUEST,
                message="Agent Package URL or base64-encoded data must be provided",
            )

        return payload, handler

    elif content_type.startswith("multipart/form-data"):
        package_zip_file, form_data = await _extract_multipart_zip_and_data(request)
        payload = _get_agent_package_payload_from_form_data(form_data)
        handler = await AgentPackageHandler.from_stream(_iter_upload_file_chunks(package_zip_file))

        return payload, handler

    else:
        raise PlatformHTTPError(
            ErrorCode.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            message=f"Unsupported content type: {content_type}",
        )


async def parse_action_package_payload(request: Request) -> tuple[ActionPackagePayload, ActionPackageHandler]:
    """
    Handles application/json and multipart/form-data.
    Returns a tuple of (ActionPackagePayload, AgentPackageHandler).
    """
    content_type = request.headers.get("content-type", "").lower()

    if content_type.startswith("application/json"):
        body_json = await _request_body_to_json(request)
        payload = ActionPackagePayload.model_validate(body_json)

        if payload.action_package_base64:
            handler = await ActionPackageHandler.from_base64(payload.action_package_base64)
        elif payload.action_package_url:
            handler = await ActionPackageHandler.from_url(payload.action_package_url)
        else:
            raise PlatformHTTPError(
                ErrorCode.BAD_REQUEST,
                message="Action Package URL or base64-encoded data must be provided",
            )

        return payload, handler

    elif content_type.startswith("multipart/form-data"):
        package_zip_file, form_data = await _extract_multipart_zip_and_data(request)
        # ActionPackagePayload does not have any nested fields, so no preparation is needed.
        payload = ActionPackagePayload.model_validate(form_data)
        handler = await ActionPackageHandler.from_stream(_iter_upload_file_chunks(package_zip_file))

        return payload, handler

    else:
        raise PlatformHTTPError(
            ErrorCode.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            message=f"Unsupported content type: {content_type}",
        )


def create_binary_zip_metadata(zip_size: int) -> dict:
    """
    Create metadata about uploaded binary ZIP content for response or logging.
    """
    return {
        "binary_package": {
            "content_type": "application/zip",
            "size": zip_size,
            "format": "binary ZIP file",
        }
    }
