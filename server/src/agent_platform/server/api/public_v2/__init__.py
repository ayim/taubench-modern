from fastapi import APIRouter

from agent_platform.server.api.public_v2.agents import router as agents_router
from agent_platform.server.api.public_v2.work_items import router as work_items_router

PUBLIC_V2_PREFIX = "/api/public/v1"

router = APIRouter()

router.include_router(
    agents_router,
    prefix="/agents",
    tags=["agents"],
)

router.include_router(
    work_items_router,
    prefix="/work-items",
    tags=["work-items"],
)


@router.get("/ok")
def ok():
    return {"ok": True}
