"""
Custom exception types for Reducto document extraction client.

These exceptions are intended to be consumed by higher layers (e.g. server)
to map to platform-friendly error types without relying on broad base
exceptions.
"""


class JobFailedError(Exception):
    """Job failed error."""

    def __init__(self, reason: str, job_id: str):
        message = f"Job ({job_id}) failed: {reason}"
        super().__init__(message)
        self.job_id = job_id


class ExtractionClientError(Exception):
    """Base error for document-extraction client."""


class UploadError(ExtractionClientError):
    """Base error for upload-related failures."""


class UploadForbiddenError(UploadError):
    """Authentication/authorization failure when requesting upload."""


class UploadPresignRequestError(UploadError):
    """Failure during the presign request to obtain the upload URL."""

    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class UploadMissingPresignedUrlError(UploadError):
    """Presign response did not include a presigned URL."""


class UploadMissingFileIdError(UploadError):
    """Presign response did not include a file ID."""


class UploadPutError(UploadError):
    """Failure when uploading content to the presigned URL."""

    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class ExtractError(ExtractionClientError):
    """Base error for extract-related failures."""


class ExtractFailedError(ExtractError):
    """Failure when extracting content from the document."""

    def __init__(self, message: str, *, reason: str | None = None):
        super().__init__(message)
        self.reason = reason


class ExtractMultipleResultsError(ExtractError):
    """Multiple results found when extracting content from the document.

    Note: in all our pipelines, we expect extraction chunking to be disabled, so
    we always only take the first result from Reducto ExtractResponse.
    """

    message: str = (
        "Multiple results found when extracting content from the document. "
        "This is not supported by our pipelines."
    )

    def __init__(self, *, results: list[dict]):
        super().__init__(self.message)
        self.results = results


class ExtractNoResultsError(ExtractError):
    """No results found when extracting content from the document."""

    message: str = "No results found when extracting content from the document."

    def __init__(self, *, results: list[dict]):
        super().__init__(self.message)
        self.results = results


class ExtractPreviousJobFailedError(ExtractError):
    """Next job cannot start because the previous job in the chain failed."""

    message: str = "Cannot start {new_job_type} job, previous job failed ({job_id}): {reason}"

    def __init__(self, *, new_job_type: str, job_id: str, reason: str | None = None):
        message = self.message.format(new_job_type=new_job_type, job_id=job_id, reason=reason)
        super().__init__(message)
        self.job_id = job_id
        self.reason = reason
        self.new_job_type = new_job_type

    def __str__(self):
        return self.message.format(
            new_job_type=self.new_job_type, job_id=self.job_id, reason=self.reason
        )
