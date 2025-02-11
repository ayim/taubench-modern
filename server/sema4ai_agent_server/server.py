import argparse
import os
import sys
from pathlib import Path
from typing import Any

import structlog
from fastapi import FastAPI
from fastapi.responses import ORJSONResponse

from sema4ai_agent_server.agent_architecture_manager import architecture_names
from sema4ai_agent_server.api import router as api_router
from sema4ai_agent_server.constants import Constants
from sema4ai_agent_server.lifespan import lifespan
from sema4ai_agent_server.log_config import setup_logging
from sema4ai_agent_server.otel import setup_otel
from sema4ai_agent_server.storage.option import get_storage

# Do not change the version here. It is managed by versionbump (see versionbump.yaml)
VERSION = "1.1.4-alpha.74"

# TODO: Setting up global things (such as logging and OTEL here) globally in the module import
# is bad practice (because just importing it from some other place will mess up any logging
# already set -- for instance, if we want one logging in prod and another in tests).
# This should ideally be done in the main() function, but it seems that in some places
# instead of using the main() function, the agent server is started using a command line
# such as: "uvicorn sema4ai_agent_server.server:app --host 127.0.0.1 --port 8000"
# and then moving the code to the main() function doesn't work reliably (and if we move
# it to the _on_startup function, it's already too late for the logging), so, postponing
# this for now (need to check how ACE and Studio are starting it).
setup_logging()
setup_otel()

logger = structlog.get_logger(__name__)


# Determine the database type
DB_TYPE = os.environ.get("S4_AGENT_SERVER_DB_TYPE", "sqlite")

if DB_TYPE not in ("sqlite", "postgres"):
    raise ValueError(f"Unable to start agent server: Invalid database type: {DB_TYPE}")


# Get root of app, used to point to directory containing static files
ROOT = Path(__file__).parent.parent

# Determine if we are running in a frozen environment
IS_FROZEN = getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


class _CustomFastAPI(FastAPI):
    def __init__(self) -> None:
        self.__custom_openapi_schema: dict | None = None
        super().__init__(
            title="Sema4.ai Agent Server API",
            lifespan=lifespan,
            version=VERSION,
            default_response_class=ORJSONResponse,  # Use more efficient JSON serialization
            separate_input_output_schemas=False,  # TODO: Remove when FrontEnd is ready to handle it
        )

    def openapi(self) -> dict[str, Any]:
        if self.__custom_openapi_schema:
            return self.__custom_openapi_schema
        openapi_schema = FastAPI.openapi(self)
        # Get the list of architecture names
        components: dict = openapi_schema.get("components", {})
        schemas: dict = components.get("schemas", {})
        agent_advanced_config_schema: dict = schemas.get("AgentAdvancedConfig", {})
        properties: dict = agent_advanced_config_schema.get("properties", {})
        architecture_field = properties.get("architecture", {})
        # Set the enum property for the architecture field,
        # sorting to ensure consistent order across environments
        architecture_field["enum"] = sorted(
            architecture_names + ["agent", "plan_execute"]
        )
        self.__custom_openapi_schema = openapi_schema
        return self.__custom_openapi_schema


app = _CustomFastAPI()
app.include_router(api_router)


def _on_startup() -> None:
    # Ensure UPLOAD_DIR exists
    os.makedirs(Constants.UPLOAD_DIR, exist_ok=True)


app.add_event_handler("startup", _on_startup)


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
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host address to run the HTTP server on. Default is '0.0.0.0'.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to run the HTTP server on. Default is 8000.",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload of the server on code changes.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"Sema4.ai Agent Server v{VERSION}",
        help="Show program's version number and exit.",
    )
    parser.add_argument(
        "--license",
        action="store_true",
        help="Show program's license and exit.",
    )

    args = parser.parse_args()

    if args.license:
        if IS_FROZEN:
            # Paths in the __main__ module work differently in frozen environments
            # but outside of it they will all work as expected.
            license_path = Path(__file__).absolute().parent / "LICENSE"
        else:
            license_path = ROOT / "LICENSE"
        try:
            with open(license_path, "r") as f:
                print(f.read())
            sys.exit(0)
        except FileNotFoundError:
            print(
                "License file not found. Please visit https://sema4.ai for license information."
            )
            sys.exit(1)

    uvicorn.run(app, host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
