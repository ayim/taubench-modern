import argparse
import os
import sys
from pathlib import Path
from typing import Any

import structlog
from fastapi import FastAPI
from fastapi.responses import ORJSONResponse
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from sema4ai_agent_server.api.private_v1 import router as v1_router
from sema4ai_agent_server.api.public_v1 import router as v2_router
from sema4ai_agent_server.constants import Constants
from sema4ai_agent_server.lifespan import lifespan
from sema4ai_agent_server.log_config import setup_logging
from sema4ai_agent_server.otel import setup_otel
from sema4ai_agent_server.storage.option import get_storage

# Do not change the version here. It is managed by versionbump (see versionbump.yaml)
VERSION = "1.1.4-alpha.91"


PUBLIC_V1_PREFIX = "/api/public/v1"
PRIVATE_V1_PREFIX = "/api/v1"
# HTTPMiddleware to ensure that all requests are prefixed with /api/v1 or /api/public/v1
class EnsureAPIPrefixMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not request.url.path.startswith((PUBLIC_V1_PREFIX, PRIVATE_V1_PREFIX)):
            return ORJSONResponse(status_code=404, content={"detail": "Not Found"})
        return await call_next(request)

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
    def __init__(self, title="Sema4.ai Agent Server API") -> None:
        self.__custom_openapi_schema: dict | None = None
        super().__init__(
            title=title,
            version=VERSION,
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
    import socket

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
    parser.add_argument(
        "--parent-pid",
        type=int,
        default=0,
        help="Parent PID of the agent server (when the given pid exits, the agent server will also exit).",
    )
    parser.add_argument(
        "--use-data-dir-lock",
        action="store_true",
        help="Use a lock file to prevent multiple instances of the agent server from running in the same data directory (defined by the S4_AGENT_SERVER_HOME or SEMA4AI_STUDIO_HOME environment variable).",
    )
    parser.add_argument(
        "--kill-lock-holder",
        action="store_true",
        help="Kill the process holding the lock file (only used if --use-data-dir-lock is also used).",
    )

    args = parser.parse_args()

    from sema4ai_agent_server.constants import DATA_DIR

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

    if args.parent_pid:
        from sema4ai.common.autoexit import exit_when_pid_exits

        logger.info(f"Marking to exit when parent PID {args.parent_pid} exits.")
        exit_when_pid_exits(args.parent_pid, soft_kill_timeout=5)

    # We need to ensure the data directory exists.
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
    except Exception:
        raise RuntimeError(f"Failed to create data directory: {DATA_DIR}")

    # Log the data directory permissions as a hex number.
    pretty_permissions = oct(DATA_DIR.stat().st_mode)
    logger.info(f"Data directory: {DATA_DIR} (permissions: {pretty_permissions})")

    if args.use_data_dir_lock:
        from sema4ai.common.app_mutex import obtain_app_mutex

        # The obtain_app_mutex function is used to obtain a mutex for the agent server.
        # The mutex obtained should be kept locked until the `mutex` variable is destroyed.
        mutex = obtain_app_mutex(
            kill_lock_holder=args.kill_lock_holder,
            data_dir=Path(DATA_DIR),
            lock_basename="agent-server.lock",
            app_name="Agent Server",
            timeout=5,
        )
        if mutex is None:
            sys.exit(1)
        # Otherwise, keep the mutex alive until the process exits (in a local variable).

    # HACK: uvicorn does not provide any hook where we could get the socket that was bound,
    # so, we monkey-patch the startup to do what we need.
    original_startup = uvicorn.Server.startup

    async def startup(self, sockets: list[socket.socket] | None = None) -> None:
        import json

        try:
            await original_startup(self, sockets)

            sockets = self.servers[0].sockets
            config = self.config

            assert sockets, "Expected sockets to be already setup at this point."

            addr_format = "%s://%s:%d"
            host = "0.0.0.0" if config.host is None else config.host
            if ":" in host:
                # It's an IPv6 address.
                addr_format = "%s://[%s]:%d"

            port = config.port
            if port == 0:
                port = sockets[0].getsockname()[1]

            protocol_name = "https" if config.ssl else "http"
            base_url = addr_format % (protocol_name, host, port)

            # Write pid file with port, pid and base_url as json
            pid_file = Path(DATA_DIR) / "agent-server.pid"
            data = {
                "port": port,
                "pid": os.getpid(),
                "base_url": base_url,
            }
            if args.use_data_dir_lock:
                data["lock_file"] = (DATA_DIR / "agent-server.lock").as_posix()
            else:
                data["lock_file"] = "<not used>"

            pid_file.write_text(json.dumps(data))
            # Ok, we're ready now.
            message = f"Agent Server running on: {base_url} (Press CTRL+C to quit)"
            logger.info(message)
            logger.info(f"pid file: {pid_file}")
        except Exception:
            logger.exception("Error during startup")
            self.should_exit = True

    uvicorn.Server.startup = startup  # type: ignore

    uvicorn.run(app, host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
