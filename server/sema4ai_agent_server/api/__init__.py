from fastapi import APIRouter

from sema4ai_agent_server.api.agents import router as agents_router
from sema4ai_agent_server.api.files import router as files_router
from sema4ai_agent_server.api.runs import router as runs_router
from sema4ai_agent_server.api.threads import router as threads_router

router = APIRouter(prefix="/api/v1")


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
    files_router,
    tags=["files"],
)
