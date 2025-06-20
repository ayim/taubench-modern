from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import ORJSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware

from agent_platform.core.errors import ErrorCode, PlatformHTTPError
from agent_platform.server import __version__
from agent_platform.server.api import (
    PRIVATE_V2_PREFIX,
    PUBLIC_V2_PREFIX,
    private_v2_router,
    public_v2_router,
)
from agent_platform.server.api.agent_mcp import build_agent_mcp_app
from agent_platform.server.api.dependencies import StorageDependency
from agent_platform.server.api.mcp import MCPAuthenticationMiddleware, mcp
from agent_platform.server.constants import SystemConfig
from agent_platform.server.error_handlers import add_exception_handlers
from agent_platform.server.lifespan import create_combined_lifespan
from agent_platform.workitems import make_workitems_app

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


# HTTPMiddleware to ensure that all requests are prefixed with /api/v1 or /api/public/v1
class EnsureAPIPrefixMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not request.url.path.startswith(
            (
                PUBLIC_V2_PREFIX,
                PRIVATE_V2_PREFIX,
                "/api/v1",  # TODO: remove this once we're able (Backwards compat)
                "/api/v2/mcp",
                "/docs",
                "/openapi.json",
                "/api/work-items",
            ),
        ):
            logger.info("Rejecting unknown request", url=request.url)
            return PlatformHTTPError(ErrorCode.NOT_FOUND, "Not Found")
        return await call_next(request)


class _CustomFastAPI(FastAPI):
    def __init__(self, title="Sema4.ai Agent Server API") -> None:
        self.__custom_openapi_schema: dict | None = None
        super().__init__(
            title=title,
            version=__version__,
            # TODO: now the only place we use ORJSON I think? Does it _really_ help?
            default_response_class=ORJSONResponse,
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
    app_private_v2 = _CustomFastAPI(
        title="Sema4.ai Agent Server Private API Version 2",
    )
    app_private_v2.include_router(private_v2_router)
    add_exception_handlers(app_private_v2)

    app_public_v2 = _CustomFastAPI(
        title="Sema4.ai Agent Server Public API Version 2",
    )
    app_public_v2.include_router(public_v2_router)
    add_exception_handlers(app_public_v2)

    @app_private_v2.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    @app_private_v2.get("/metrics")
    async def metrics(storage: StorageDependency) -> dict:
        return {
            "agentCount": await storage.count_agents(),
            "threadCount": await storage.count_threads(),
        }

    mcp_app = mcp.streamable_http_app()
    agent_mcp = build_agent_mcp_app()
    workitems_app = make_workitems_app(agent_app=app_private_v2)

    # Main FastAPI app to include both versions

    app = FastAPI(
        lifespan=create_combined_lifespan(mcp_app, agent_mcp, workitems_app),
    )

    # Add authentication middleware to the MCP app to enable user-based authentication
    mcp_app.add_middleware(MCPAuthenticationMiddleware)
    app.mount("/api/v2/public-mcp/", mcp_app)
    app.mount("/api/v2/agent-mcp/", agent_mcp)

    # CORS middleware (completely configurable via SystemConfig)
    if SystemConfig.cors_mode == "all":
        # This is for local development ONLY. Simply allow all
        # origins, credentials, methods, headers, etc.
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.add_middleware(EnsureAPIPrefixMiddleware)
    app.include_router(private_v2_router)
    app.include_router(public_v2_router)
    # Mount the API versions under their respective prefixes
    app.mount(PRIVATE_V2_PREFIX, app_private_v2)
    app.mount(PUBLIC_V2_PREFIX, app_public_v2)

    # TODO: remove this once we're able
    app_private_v1 = _CustomFastAPI(
        title="Sema4.ai Agent Server Private API Version 1",
    )
    app_private_v1.include_router(private_v2_router)
    add_exception_handlers(app_private_v1)
    app.mount("/api/v1", app_private_v1)  # Backwards compatibility

    # Mount the work-items app
    app.mount("/api/work-items", workitems_app)

    return app
