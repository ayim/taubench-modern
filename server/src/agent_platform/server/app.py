from typing import Any
from uuid import UUID

import structlog
from fastapi import FastAPI, Request
from fastapi.openapi.constants import REF_PREFIX
from fastapi.responses import ORJSONResponse
from pydantic import BaseModel, Field
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

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


# NOTE: We are intentionally using Pydantic models here despite our design principles
# of avoiding Pydantic in our codebase. This is necessary because FastAPI's OpenAPI
# generation requires Pydantic models to automatically generate JSON schemas.
# Without these models, we cannot customize the error response schemas in our
# OpenAPI documentation to match our actual error envelope format.
class ErrorDetail(BaseModel):
    """Pydantic model for error detail - used only for OpenAPI schema generation."""

    error_id: UUID = Field(..., description="Unique ID for tracing")
    code: str = Field(..., description="Error code in format 'family.code'")
    message: str = Field(..., description="Human readable error message")


class ErrorEnvelope(BaseModel):
    """Pydantic model for error envelope - used only for OpenAPI schema generation.

    This matches the exact structure returned by our error handlers:
    {
        "error": {
            "error_id": "<uuid>",
            "code": "<family.code>",
            "message": "<human-readable>"
        }
    }
    """

    error: ErrorDetail


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
        """Customize the OpenAPI schema to include our custom error responses.

        This method:
        1. Customizes the enum related to the architecture field (legacy behavior)
        2. Adds our ErrorEnvelope schema to components
        3. Replaces all error response schemas with our custom format
        4. Removes FastAPI's default validation error schemas
        """
        if self.__custom_openapi_schema:
            return self.__custom_openapi_schema
        openapi_schema = FastAPI.openapi(self)

        # Get the list of architecture names (legacy behavior)
        components: dict = openapi_schema.get("components", {})
        schemas: dict = components.get("schemas", {})

        # Only modify AgentAdvancedConfig if it exists
        agent_advanced_config_schema: dict = schemas.get("AgentAdvancedConfig", {})
        if agent_advanced_config_schema:
            properties: dict = agent_advanced_config_schema.get("properties", {})
            architecture_field = properties.get("architecture", {})
            if architecture_field:
                architecture_field["enum"] = sorted(["agent", "plan_execute"])

        # ------------------------------------------------------------------
        # 1. Register our custom error schemas in components
        # ------------------------------------------------------------------
        # Use a ref template that points directly at #/components/schemas/
        _ref_template = REF_PREFIX + "{model}"

        # Register ErrorDetail first so ErrorEnvelope can reference it
        if "ErrorDetail" not in schemas:
            schemas["ErrorDetail"] = ErrorDetail.model_json_schema(ref_template=_ref_template)

        # Generate ErrorEnvelope schema that references ErrorDetail via components
        envelope_schema = ErrorEnvelope.model_json_schema(ref_template=_ref_template)
        # The generated schema may still contain an internal "$defs" section; remove it
        envelope_schema.pop("$defs", None)
        schemas["ErrorEnvelope"] = envelope_schema

        # Remove FastAPI's default validation schemas since we're replacing them
        schemas.pop("HTTPValidationError", None)
        schemas.pop("ValidationError", None)

        # ------------------------------------------------------------------
        # 2. Replace existing error responses with ErrorEnvelope schema
        # ------------------------------------------------------------------
        # Only replace error codes that already exist on endpoints
        error_codes_to_replace = {"400", "401", "403", "404", "405", "409", "422", "429", "500"}

        for path_item in openapi_schema.get("paths", {}).values():
            for operation in path_item.values():  # get/post/put/...
                responses = operation.get("responses", {})

                # Only modify responses that already exist and are error codes we handle
                for status_code in list(responses.keys()):
                    if status_code in error_codes_to_replace:
                        response_obj = responses[status_code]
                        # Replace the content with our ErrorEnvelope schema, preserving description
                        response_obj["content"] = {
                            "application/json": {"schema": {"$ref": REF_PREFIX + "ErrorEnvelope"}}
                        }

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
    workitems_app = None

    apps_to_lifespans = [mcp_app, agent_mcp]
    if SystemConfig.enable_workitems:
        logger.info("Starting workitems server")
        from agent_platform.workitems import make_workitems_app

        workitems_app = make_workitems_app(agent_app=app_private_v2)
        apps_to_lifespans.append(workitems_app)
    else:
        logger.info("Workitems server is disabled")

    # Main FastAPI app to include both versions

    app = _CustomFastAPI(
        title="Sema4.ai Agent Server API",
    )
    app.router.lifespan_context = create_combined_lifespan(*apps_to_lifespans)

    # Lift workitems app state into the main app
    if workitems_app:
        for k, v in workitems_app.state._state.items():
            logger.info(f"Carrying over Workitems app state: {k} = {v}")
            app.state._state[k] = v

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
    if workitems_app:
        app.mount("/api/work-items", workitems_app)

    return app
