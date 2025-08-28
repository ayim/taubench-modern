from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from reducto.types.shared.parse_response import ResultFullResult as ParseResult
from reducto.types.shared.split_response import Result as SplitResult
from sema4ai_docint import normalize_name
from sema4ai_docint.extraction.reducto.async_ import JobStatus, JobType

from agent_platform.core.errors import ErrorCode, PlatformHTTPError
from agent_platform.core.files import UploadedFile
from agent_platform.core.payloads.upsert_document_layout import DocumentLayoutPayload


@dataclass(frozen=True)
class GenerateLayoutResponsePayload:
    layout: DocumentLayoutPayload
    file: UploadedFile | None = None


@dataclass(frozen=True)
class GenerateSchemaResponsePayload:
    schema: dict[str, Any]
    file: UploadedFile | None = None


@dataclass(frozen=True)
class ExtractDocumentPayload:
    """Payload for extracting a document."""

    # File related fields
    thread_id: str
    file_name: str

    # Data model related fields (required when layout_name is provided)
    data_model_name: str | None = None
    data_model_prompt: str | None = None

    # Layout related fields, one or the other must be provided.
    layout_name: str | None = None
    document_layout: DocumentLayoutPayload | None = None

    @classmethod
    def model_validate(cls, data: Any) -> ExtractDocumentPayload:  # noqa: C901
        # Complexity warning comes from number of if branches for validation and is not
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
                message="thread_id and file_name are required",
            )

        # Validate layout fields: layout_name or document_layout must be provided
        document_layout = obj.get("document_layout")
        if obj.get("layout_name") is None and document_layout is None:
            raise PlatformHTTPError(
                error_code=ErrorCode.BAD_REQUEST,
                message="One of layout_name or document_layout must be provided",
            )
        if obj.get("layout_name") is not None and document_layout is not None:
            raise PlatformHTTPError(
                error_code=ErrorCode.BAD_REQUEST,
                message="layout_name and document_layout cannot both be provided",
            )
        if obj.get("layout_name") is not None and obj.get("data_model_name") is None:
            raise PlatformHTTPError(
                error_code=ErrorCode.BAD_REQUEST,
                message="data_model_name is required when layout_name is provided",
            )

        if document_layout is not None:
            if not isinstance(document_layout, dict | DocumentLayoutPayload):
                raise PlatformHTTPError(
                    error_code=ErrorCode.BAD_REQUEST,
                    message="The 'document_layout' field must be a dictionary or "
                    "DocumentLayoutPayload",
                )
            # Validate the document layout
            if isinstance(document_layout, dict):
                document_layout = DocumentLayoutPayload.model_validate(document_layout)

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
            document_layout=document_layout,
            file_name=file_name,
            thread_id=thread_id,
        )


# Extraction Client Job result types


@dataclass(frozen=True)
class JobStartResponsePayload:
    job_id: str
    job_type: JobType
    uploaded_file: UploadedFile | None = None


@dataclass(frozen=True)
class JobStatusResponsePayload:
    job_id: str
    # Matches Reducto's types.job_get_response.JobGetResponse.status
    status: JobStatus
    # URL to fetch the result when job is complete (only present when status is COMPLETED)
    result_url: str | None = None


# Response types for get_job_result endpoint
@dataclass(frozen=True)
class ParseJobResult:
    result: ParseResult
    job_type: Literal["parse"] = "parse"


@dataclass(frozen=True)
class ExtractJobResult:
    result: dict[str, Any]  # Extract results are untyped objects
    job_type: Literal["extract"] = "extract"


@dataclass(frozen=True)
class SplitJobResult:
    result: SplitResult
    job_type: Literal["split"] = "split"


# Union type for job results
JobResult = ParseJobResult | ExtractJobResult | SplitJobResult
