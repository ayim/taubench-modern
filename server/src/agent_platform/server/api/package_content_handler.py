import json
from collections.abc import Callable
from functools import wraps
from typing import TypeVar, cast

from fastapi import HTTPException, Request, status

T = TypeVar("T")


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
                                "required": ["package_zip_file"],
                            },
                        ]
                    },
                    "encoding": {"package_zip_file": {"contentType": "application/zip"}},
                    "description": (
                        f"Multipart form with all {schema_ref} fields plus "
                        "ZIP file under the 'package_zip_file' field"
                    ),
                },
                "application/zip": {
                    "schema": {"type": "string", "format": "binary"},
                    "description": "Binary ZIP file containing the package",
                },
                "application/octet-stream": {
                    "schema": {"type": "string", "format": "binary"},
                    "description": "Binary ZIP file containing the package",
                },
            }
        }
    }


def supports_binary_zip(schema_ref: str, summary: str = "", description: str = ""):
    """
    Decorator to add binary ZIP file support to FastAPI endpoints.
    """

    def decorator(func: Callable) -> Callable:
        # Add the OpenAPI extra configuration to the function
        if not hasattr(func, "__annotations__"):
            func.__annotations__ = {}

        # Store the binary ZIP configuration as an attribute
        func._binary_zip_schema_ref = schema_ref
        func._binary_zip_summary = summary or func.__name__.replace("_", " ").title()
        func._binary_zip_description = description or "Accepts both JSON and binary ZIP files."
        func._binary_zip_openapi_extra = create_binary_zip_openapi_extra(schema_ref)

        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)

        return wrapper

    return decorator


def validate_zip_content(content: bytes) -> None:
    """
    Validate that the binary content is a valid ZIP file.
    """
    import zipfile
    from io import BytesIO

    try:
        with zipfile.ZipFile(BytesIO(content), "r") as zip_file:
            # Try to read the ZIP file to validate it
            zip_file.testzip()
    except (zipfile.BadZipFile, RuntimeError) as e:
        raise ValueError(f"Invalid ZIP file: {e}") from e


async def _extract_binary_zip(request: Request) -> bytes:
    """
    Extract binary ZIP content from request body.
    """
    content = await request.body()

    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty request body")

    # Validate that it's a valid ZIP file
    try:
        validate_zip_content(content)
    except ValueError as exc:
        # Normalize to HTTP 422 for invalid zip content
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    return content


async def _extract_multipart_zip_and_data(request: Request) -> tuple[bytes, dict]:
    """
    Extract ZIP content and form data from multipart/form-data request.
    Expects a file field named 'package_zip_file' and other fields matching the payload schema.
    Also tolerates 'file', 'package' or 'zip' for file field for backward compatibility.
    """
    form = await request.form()
    candidate = (
        form.get("package_zip_file") or form.get("file") or form.get("package") or form.get("zip")
    )

    # Extract all other form fields as data for the payload
    form_data = {}
    for key, value in form.items():
        if key not in ("package_zip_file", "file", "package", "zip"):  # Skip the file fields
            if hasattr(value, "read"):
                # If it's somehow uploaded as a file, read its content
                content = await value.read()  # type: ignore[attr-defined]
                form_data[key] = (
                    content.decode("utf-8") if isinstance(content, bytes) else str(content)
                )
            else:
                form_data[key] = value

    # FastAPI/Starlette provides UploadFile objects for files
    # Check for UploadFile by type name and hasattr to handle import/type issues
    if hasattr(candidate, "read") and hasattr(candidate, "filename"):
        # This is likely an UploadFile or file-like object
        content = await candidate.read()  # type: ignore[attr-defined]
    elif isinstance(candidate, bytes | bytearray):
        content = bytes(candidate)
    elif isinstance(candidate, str):
        # Not expected, but handle gracefully
        content = candidate.encode("utf-8")
    else:
        content = b""

    if content:
        try:
            validate_zip_content(content)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
            ) from exc
    return content, form_data


