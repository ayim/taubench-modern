from pathlib import Path
from typing import Any
from uuid import UUID

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.openapi.constants import REF_PREFIX
from fastapi.responses import HTMLResponse, ORJSONResponse
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
from agent_platform.server.api.agent_mcp import (
    AGENT_MCP_OPENAPI_SCHEMA_PATHS,
    build_agent_mcp_app,
)
from agent_platform.server.api.mcp import MCPAuthenticationMiddleware, mcp
from agent_platform.server.api.private_v2.health import router as health_router
from agent_platform.server.constants import SystemConfig
from agent_platform.server.error_handlers import add_exception_handlers
from agent_platform.server.lifespan import create_combined_lifespan
from agent_platform.server.openapi.platform_catalog import inject_platform_model_catalog

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
            ),
        ):
            logger.info("Rejecting unknown request", url=request.url)
            return PlatformHTTPError(ErrorCode.NOT_FOUND, "Not Found")
        return await call_next(request)


class _CustomFastAPI(FastAPI):
    def __init__(
        self,
        title="Sema4.ai Agent Server API",
        docs_url: str | None = "/docs",  # use the openapi generated landed page by default.
    ) -> None:
        self._custom_openapi_schema: dict | None = None
        super().__init__(
            title=title,
            version=__version__,
            docs_url=docs_url,
            default_response_class=ORJSONResponse,
            separate_input_output_schemas=False,
        )

    def _set_required_fields(self, schemas: dict[str, Any]) -> None:
        """Adds a required field to selected fields in schemas

        Mark platform_id as required in all platform parameter schemas.

        Auto-detects platform parameter schemas by name pattern and platform_id property,
        then ensures platform_id is marked as required in the OpenAPI schema.
        """
        for schema_name, schema in schemas.items():
            # Detect platform parameter schemas by checking if they have platform_id property
            if (
                schema_name.endswith("PlatformParameters")
                and isinstance(schema, dict)
                and "properties" in schema
                and "platform_id" in schema.get("properties", {})
            ):
                # Force platform_id to be required
                required_fields = schema.setdefault("required", [])
                if "platform_id" not in required_fields:
                    required_fields.append("platform_id")

    def openapi(self) -> dict[str, Any]:
        """Customize the OpenAPI schema to include our custom error responses.

        This method:
        1. Customizes the enum related to the architecture field (legacy behavior)
        2. Adds our ErrorEnvelope schema to components
        3. Replaces all error response schemas with our custom format
        4. Removes FastAPI's default validation error schemas
        """
        if self._custom_openapi_schema:
            return self._custom_openapi_schema
        openapi_schema = FastAPI.openapi(self)

        # Get the list of architecture names (legacy behavior)
        components: dict = openapi_schema.get("components", {})
        schemas: dict = components.get("schemas", {})
        _ref_template = REF_PREFIX + "{model}"

        inject_platform_model_catalog(components, schemas, _ref_template)

        # Only modify AgentAdvancedConfig if it exists
        agent_advanced_config_schema: dict = schemas.get("AgentAdvancedConfig", {})
        if agent_advanced_config_schema:
            properties: dict = agent_advanced_config_schema.get("properties", {})
            architecture_field = properties.get("architecture", {})
            if architecture_field:
                architecture_field["enum"] = sorted(["agent", "plan_execute"])

        # ------------------------------------------------------------------
        # Filter out deprecated PRECREATED status from WorkItemStatus enum
        # ------------------------------------------------------------------
        work_item_status_schema: dict = schemas.get("WorkItemStatus", {})
        if work_item_status_schema and "enum" in work_item_status_schema:
            # Remove PRECREATED from the enum values shown in OpenAPI docs
            enum_values = work_item_status_schema["enum"]
            work_item_status_schema["enum"] = [v for v in enum_values if v != "PRECREATED"]

        # ------------------------------------------------------------------
        # Set required for specific fields
        # ------------------------------------------------------------------
        self._set_required_fields(schemas)

        # ------------------------------------------------------------------
        # 1. Register our custom error schemas in components
        # ------------------------------------------------------------------
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

        self._custom_openapi_schema = openapi_schema
        return self._custom_openapi_schema


class _PublicAgentServerApp(_CustomFastAPI):
    def openapi(self) -> dict[str, Any]:
        should_update = not bool(self._custom_openapi_schema)
        result = super().openapi()

        if should_update:
            result["paths"] |= AGENT_MCP_OPENAPI_SCHEMA_PATHS
            self._custom_openapi_schema = result

        return result


def create_app() -> FastAPI:
    app = _agent_server_app()

    # /api/v2
    app_private_v2 = _CustomFastAPI(
        title="Sema4.ai Agent Server Private API Version 2",
    )
    app_private_v2.include_router(private_v2_router)
    app_private_v2.include_router(
        health_router,
        tags=["health"],
    )
    add_exception_handlers(app_private_v2)

    # /api/public/v1
    app_public_v2 = _PublicAgentServerApp(
        title="Sema4.ai Agent Server Public API Version 2",
    )
    app_public_v2.include_router(public_v2_router)
    add_exception_handlers(app_public_v2)

    # Create the FastMCP Apps (agent server as MCP and agent as MCP)
    mcp_app = mcp.streamable_http_app()
    agent_mcp = build_agent_mcp_app()
    # Add authentication middleware to the MCP app to enable user-based authentication
    mcp_app.add_middleware(MCPAuthenticationMiddleware)

    # Attach the MCP apps to the agent server App
    apps_to_lifespans = [mcp_app, agent_mcp]
    app.router.lifespan_context = create_combined_lifespan(*apps_to_lifespans)

    # Mount all of the sub-apps. This _must_ be the last step, else the combined lifespan
    # is overwritten.
    # Each mounted sub-application has its own independent lifecycle, including its own
    # lifespan. We need to mount all of the apps after the combined lifespan is applied.
    app.mount("/api/v2/public-mcp/", mcp_app)
    app.mount(f"{PUBLIC_V2_PREFIX}/agent-mcp/", agent_mcp)
    app.mount(PRIVATE_V2_PREFIX, app_private_v2)
    app.mount(PUBLIC_V2_PREFIX, app_public_v2)

    return app


def _agent_server_app() -> FastAPI:
    """
    Creates the top level agent server FastAPI app.
    """
    app = _CustomFastAPI(
        title="Sema4.ai Agent Server API",
        docs_url=None,  # We provide our own custom docs landing page.
    )

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

    # Ensure all requests have known prefixes.
    app.add_middleware(EnsureAPIPrefixMiddleware)

    # Ignore requests for favicon.ico
    @app.middleware("http")
    async def ignore_favicon(request: Request, call_next):
        if request.url.path == "/favicon.ico":
            return Response(content="", media_type="image/x-icon")
        return await call_next(request)

    # Custom docs landing page
    @app.get("/docs", response_class=HTMLResponse, include_in_schema=False)
    async def custom_docs_page():
        template_path = Path(__file__).parent / "templates" / "docs_landing.html"
        template_content = template_path.read_text(encoding="utf-8")
        # Replace template variables
        return template_content.replace("{{version}}", __version__)

    # Add exception handles to the root app as well (handles endpoint 404s and 405s)
    add_exception_handlers(app)

    return app
