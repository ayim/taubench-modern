from fastapi import APIRouter

from agent_platform.server.api.private_v2.agents import router as agents_router
from agent_platform.server.api.private_v2.debug import router as debug_router
from agent_platform.server.api.private_v2.runs import router as runs_router
from agent_platform.server.api.private_v2.threads import router as threads_router

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
