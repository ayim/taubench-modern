from fastapi import APIRouter

from agent_platform.server.api.dependencies import StorageDependency
from agent_platform.server.api.private_v2.agents import router as agents_router
from agent_platform.server.api.private_v2.capabilities import (
    router as capabilities_router,
)
from agent_platform.server.api.private_v2.config import router as config_router
from agent_platform.server.api.private_v2.data_connections import router as data_connections_router
from agent_platform.server.api.private_v2.data_sources import router as data_sources_router
from agent_platform.server.api.private_v2.debug import router as debug_router
from agent_platform.server.api.private_v2.document_intelligence.document_intelligence import (
    router as document_intelligence_router,
)
from agent_platform.server.api.private_v2.evals import router as evals_router
from agent_platform.server.api.private_v2.mcp_servers import router as mcp_servers_router
from agent_platform.server.api.private_v2.observability import (
    router as observability_router,
)
from agent_platform.server.api.private_v2.package import router as package_router
from agent_platform.server.api.private_v2.platforms import router as platforms_router
from agent_platform.server.api.private_v2.prompt import router as prompt_router
from agent_platform.server.api.private_v2.runs import router as runs_router
from agent_platform.server.api.private_v2.semantic_data_model_api import (
    router as semantic_data_models_router,
)
from agent_platform.server.api.private_v2.threads import router as threads_router
from agent_platform.server.api.private_v2.threads_data_frames import (
    router as threads_data_frames_router,
)
from agent_platform.server.api.private_v2.work_items import (
    router as work_items_router,
)

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
    threads_data_frames_router,
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
    observability_router,
    tags=["observability-integrations"],
)
router.include_router(
    document_intelligence_router,
    prefix="/document-intelligence",
    tags=["document-intelligence"],
)
router.include_router(
    package_router,
    prefix="/package",
    tags=["package"],
)
router.include_router(
    platforms_router,
    prefix="/platforms",
    tags=["platforms"],
)

router.include_router(
    work_items_router,
    prefix="/work-items",
    tags=["work-items"],
)

router.include_router(
    data_sources_router,
    prefix="/data-sources",
    tags=["data-sources"],
)

router.include_router(
    data_connections_router,
    prefix="/data-connections",
    tags=["data-connections"],
)

router.include_router(
    evals_router,
    prefix="/evals",
    tags=["evals"],
)

router.include_router(
    semantic_data_models_router,
    prefix="/semantic-data-models",
    tags=["semantic-data-models"],
)


@router.get("/metrics")
async def metrics(storage: StorageDependency) -> dict:
    return {
        "agentCount": await storage.count_agents(),
        "threadCount": await storage.count_threads(),
        "conversationalAgentCount": await storage.count_agents_by_mode("conversational"),
        "workerAgentCount": await storage.count_agents_by_mode("worker"),
        "messageCount": await storage.count_messages(),
    }
