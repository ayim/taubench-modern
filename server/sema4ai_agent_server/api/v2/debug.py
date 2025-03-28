import uuid

from fastapi import APIRouter, HTTPException
from structlog import get_logger

from agent_server_types_v2.kernel_interfaces.otel import OTelArtifact
from sema4ai_agent_server.auth.handlers_v2 import AuthedUserV2
from sema4ai_agent_server.storage.v2 import get_storage_v2

router = APIRouter()
logger = get_logger(__name__)


@router.get("/artifacts")
async def get_artifacts(_: AuthedUserV2) -> list[OTelArtifact]:
    return await get_storage_v2().get_otel_artifacts_v2()

@router.get("/artifacts/search")
async def search_artifacts(  # noqa: PLR0913
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
    return await get_storage_v2().search_otel_artifacts_v2(
        trace_id=trace_id,
        user_id=user_id,
        agent_id=agent_id,
        thread_id=thread_id,
        run_id=run_id,
        message_id=message_id,
    )

@router.get("/artifacts/{aid}")
async def get_artifact(aid: str) -> OTelArtifact:
    return await get_storage_v2().get_otel_artifact_v2(aid)

@router.delete("/artifacts")
async def delete_artifacts(_: AuthedUserV2) -> int:
    return await get_storage_v2().delete_all_otel_artifacts_v2()