async def convert_binary_to_base64(zip_content: bytes) -> str:
    """
    Convert binary ZIP content to base64 string for processing.
    """
    import base64

    return base64.b64encode(zip_content).decode("utf-8")


async def _parse_json_payload(request: Request, payload_model: type[T]) -> T:
    """Parse JSON from request body and create payload object."""
    body = await request.body()
    if not body:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty request body")

    try:
        json_data = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid JSON in request body: {exc}"
        ) from exc

    # Try Pydantic BaseModel first
    if hasattr(payload_model, "model_validate"):
        return payload_model.model_validate(json_data)  # type: ignore[attr-defined]

    # Fallback to dataclass
    import dataclasses

    if dataclasses.is_dataclass(payload_model):
        field_names = {f.name for f in dataclasses.fields(payload_model)}  # type: ignore[arg-type]
        filtered_data = {k: v for k, v in json_data.items() if k in field_names}
        return payload_model(**filtered_data)

    # Last resort - direct constructor
    return payload_model(**json_data)  # type: ignore[call-arg]


async def _create_payload_from_form_data(payload_model: type[T], form_data: dict) -> T:
    """Create payload from multipart form data."""
    # Try Pydantic BaseModel first
    if hasattr(payload_model, "model_validate"):
        return payload_model.model_validate(form_data)  # type: ignore[attr-defined]

    # Fallback to dataclass
    import dataclasses

    if dataclasses.is_dataclass(payload_model):
        field_names = {f.name for f in dataclasses.fields(payload_model)}  # type: ignore[arg-type]
        filtered_data = {k: v for k, v in form_data.items() if k in field_names}
        return payload_model(**filtered_data)

    # Last resort - direct constructor
    return payload_model(**form_data)  # type: ignore[call-arg]


async def _create_minimal_payload(payload_model: type[T]) -> T:
    """Create minimal payload for binary ZIP uploads."""
    # Try Pydantic BaseModel first
    if hasattr(payload_model, "model_validate"):
        minimal_data = {"name": "Uploaded Package", "description": "Package uploaded as binary ZIP"}
        return payload_model.model_validate(minimal_data)  # type: ignore[attr-defined]

    # Fallback to dataclass
    import dataclasses

    if dataclasses.is_dataclass(payload_model):
        field_names = {f.name for f in dataclasses.fields(payload_model)}  # type: ignore[arg-type]
        minimal_data = {"name": "Uploaded Package"}
        if "description" in field_names:
            minimal_data["description"] = "Package uploaded as binary ZIP"
        return payload_model(**minimal_data)

    # Last resort
    return payload_model(name="Uploaded Package")  # type: ignore[call-arg]


async def handle_json_or_binary_zip(
    request: Request, payload_model: type[T] | None = None
) -> tuple[T, bytes | None]:
    """
    Handle application/json, multipart/form-data, and binary ZIP content types.
    Returns a tuple of (payload, zip_content).
    """
    if payload_model is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="payload_model is required"
        )

    content_type = request.headers.get("content-type", "").lower()

    if content_type.startswith("application/json"):
        payload = await _parse_json_payload(request, payload_model)
        return cast(T, payload), None

    elif content_type.startswith(("application/zip", "application/octet-stream")):
        zip_content = await _extract_binary_zip(request)
        payload = await _create_minimal_payload(payload_model)
        return cast(T, payload), zip_content

    elif content_type.startswith("multipart/form-data"):
        zip_content, form_data = await _extract_multipart_zip_and_data(request)
        payload = await _create_payload_from_form_data(payload_model, form_data)
        return cast(T, payload), zip_content

    else:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported content type: {content_type}",
        )


def create_binary_zip_metadata(zip_content: bytes) -> dict:
    """
    Create metadata about uploaded binary ZIP content for response or logging.
    """
    return {
        "binary_package": {
            "content_type": "application/zip",
            "size": len(zip_content),
            "format": "binary ZIP file",
        }
    }
