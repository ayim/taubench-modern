from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sema4ai_docint import normalize_name

from agent_platform.core.document_intelligence.document_layout import DocumentLayoutBridge
from agent_platform.core.errors import ErrorCode, PlatformHTTPError
from agent_platform.core.files import UploadedFile
from agent_platform.core.payloads.upsert_document_layout import DocumentLayoutPayload


@dataclass(frozen=True)
class GenerateLayoutResponsePayload:
    layout: DocumentLayoutBridge
    file: UploadedFile | None = None


@dataclass(frozen=True)
class ExtractDocumentPayload:
    """Payload for extracting a document."""

    # File related fields
    thread_id: str
    file_name: str

    # Data model related fields.
    data_model_name: str | None = None
    data_model_prompt: str | None = None

    # Layout related fields, one or the other must be provided.
    layout_name: str | None = None
    document_layout: DocumentLayoutPayload | None = None

    @classmethod
    def model_validate(cls, data: Any) -> ExtractDocumentPayload:
        # Complexiy warning comes from number of if branches for validation and is not
        # worth refactoring for.
        if isinstance(data, dict):
            obj = dict(data)
        else:
            obj = dict(getattr(data, "__dict__", {}))

        # Validate file fields to ensure not None
        file_name = obj.get("file_name")
        thread_id = obj.get("thread_id")
        if thread_id is None or file_name is None:
            raise PlatformHTTPError(
                error_code=ErrorCode.BAD_REQUEST,
                message="thread_id and file are required",
            )

        # Validate layout fields and ensure we have a data model name if we have a layout name
        if obj.get("layout_name") is None and obj.get("document_layout") is None:
            raise PlatformHTTPError(
                error_code=ErrorCode.BAD_REQUEST,
                message="One of layout_name or document_layout must be provided",
            )
        if obj.get("layout_name") is not None and obj.get("document_layout") is not None:
            raise PlatformHTTPError(
                error_code=ErrorCode.BAD_REQUEST,
                message="layout_name and document_layout cannot both be provided",
            )
        if obj.get("layout_name") is not None and obj.get("data_model_name") is None:
            raise PlatformHTTPError(
                error_code=ErrorCode.BAD_REQUEST,
                message="data_model_name is required when layout_name is provided",
            )

        if obj.get("document_layout") is not None and not isinstance(
            obj.get("document_layout"), dict | DocumentLayoutPayload
        ):
            raise PlatformHTTPError(
                error_code=ErrorCode.BAD_REQUEST,
                message="The 'document_layout' field must be a dictionary or DocumentLayoutPayload",
            )

        # If we were given a document layout, let's validate it
        if obj.get("document_layout") is not None:
            DocumentLayoutPayload.model_validate(obj.get("document_layout"))

        # Normalize names if provided
        data_model_name: str | None = None
        layout_name: str | None = None
        if obj.get("data_model_name"):
            data_model_name = normalize_name(str(obj.get("data_model_name")))
        if obj.get("layout_name"):
            layout_name = normalize_name(str(obj.get("layout_name")))

        return cls(
            data_model_name=data_model_name,
            data_model_prompt=obj.get("data_model_prompt"),
            layout_name=layout_name,
            document_layout=obj.get("document_layout"),
            file_name=file_name,
            thread_id=thread_id,
        )
