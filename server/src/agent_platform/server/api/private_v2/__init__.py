from fastapi import APIRouter

from agent_platform.server.api.private_v2.agents import router as agents_router
from agent_platform.server.api.private_v2.capabilities import (
    router as capabilities_router,
)
from agent_platform.server.api.private_v2.config import router as config_router
from agent_platform.server.api.private_v2.debug import router as debug_router
from agent_platform.server.api.private_v2.document_intelligence import (
    router as document_intelligence_router,
)
from agent_platform.server.api.private_v2.mcp_servers import router as mcp_servers_router
from agent_platform.server.api.private_v2.prompt import router as prompt_router
from agent_platform.server.api.private_v2.runs import router as runs_router
from agent_platform.server.api.private_v2.threads import router as threads_router
from agent_platform.server.api.private_v2.work_items import router as work_items_router

PRIVATE_V2_PREFIX = "/api/v2"

router = APIRouter()


@router.get("/ok")
def ok():
    return {"ok": True}


router.include_router(
    agents_router,
    prefix="/agents",
    tags=["agents"],
)
router.include_router(
    runs_router,
    prefix="/runs",
    tags=["runs"],
)
router.include_router(
    threads_router,
    prefix="/threads",
    tags=["threads"],
)
router.include_router(
    debug_router,
    prefix="/debug",
    tags=["debug"],
)
router.include_router(
    capabilities_router,
    prefix="/capabilities",
    tags=["capabilities"],
)
router.include_router(
    prompt_router,
    prefix="/prompts",
    tags=["prompts"],
)
router.include_router(
    mcp_servers_router,
    prefix="/mcp-servers",
    tags=["mcp-servers"],
)
router.include_router(
    config_router,
    prefix="/config",
    tags=["config"],
)
router.include_router(
    document_intelligence_router,
    prefix="/document-intelligence",
    tags=["document-intelligence"],
)

# Workroom uses the private API, so we need work-items published on the private api, too.
router.include_router(
    work_items_router,
    prefix="/work-items",
    tags=["work-items"],
)
