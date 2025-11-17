"""Client for MCP Runtime API lifecycle operations."""

from http import HTTPStatus

import httpx
from structlog import get_logger

from agent_platform.server.mcp_runtime.config import MCPRuntimeConfig

logger = get_logger(__name__)


async def delete_deployment(deployment_id: str) -> bool:
    """Delete a deployment from the MCP Runtime API.

    Args:
        deployment_id: Unique identifier for the deployment

    Returns:
        True if deletion succeeded or deployment not found (404), False on other errors

    Note:
        This is a best-effort cleanup operation. It logs errors but does not raise
        exceptions, allowing database cleanup to proceed even if runtime cleanup fails.
    """
    runtime_api_base_url = MCPRuntimeConfig.mcp_runtime_api_url
    delete_endpoint = f"{runtime_api_base_url}/api/deployments/{deployment_id}"

    logger.info(
        "Deleting MCP runtime deployment",
        deployment_id=deployment_id,
        delete_endpoint=delete_endpoint,
    )

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.delete(delete_endpoint)

            if response.status_code == HTTPStatus.OK:
                logger.info(
                    "Successfully deleted MCP runtime deployment",
                    deployment_id=deployment_id,
                )
                return True

            if response.status_code == HTTPStatus.NOT_FOUND:
                logger.warning(
                    "MCP runtime deployment not found (already deleted or never existed)",
                    deployment_id=deployment_id,
                )
                return True

            response.raise_for_status()
            return True

    except httpx.HTTPStatusError as e:
        logger.error(
            "Failed to delete MCP runtime deployment - HTTP error",
            deployment_id=deployment_id,
            status_code=e.response.status_code,
            error=str(e),
        )
        return False
    except httpx.TimeoutException as e:
        logger.error(
            "Failed to delete MCP runtime deployment - timeout",
            deployment_id=deployment_id,
            error=str(e),
        )
        return False
    except Exception as e:
        logger.error(
            "Failed to delete MCP runtime deployment - unexpected error",
            deployment_id=deployment_id,
            error=str(e),
        )
        return False
