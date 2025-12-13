from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from reducto.types.shared.parse_response import ResultFullResultChunk
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


@dataclass(frozen=True)
class ModifySchemaRequestPayload:
    schema: dict[str, Any]
    instructions: str
    file_name: str | None = None


@dataclass(frozen=True)
class ModifySchemaResponsePayload:
    schema: dict[str, Any]


@dataclass(frozen=True)
class ExtractDocumentPayload:
    """Payload for extracting a document."""

    # File related fields
    thread_id: str
    file_name: str
    job_id: str | None = None

    # Data model related fields (required when layout_name is provided)
    data_model_name: str | None = None
    data_model_prompt: str | None = None

    # Layout related fields, one or the other must be provided.
    layout_name: str | None = None
    document_layout: DocumentLayoutPayload | None = None

    # Top level Extraction options
    generate_citations: bool | None = True

    @classmethod
    def model_validate(cls, data: Any) -> ExtractDocumentPayload:
        # Complexity warning comes from number of if branches for validation and is not
        # worth refactoring for.
        if isinstance(data, dict):
            obj = dict(data)
        else:
            obj = dict(getattr(data, "__dict__", {}))

        # Validate file fields to ensure not None
        file_name = obj.get("file_name")
        thread_id = obj.get("thread_id")
        job_id = obj.get("job_id")
        if thread_id is None:
            raise PlatformHTTPError(
                error_code=ErrorCode.BAD_REQUEST,
                message="thread_id is required",
            )
        if file_name is None:
            raise PlatformHTTPError(
                error_code=ErrorCode.BAD_REQUEST,
                message="file_name is required",
            )

        # Make sure the job_id is prefixed.
        job_id = f"jobid://{job_id}" if job_id and not job_id.startswith("jobid://") else job_id

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
                    message="The 'document_layout' field must be a dictionary or DocumentLayoutPayload",
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
            job_id=job_id,
            thread_id=thread_id,
            generate_citations=obj.get("generate_citations", True),
        )

    def model_dump(self) -> dict[str, Any]:
        return {
            "data_model_name": self.data_model_name,
            "data_model_prompt": self.data_model_prompt,
            "layout_name": self.layout_name,
            "document_layout": self.document_layout.model_dump() if self.document_layout else None,
            "file_name": self.file_name,
            "job_id": self.job_id,
            "thread_id": self.thread_id,
            "generate_citations": self.generate_citations,
        }


@dataclass(frozen=True)
class ExtractDocumentResponsePayload:
    result: dict[str, Any]
    citations: dict[str, Any] | None = None


@dataclass(frozen=True)
class ParseDocumentResponsePayload:
    # We exclude the `type`, `custom`, and `ocr` fields from the OpenAPI schema because they
    # are not used by any downstream users (e.g., spar-ui)
    chunks: list[ResultFullResultChunk]

    @classmethod
    def model_validate(cls, data: Any) -> ParseDocumentResponsePayload:
        return cls(
            chunks=[ResultFullResultChunk.model_validate(chunk) for chunk in data["chunks"]],
        )


@dataclass(frozen=True)
class UpsertLayoutResponsePayload:
    ok: bool


# Extraction Client Job result types


@dataclass(frozen=True)
class JobStartResponsePayload:
    job_id: str
    job_type: JobType
    uploaded_file: UploadedFile | None = None

    @classmethod
    def model_validate(cls, data: dict[str, Any]) -> JobStartResponsePayload:
        if data.get("uploaded_file") is not None:
            uploaded_file = UploadedFile.model_validate(data["uploaded_file"])
        else:
            uploaded_file = None

        return cls(
            job_id=data["job_id"],
            job_type=data["job_type"],
            uploaded_file=uploaded_file,
        )


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
    result: ParseDocumentResponsePayload
    job_id: str
    job_type: Literal["parse"] = "parse"

    @classmethod
    def model_validate(cls, data: dict[str, Any]) -> ParseJobResult:
        if not isinstance(data, dict):
            raise ValueError("data must be a dictionary")
        if "job_id" not in data:
            raise ValueError("job_id is required")
        if "job_type" not in data:
            raise ValueError("job_type is required")
        if data["job_type"] != "parse":
            raise ValueError("job_type must be 'parse'")
        if "result" not in data:
            raise ValueError("result is required")
        return cls(
            result=ParseDocumentResponsePayload.model_validate(data["result"]),
            job_id=data["job_id"],
            job_type=data["job_type"],
        )


@dataclass(frozen=True)
class ExtractJobResult:
    result: dict[str, Any]  # Extract results are untyped objects
    job_id: str
    citations: dict[str, Any] | None = None  # Citations are untyped objects
    job_type: Literal["extract"] = "extract"

    @classmethod
    def model_validate(cls, data: dict[str, Any]) -> ExtractJobResult:
        if not isinstance(data, dict):
            raise ValueError("data must be a dictionary")
        if "job_id" not in data:
            raise ValueError("job_id is required")
        if "job_type" not in data:
            raise ValueError("job_type is required")
        if data["job_type"] != "extract":
            raise ValueError("job_type must be 'extract'")
        if "result" not in data:
            raise ValueError("result is required")

        return cls(
            result=data["result"],
            citations=data.get("citations", None),
            job_id=data["job_id"],
            job_type=data["job_type"],
        )


@dataclass(frozen=True)
class SplitJobResult:
    result: SplitResult
    job_id: str
    job_type: Literal["split"] = "split"

    @classmethod
    def model_validate(cls, data: dict[str, Any]) -> SplitJobResult:
        return cls(
            result=SplitResult.model_validate(data["result"]),
            job_id=data["job_id"],
            job_type=data["job_type"],
        )


# Union type for job results
JobResult = ParseJobResult | ExtractJobResult | SplitJobResult
