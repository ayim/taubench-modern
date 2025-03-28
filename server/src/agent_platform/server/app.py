from typing import Any

import structlog
from fastapi import FastAPI
from fastapi.responses import ORJSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from agent_platform.server import __version__
from agent_platform.server.api.private_v2 import router as private_v2_router
from agent_platform.server.lifespan import lifespan
from agent_platform.server.storage.option import get_storage

PRIVATE_V2_PREFIX = "/api/v2"

logger = structlog.get_logger(__name__)


# HTTPMiddleware to ensure that all requests are prefixed with /api/v1 or /api/public/v1
class EnsureAPIPrefixMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not request.url.path.startswith((PRIVATE_V2_PREFIX,)):
            return ORJSONResponse(status_code=404, content={"detail": "Not Found"})
        return await call_next(request)


class _CustomFastAPI(FastAPI):
    def __init__(self, title="Sema4.ai Agent Server API") -> None:
        self.__custom_openapi_schema: dict | None = None
        super().__init__(
            title=title,
            version=__version__,
            default_response_class=ORJSONResponse,  # Use more efficient JSON serialization
            separate_input_output_schemas=False,
        )

    def openapi(self) -> dict[str, Any]:
        """Customize the enum related to the architecture field. This now
        only returns the legacy architecture names.
        """
        if self.__custom_openapi_schema:
            return self.__custom_openapi_schema
        openapi_schema = FastAPI.openapi(self)
        # Get the list of architecture names
        components: dict = openapi_schema.get("components", {})
        schemas: dict = components.get("schemas", {})
        agent_advanced_config_schema: dict = schemas.get("AgentAdvancedConfig", {})
        properties: dict = agent_advanced_config_schema.get("properties", {})
        architecture_field = properties.get("architecture", {})
        architecture_field["enum"] = sorted(["agent", "plan_execute"])
        self.__custom_openapi_schema = openapi_schema
        return self.__custom_openapi_schema


def create_app() -> FastAPI:
    # Version 1 API
    app_v1 = _CustomFastAPI(
        title="Sema4.ai Agent Server Private API Version 2",
    )
    app_v1.include_router(private_v2_router)

    # Main FastAPI app to include both versions
    app = FastAPI(
        lifespan=lifespan,
        openapi_url=None,  # Disable the default /openapi.json path
    )

    app.add_middleware(EnsureAPIPrefixMiddleware)
    app.include_router(private_v2_router)

    # Mount the API versions under their respective prefixes
    app.mount(PRIVATE_V2_PREFIX, app_v1)

    @app.get("/api/v2/health")
    async def health() -> dict:
        return {"status": "ok"}

    @app.get("/api/v2/metrics")
    async def metrics() -> dict:
        return {
            "agentCount": await get_storage().agent_count(),
            "threadCount": await get_storage().thread_count(),
        }

    return app
