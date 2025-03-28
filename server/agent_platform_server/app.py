from typing import Any

import structlog
from fastapi import FastAPI
from fastapi.responses import ORJSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from sema4ai_agent_server import __version__
from sema4ai_agent_server.api.private_v1 import router as v1_router
from sema4ai_agent_server.api.public_v1 import router as v2_router
from sema4ai_agent_server.lifespan import lifespan
from sema4ai_agent_server.storage.option import get_storage

PUBLIC_V1_PREFIX = "/api/public/v1"
PRIVATE_V1_PREFIX = "/api/v1"

logger = structlog.get_logger(__name__)


# HTTPMiddleware to ensure that all requests are prefixed with /api/v1 or /api/public/v1
class EnsureAPIPrefixMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not request.url.path.startswith((PUBLIC_V1_PREFIX, PRIVATE_V1_PREFIX)):
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
        title="Sema4.ai Agent Server Private API Version 1",
    )
    app_v1.include_router(v1_router)

    # Version 2 API
    app_v2 = _CustomFastAPI(
        title="Sema4.ai Agent Server Public API Version 1",
    )
    app_v2.include_router(v2_router)

    # Main FastAPI app to include both versions
    app = FastAPI(
        lifespan=lifespan,
        openapi_url=None,  # Disable the default /openapi.json path
    )

    app.add_middleware(EnsureAPIPrefixMiddleware)
    app.include_router(v1_router)
    app.include_router(v2_router)

    # Mount the API versions under their respective prefixes
    app.mount(PRIVATE_V1_PREFIX, app_v1)
    app.mount(PUBLIC_V1_PREFIX, app_v2)

    @app.get("/api/v1/health")
    async def health() -> dict:
        return {"status": "ok"}

    @app.get("/api/v1/metrics")
    async def metrics() -> dict:
        return {
            "agentCount": await get_storage().agent_count(),
            "threadCount": await get_storage().thread_count(),
        }

    return app
