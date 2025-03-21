import argparse
import os
import platform
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
VERSION = "1.2.2-alpha"


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


def is_port_in_use(port: int) -> bool:
    """Check if a port is already in use without binding to it.

    Uses psutil to check active connections, which is more reliable on Windows
    and avoids the race condition of binding/releasing.

    Args:
        port: The port number to check

    Returns:
        bool: True if the port is in use, False otherwise
    """
    try:
        import psutil

        # Check all network connections for this port
        for conn in psutil.net_connections():
            try:
                if conn.laddr.port == port:
                    # Port is definitely in use
                    return True
            except (PermissionError, OSError) as e:
                logger.warning(f"Could not use psutil to check port {port}: {e}")
                logger.warning("Port availability checks may be less reliable")
                continue
    except Exception as e:
        logger.warning(
            f"Could not use psutil to check ports, port checks may be unreliable: {e}"
        )
        return False

    # If we got here and found no active connections using this port,
    # it's likely available
    return False


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
        # Will handle the case where the parent PID does not exist.
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

    # On Windows, explicitly check if the port is in use first. This is needed because
    # Uvicorn's bind_socket method uses the `SO_REUSEADDR` socket option, which on Windows
    # will allow the socket to bind to a socket that is already in use by another process.
    if args.port != 0 and platform.system() == "Windows":
        logger.debug(f"Checking if port {args.port} is already in use")
        if is_port_in_use(args.port):
            error_msg = (
                f"Port {args.port} is already in use. Please choose a different port."
            )
            logger.error(error_msg)
            sys.exit(1)

    # Create a Config instance to use Uvicorn's built-in bind_socket method
    config = uvicorn.Config(
        app=app,
        host=args.host,
        port=args.port,
        reload=args.reload,
    )

    # Bind the socket using Uvicorn's method - this handles all the socket setup
    # and returns a bound socket, eliminating any race condition
    try:
        logger.debug(f"Attempting to bind to {args.host}:{args.port}")
        sock = config.bind_socket()
        # Get the actual port from the socket
        # For IPv4, getsockname() returns (host, port)
        # For IPv6, getsockname() returns (host, port, flowinfo, scopeid)
        # So we take the second element in both cases
        actual_socket_info = sock.getsockname()
        actual_host, port = actual_socket_info[:2]
        logger.debug(f"Successfully bound socket to {actual_host}:{port}")

    except (OSError, SystemExit) as e:
        e_msg = str(e) if isinstance(e, OSError) else f"Uvicorn exit code: {e}"
        # Log specific error messages that tests will look for
        if isinstance(e, OSError):
            if "Address already in use" in str(e):
                logger.error(
                    f"Port {args.port} is already in use. Address already in use."
                )
            else:
                logger.error(f"Failed to bind socket: {e_msg}")
        else:
            logger.error(f"Failed to bind socket: {e_msg}")

        logger.error("Cannot continue without binding to a socket. Exiting.")
        sys.exit(1)

    # When binding to 0.0.0.0 (all interfaces), the socket may report a specific IP
    # For proper network URL construction, we need to handle this carefully
    if args.host == "0.0.0.0" and actual_host != args.host:
        logger.info(
            f"Socket bound to all interfaces (0.0.0.0) but actual socket reports: {actual_host}"
        )
        # We'll still use 0.0.0.0 or the provided host for the PID file for user-friendliness
        bound_host = args.host
    elif args.host == "::" and actual_host != args.host:
        logger.info(
            f"Socket bound to all IPv6 interfaces (::) but actual socket reports: {actual_host}"
        )
        bound_host = args.host
    elif actual_host != args.host and args.host not in ["localhost", "127.0.0.1"]:
        # If requested host doesn't match actual and isn't a special case, log a warning
        logger.warning(
            f"Requested host {args.host} differs from actual bound host {actual_host}"
        )
        # Decide whether to use the actual bound host or the requested host
        bound_host = actual_host  # Use the actual bound host for accuracy
    else:
        # Host matches or is a special case, use the requested host
        bound_host = args.host

    # Write pid file with port, pid and base_url info
    import json

    pid_file = Path(DATA_DIR) / "agent-server.pid"
    host = bound_host
    addr_format = "%s://%s:%d"
    if ":" in host:
        # It's an IPv6 address.
        addr_format = "%s://[%s]:%d"

    protocol_name = "http"  # TODO: Make this configurable
    base_url = addr_format % (protocol_name, host, port)

    data = {
        "port": port,
        "pid": os.getpid(),
        "base_url": base_url,
        "host": host,  # Add the actual host we're bound to
    }
    if args.use_data_dir_lock:
        data["lock_file"] = (DATA_DIR / "agent-server.lock").as_posix()
    else:
        data["lock_file"] = "<not used>"

    pid_file.write_text(json.dumps(data))
    logger.info(f"Agent Server running on: {base_url} (Press CTRL+C to quit)")
    logger.info(f"pid file: {pid_file}")

    # Create server instance with our config
    server = uvicorn.Server(config)

    # Set up our own signal handlers to ensure graceful shutdown
    import signal

    def signal_handler(sig, frame):
        logger.info(f"Received signal {sig}, shutting down...")
        # Force exit the server
        server.should_exit = True
        # No need to call sys.exit() here, we'll let the server shutdown gracefully

    # Register our signal handlers for common termination signals
    for sig in [signal.SIGINT, signal.SIGTERM]:
        signal.signal(sig, signal_handler)

    # Run the server with our pre-bound socket
    # Use server.run instead of asyncio.run(server.serve()) to properly handle signals
    try:
        server.run(sockets=[sock])
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, shutting down...")
        # This is a fallback in case our signal handler didn't catch it
    except Exception as e:
        logger.exception(f"Unexpected error running server: {e}")
    finally:
        logger.info("Server shutdown complete.")


if __name__ == "__main__":
    main()
