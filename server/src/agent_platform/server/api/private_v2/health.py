"""Endpoints for health and readiness for the Kubernetes HPA."""

from dataclasses import dataclass

from fastapi import APIRouter, HTTPException, status

from agent_platform.server.shutdown_manager import ShutdownManager

router = APIRouter()


@dataclass
class HealthResponse:
    """Response model for health check endpoint."""

    status: str


@dataclass
class ReadyResponse:
    """Response model for readiness check endpoint."""

    status: str
    message: str


@router.get("/health")
async def health() -> HealthResponse:
    """Health check endpoint - always returns OK if server is running."""
    return HealthResponse(status="ok")


@router.get("/ready")
async def ready() -> ReadyResponse:
    """Readiness probe endpoint for Kubernetes.

    Returns:
        200 OK if server is HEALTHY and ready to accept requests
        503 Service Unavailable if server is DRAINING
    """
    if ShutdownManager.is_healthy():
        return ReadyResponse(status="ready", message="Server is ready to accept requests")
    else:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Server is draining and not accepting new requests",
        )
