import argparse
import os
from pathlib import Path

import structlog
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from fastapi.responses import ORJSONResponse

from sema4ai_agent_server.agent_architecture_manager import architecture_names
from sema4ai_agent_server.api import router as api_router
from sema4ai_agent_server.constants import UPLOAD_DIR
from sema4ai_agent_server.lifespan import lifespan
from sema4ai_agent_server.log_config import setup_logging
from sema4ai_agent_server.otel import setup_otel
from sema4ai_agent_server.storage.option import get_storage

# Do not change the version here. It is managed by versionbump (see versionbump.yaml)
VERSION = "1.1.0"

setup_logging()
setup_otel()
logger = structlog.get_logger(__name__)

# Ensure UPLOAD_DIR exists
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Determine the database type
DB_TYPE = os.environ.get("S4_AGENT_SERVER_DB_TYPE", "sqlite").lower()
# Get root of app, used to point to directory containing static files
ROOT = Path(__file__).parent.parent
app = FastAPI(
    title="Sema4.ai Agent Server API",
    lifespan=lifespan,
    version=VERSION,
    default_response_class=ORJSONResponse,  # Use more efficient JSON serialization
    separate_input_output_schemas=False,  # TODO: Remove when FrontEnd is ready to handle it
)
app.include_router(api_router)


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="Sema4.ai Agent Server API",
        version=VERSION,
        routes=app.routes,
        separate_input_output_schemas=False,  # TODO: Remove when FrontEnd is ready to handle it
    )
    # Get the list of architecture names
    components: dict = openapi_schema.get("components", {})
    schemas: dict = components.get("schemas", {})
    agent_advanced_config_schema: dict = schemas.get("AgentAdvancedConfig", {})
    properties: dict = agent_advanced_config_schema.get("properties", {})
    architecture_field = properties.get("architecture", {})
    # Set the enum property for the architecture field,
    # this includes the agent and plan_execute options for backwards compatibility.
    architecture_field["enum"] = architecture_names + ["agent", "plan_execute"]
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


@app.get("/api/v1/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/api/v1/metrics")
async def metrics() -> dict:
    return {
        "agentCount": await get_storage().agent_count(),
        "threadCount": await get_storage().thread_count(),
    }


def main():
    import uvicorn

    parser = argparse.ArgumentParser(description="Run the Sema4.ai Agent Server.")
    parser.add_argument(
        "-p",
        "--port",
        type=int,
        default=8000,
        help="Port to run the HTTP server on. Default is 8000.",
    )
    parser.add_argument(
        "-r",
        "--reload",
        action="store_true",
        help="Enable auto-reload of the server on code changes.",
    )

    args = parser.parse_args()
    uvicorn.run("server:app", host="0.0.0.0", port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
