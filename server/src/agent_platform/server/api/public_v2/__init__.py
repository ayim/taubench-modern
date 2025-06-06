from fastapi import APIRouter

from agent_platform.server.api.public_v2.agents import router as agents_router

PUBLIC_V2_PREFIX = "/api/public/v2"

router = APIRouter()

router.include_router(
    agents_router,
    prefix="/agents",
    tags=["agents"],
)


@router.get("/ok")
def ok():
    return {"ok": True}
