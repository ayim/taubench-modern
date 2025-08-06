from fastapi import APIRouter, Depends
from structlog import get_logger
from structlog.stdlib import BoundLogger

from agent_platform.core.errors.base import PlatformHTTPError
from agent_platform.core.errors.responses import ErrorCode


def _require_document_intelligence_data_server():
    """Checks that a DIDS is configured for the agent server, or fail as a pre-ignition check."""
    # TODO: Implement the actual check
    raise PlatformHTTPError(
        ErrorCode.PRECONDITION_FAILED, "Document Intelligence Data Server is not configured"
    )


router = APIRouter(dependencies=[Depends(_require_document_intelligence_data_server)])
logger: BoundLogger = get_logger(__name__)


@router.get("/ok")
async def ok():
    return {"ok": True}
