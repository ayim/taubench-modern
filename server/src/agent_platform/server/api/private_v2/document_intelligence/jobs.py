from fastapi import APIRouter, Request
from sema4ai_docint.extraction.reducto.async_ import Job, JobStatus, JobType
from sema4ai_docint.extraction.reducto.exceptions import ExtractFailedError
from structlog import get_logger

from agent_platform.core.errors.base import PlatformHTTPError
from agent_platform.core.errors.responses import ErrorCode
from agent_platform.core.payloads.document_intelligence import JobResult, JobStatusResponsePayload
from agent_platform.server.api.dependencies import AsyncExtractionClientDependency
from agent_platform.server.api.private_v2.document_intelligence.services import _create_job_result
from agent_platform.server.auth import AuthedUser

logger = get_logger(__name__)


router = APIRouter()


@router.get("/jobs/{job_id}/status")
async def get_job_status(
    job_id: str,
    job_type: JobType,
    request: Request,
    user: AuthedUser,
    extraction_client: AsyncExtractionClientDependency,
) -> JobStatusResponsePayload:
    """Get the status of an asynchronous job.

    Args:
        job_id: The ID of the job
        job_type: The type of job (JobType.PARSE, JobType.EXTRACT, or JobType.SPLIT)

    Returns:
        A response containing:
        - job_id: The ID of the job
        - status: The current status ("Pending", "Idle", "Completed", "Failed")
        - result_url: URL to fetch the result (only present when status is "Completed")
    """
    try:
        # Reconstruct the Job object
        job = Job(job_id=job_id, job_type=job_type, client=extraction_client)
        status = await job.status()

        # Construct result URL if job is completed
        result_url = None
        if status == JobStatus.COMPLETED:
            # Construct the URL to the result endpoint
            base_url = str(request.url_for("get_job_result", job_id=job_id))
            result_url = f"{base_url}?job_type={job_type.value}"

        return JobStatusResponsePayload(
            job_id=job_id,
            status=status,
            result_url=result_url,
        )
    except Exception as e:
        logger.error(f"Failed to get job status for {job_id}: {e}")
        raise PlatformHTTPError(
            ErrorCode.NOT_FOUND,
            f"Job {job_id} not found or inaccessible",
        ) from e


@router.get("/jobs/{job_id}/result")
async def get_job_result(
    job_id: str,
    job_type: JobType,
    user: AuthedUser,
    extraction_client: AsyncExtractionClientDependency,
) -> JobResult:
    """Get the result of a completed asynchronous job.

    This endpoint returns immediately based on the current job status:
    HTTP Status Codes:
        200: Job completed successfully - returns JobResult
        404: Job not found OR result not available yet (job still processing)
        422: Job failed

    Args:
        job_id: The ID of the job
        job_type: The type of job (JobType.PARSE, JobType.EXTRACT, or JobType.SPLIT)

    Returns:
        The job result (parse or extract result) when complete.
        For parse jobs, this returns the localized parse response.
        For extract jobs, this returns the extraction results.

    Raises:
        PlatformHTTPError: If the job is still processing, failed, or not found.
    """
    try:
        # Reconstruct the Job object with proper type information
        job = Job(job_id=job_id, job_type=job_type, client=extraction_client)

        # Check job status first
        status = await job.status()

        match status:
            case JobStatus.COMPLETED:
                # Job is complete, get result without polling
                result = await job.result()  # This should return immediately since job is done
                return _create_job_result(result)
            case JobStatus.PENDING | JobStatus.IDLE:
                # Job still processing - result resource doesn't exist yet
                raise PlatformHTTPError(
                    ErrorCode.NOT_FOUND,
                    "Job result not available yet - job is still processing",
                )
            case JobStatus.FAILED:
                # Job failed - return 422
                raise PlatformHTTPError(
                    ErrorCode.UNPROCESSABLE_ENTITY,
                    f"Job {job_id} failed",
                )
            case _:
                # Unknown status
                raise PlatformHTTPError(
                    ErrorCode.UNEXPECTED,
                    f"Unknown job status: {status}",
                )

    except PlatformHTTPError:
        # Re-raise PlatformHTTPErrors (including our status-based errors above)
        raise
    except ExtractFailedError as e:
        logger.error(f"Job {job_id} extraction failed: {e}")
        reason = getattr(e, "reason", None)
        raise PlatformHTTPError(
            ErrorCode.UNPROCESSABLE_ENTITY,
            f"Job {job_id} failed: {reason or str(e)}",
        ) from e
    except Exception as e:
        logger.error(f"Failed to get job result for {job_id}: {e}")
        raise PlatformHTTPError(
            ErrorCode.NOT_FOUND,
            f"Job {job_id} not found or inaccessible",
        ) from e
