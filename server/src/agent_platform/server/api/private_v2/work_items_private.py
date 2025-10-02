from fastapi import APIRouter, Depends
from structlog import get_logger

from agent_platform.core.errors import ErrorCode, PlatformHTTPError
from agent_platform.server.api.dependencies import StorageDependency
from agent_platform.server.auth import AuthedUser
from agent_platform.server.constants import SystemConfig
from agent_platform.server.work_items.rest import AgentWorkItemsSummaryResponse


def _require_workitems_enabled():
    """Raise an error if work items are disabled in configuration."""
    if not SystemConfig.enable_workitems:
        raise PlatformHTTPError(ErrorCode.FORBIDDEN, "Work items feature is disabled")


# Attach the dependency to all routes in this router. If the feature is disabled,
# every request will immediately raise the above error.
router = APIRouter(dependencies=[Depends(_require_workitems_enabled)])
logger = get_logger(__name__)


@router.get("/summary", response_model=list[AgentWorkItemsSummaryResponse])
async def get_work_items_summary(
    user: AuthedUser,
    storage: StorageDependency,
) -> list[AgentWorkItemsSummaryResponse]:
    """Get work items summary grouped by agent and status."""
    # Get summary data from storage (already grouped, counted, and converted to response models)
    return await storage.get_work_items_summary(user.user_id)
