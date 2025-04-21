import uuid

from fastapi import APIRouter, HTTPException
from structlog import get_logger

from agent_platform.core.kernel_interfaces.otel import OTelArtifact
from agent_platform.server.api.dependencies import StorageDependency
from agent_platform.server.auth import AuthedUser

router = APIRouter()
logger = get_logger(__name__)


@router.get("/artifacts")
async def get_artifacts(
    _: AuthedUser,
    storage: StorageDependency,
) -> list[OTelArtifact]:
    return await storage.get_otel_artifacts()


@router.get("/artifacts/search")
async def search_artifacts(  # noqa: PLR0913
    storage: StorageDependency,
    trace_id: str | None = None,
    user_id: str | None = None,
    agent_id: str | None = None,
    thread_id: str | None = None,
    run_id: str | None = None,
    message_id: str | None = None,
) -> list[OTelArtifact]:
    # 1. Validate the correlation IDs (each must be of the form kind:value)
    for correlation_id in [trace_id, user_id, agent_id, thread_id, run_id, message_id]:
        if correlation_id is None:
            continue

        try:
            uuid.UUID(correlation_id)
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Each correlation ID must be a valid UUID"
                    f"({correlation_id} is invalid)"
                ),
            ) from e

    # 2. Search for artifacts with the given correlation IDs
    return await storage.search_otel_artifacts(
        trace_id=trace_id,
        user_id=user_id,
        agent_id=agent_id,
        thread_id=thread_id,
        run_id=run_id,
        message_id=message_id,
    )


@router.get("/artifacts/{aid}")
async def get_artifact(aid: str, storage: StorageDependency) -> OTelArtifact:
    return await storage.get_otel_artifact(aid)


@router.delete("/artifacts")
async def delete_artifacts(_: AuthedUser, storage: StorageDependency) -> int:
    return await storage.delete_all_otel_artifacts()
