import argparse
import json
import os
import platform
import sys
from pathlib import Path

import structlog
import uvicorn

import sema4ai_agent_server
from sema4ai_agent_server.configuration_manager import (
    get_configuration_manager,
    init_configurations,
)
from sema4ai_agent_server.constants import IS_FROZEN, ROOT, default_config_path
from sema4ai_agent_server.log_config import setup_logging

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


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
    parser = argparse.ArgumentParser(description="Run the Sema4.ai Agent Server.")
    parser.add_argument(
        "--host",
        type=str,
        help="Host address to run the HTTP server on. Default is from config or '0.0.0.0'.",
    )
    parser.add_argument(
        "--port",
        type=int,
        help="Port to run the HTTP server on. Default is from config or 8000.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"Sema4.ai Agent Server v{sema4ai_agent_server.__version__}",
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
        help="Parent PID of the agent server (when the given pid exits, the agent server "
        "will also exit).",
    )
    parser.add_argument(
        "--use-data-dir-lock",
        action="store_true",
        help="Use a lock file to prevent multiple instances of the agent server from running "
        "in the same data directory (defined by the SEMA4AI_AGENT_SERVER_HOME or "
        "SEMA4AI_STUDIO_HOME environment variable).",
    )
    parser.add_argument(
        "--kill-lock-holder",
        action="store_true",
        help="Kill the process holding the lock file (only used if --use-data-dir-lock "
        "is also used).",
    )
    parser.add_argument(
        "--config-path",
        type=str,
        default=None,
        help="Path to the configuration file. Search order if not specified: "
        "1. SEMA4AI_AGENT_SERVER_CONFIG_PATH environment variable "
        "2. SEMA4AI_AGENT_SERVER_HOME/agent-server-config.json "
        "3. SEMA4AI_STUDIO_HOME/agent-server-config.json "
        "4. Current working directory "
        "If no configuration file is found, server defaults will be used.",
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default=None,
        help="Path to the data directory. If not provided, defaults to the "
        "SEMA4AI_AGENT_SERVER_HOME or SEMA4AI_STUDIO_HOME environment variable, in that order. "
        "If none of the above are set, the server defaults are used.",
    )
    parser.add_argument(
        "--log-dir",
        type=str,
        default=None,
        help="Path to the log directory. If not provided, defaults to the "
        "SEMA4AI_AGENT_SERVER_HOME or SEMA4AI_STUDIO_HOME environment variable, in that order. "
        "If none of the above are set, the server defaults are used.",
    )
    parser.add_argument(
        "--ignore-config",
        action="store_true",
        help="Ignore the configuration file and use the defaults, CLI "
        "arguments or environment variables.",
    )
    parser.add_argument(
        "--show-config",
        action="store_true",
        help="Show the current configuration and exit. Shows defaults for any missing values "
        "and provides usage information.",
    )
    parser.add_argument(
        "--export-config",
        action="store_true",
        help="Export the current configuration as JSON without any additional text. "
        "Useful for shell redirection (e.g., --export-config > config.json)",
    )
    args = parser.parse_args()

    # Debug output to identify potential issues in argument parsing
    logger.debug(f"Parsed command-line arguments: {vars(args)}")

    # Handle quick exiting arguments.
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

    # Get configuration path
    if args.ignore_config:
        logger.info("Ignoring configuration file")
        config_path = None
        is_config_path = False
    else:
        config_path = (
            Path(args.config_path)
            if args.config_path is not None
            else default_config_path()
        )
        is_config_path = config_path.exists()
        if not is_config_path:
            logger.warning(f"Configuration file not found at {config_path}.")
            config_path = None

    # Prepare configuration overrides
    overrides = {}
    config_path_key = "sema4ai_agent_server.constants.SystemPaths"

    # Apply CLI data_dir and log_dir if provided
    if args.data_dir or args.log_dir:
        overrides[config_path_key] = {}

        if args.data_dir:
            overrides[config_path_key]["data_dir"] = str(Path(args.data_dir))

        if args.log_dir:
            overrides[config_path_key]["log_dir"] = str(Path(args.log_dir))

    # Step 1: Initialize only the essential configurations needed for startup
    # This allows us to import constants and set up paths before loading the full application
    init_configurations(
        config_path,
        config_modules=["sema4ai_agent_server.constants"],
        overrides=overrides,
    )

    # Now we can import the constants and other modules that rely on them.
    from sema4ai_agent_server.app import create_app
    from sema4ai_agent_server.constants import SystemConfig, SystemPaths

    logger.debug("Setting up logging")
    setup_logging()
    logger.debug("Logging setup complete")

    # Log configuration information
    config_status = "using defaults" if not is_config_path else "from file"

    logger.info(
        f"Initialized essential configurations: config_path={config_path} ({config_status}), "
        f"data_dir={SystemPaths.data_dir}, log_dir={SystemPaths.log_dir}"
    )

    # Debug point to ensure we're getting past the show-config check
    logger.debug("Past initial argument checks, proceeding with configuration")

    # Handle show-config or export-config action
    if args.show_config or args.export_config:
        from sema4ai_agent_server.agent_architecture_manager import (
            get_agent_architectures,
        )

        logger.debug(
            f"{'--show-config' if args.show_config else '--export-config'} flag detected, displaying configuration and exiting"
        )
        manager = get_configuration_manager()
        # Get all agent architectures so we can scan them for configurations
        agent_architectures = get_agent_architectures()
        packages_to_scan = [
            "sema4ai_agent_server",
            "agent_server_types",
            *[str(arch) for arch in agent_architectures],
        ]
        # Make sure all configurations are loaded
        manager.reload(packages_to_scan=packages_to_scan)

        # Get the complete configuration
        complete_config = manager.get_complete_config()

        if args.export_config:
            # Only output the raw JSON configuration for shell redirection
            print(json.dumps(complete_config, indent=2, default=str))
        else:
            # Show the configuration with helpful text
            print("\nConfiguration Information")
            print("========================")
            print("\nCurrent Configuration:")
            print("---------------------")
            # Use the get_complete_config method to get all values including defaults
            print(json.dumps(complete_config, indent=2, default=str))
            print(f"\nConfiguration file expected at: {manager.config_path}")
            print("\nConfiguration File Usage Guide")
            print("----------------------------")
            print("1. The configuration file should be a JSON file.")
            print(
                "2. The server looks for the configuration file in the following order:"
            )
            print(
                "   - Path specified by SEMA4AI_AGENT_SERVER_CONFIG_PATH environment variable"
            )
            print("   - SEMA4AI_AGENT_SERVER_HOME/agent-server-config.json")
            print("   - SEMA4AI_STUDIO_HOME/agent-server-config.json")
            print("   - Current working directory")
            print("\n3. To create or modify a configuration file:")
            print(
                "   a. Use --export-config > agent-server-config.json to create a template"
            )
            print("   b. Save it as a JSON file (e.g., agent-server-config.json)")
            print("   c. Place it in one of the locations listed above")
            print("   d. Edit the file to customize your settings")
            print(
                "\n4. The configuration file supports partial updates - you only need to specify"
            )
            print(
                "   the settings you want to override. Default values will be used for any"
            )
            print("   unspecified settings.")
            print(
                "\n5. Configuration changes require editing the file and restarting the server."
            )
            print("   Runtime configuration updates are not supported.")
            print(
                "\n6. For development/testing, you can also use the --config-path argument"
            )
            print("   to specify a custom configuration file location.")
        sys.exit(0)

    logger.debug("Continuing with server initialization (not in show-config mode)")

    # Use configuration values if CLI arguments are not provided
    host = args.host if args.host is not None else SystemConfig.host
    port = args.port if args.port is not None else SystemConfig.port

    logger.debug(f"Using host={host}, port={port} for server")

    if args.parent_pid:
        from sema4ai.common.autoexit import exit_when_pid_exits

        logger.info(f"Marking to exit when parent PID {args.parent_pid} exits.")
        # Will handle the case where the parent PID does not exist.
        exit_when_pid_exits(args.parent_pid, soft_kill_timeout=5)

    try:
        # We need to ensure the data directory exists.
        logger.debug(f"Creating data directory at {SystemPaths.data_dir}")
        SystemPaths.data_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.exception(f"Failed to create data directory: {SystemPaths.data_dir}")
        raise RuntimeError(
            f"Failed to create data directory: {SystemPaths.data_dir}"
        ) from e

    # Log the data directory permissions as a hex number.
    pretty_permissions = oct(SystemPaths.data_dir.stat().st_mode)
    logger.info(
        f"Data directory available at: {SystemPaths.data_dir} (permissions: {pretty_permissions})"
    )

    try:
        # We need to ensure the log directory exists.
        logger.debug(f"Creating log directory at {SystemPaths.log_dir}")
        SystemPaths.log_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.exception(f"Failed to create log directory: {SystemPaths.log_dir}")
        raise RuntimeError(
            f"Failed to create log directory: {SystemPaths.log_dir}"
        ) from e

    # Log the log directory permissions as a hex number.
    pretty_permissions = oct(SystemPaths.log_dir.stat().st_mode)
    logger.info(
        f"Log directory available at: {SystemPaths.log_dir} (permissions: {pretty_permissions})"
    )

    if args.use_data_dir_lock:
        from sema4ai.common.app_mutex import obtain_app_mutex

        logger.debug("Attempting to obtain app mutex lock")
        # The obtain_app_mutex function is used to obtain a mutex for the agent server.
        # The mutex obtained should be kept locked until the `mutex` variable is destroyed.
        mutex = obtain_app_mutex(
            kill_lock_holder=args.kill_lock_holder,
            data_dir=SystemPaths.data_dir,
            lock_basename="agent-server.lock",
            app_name="Agent Server",
            timeout=5,
        )
        if mutex is None:
            logger.error("Failed to obtain app mutex lock. Exiting.")
            sys.exit(1)
        logger.debug("Successfully obtained app mutex lock")
        # Otherwise, keep the mutex alive until the process exits (in a local variable).

    # On Windows, explicitly check if the port is in use first. This is needed because
    # Uvicorn's bind_socket method uses the `SO_REUSEADDR` socket option, which on Windows
    # will allow the socket to bind to a socket that is already in use by another process.
    if port != 0 and platform.system() == "Windows":
        logger.debug(f"Checking if port {port} is already in use")
        if is_port_in_use(port):
            error_msg = (
                f"Port {port} is already in use. Please choose a different port."
            )
            logger.error(error_msg)
            sys.exit(1)
        logger.debug(f"Port {port} is available")

    # Create a Config instance to use Uvicorn's built-in bind_socket method
    logger.debug("Creating Uvicorn config")
    config_kwargs = {
        "app": create_app(),
        "host": host,
        "port": port,
    }

    config = uvicorn.Config(**config_kwargs)
    logger.debug(f"Uvicorn config created: {config_kwargs}")

    # Bind the socket using Uvicorn's method - this handles all the socket setup
    # and returns a bound socket, eliminating any race condition
    try:
        logger.debug(f"Attempting to bind to {host}:{port}")
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
                logger.error(f"Port {port} is already in use. Address already in use.")
            else:
                logger.error(f"Failed to bind socket: {e_msg}")
        else:
            logger.error(f"Failed to bind socket: {e_msg}")

        logger.error("Cannot continue without binding to a socket. Exiting.")
        sys.exit(1)

    # When binding to 0.0.0.0 (all interfaces), the socket may report a specific IP
    # For proper network URL construction, we need to handle this carefully
    if host == "0.0.0.0" and actual_host != host:
        logger.info(
            f"Socket bound to all interfaces (0.0.0.0) but actual socket reports: {actual_host}"
        )
        # We'll still use 0.0.0.0 or the provided host for the PID file for user-friendliness
        bound_host = host
    elif host == "::" and actual_host != host:
        logger.info(
            f"Socket bound to all IPv6 interfaces (::) but actual socket reports: {actual_host}"
        )
        bound_host = host
    elif actual_host != host and host not in ["localhost", "127.0.0.1"]:
        # If requested host doesn't match actual and isn't a special case, log a warning
        logger.warning(
            f"Requested host {host} differs from actual bound host {actual_host}"
        )
        # Decide whether to use the actual bound host or the requested host
        bound_host = actual_host  # Use the actual bound host for accuracy
    else:
        # Host matches or is a special case, use the requested host
        bound_host = host

    # Write pid file with port, pid and base_url info
    pid_file = SystemPaths.data_dir / "agent-server.pid"
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
        data["lock_file"] = (SystemPaths.data_dir / "agent-server.lock").as_posix()
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

    # Step 2: Load all remaining configurations before running the server
    # This will use the already initialized manager and update it, not reinitialize it
    logger.info("Loading all configurations before starting server...")
    from sema4ai_agent_server.agent_architecture_manager import get_agent_architectures

    manager = get_configuration_manager()
    agent_architectures = get_agent_architectures()
    packages_to_scan = [
        "sema4ai_agent_server",
        "agent_server_types",
        *[str(arch) for arch in agent_architectures],
    ]
    # Load configurations from all core packages and any plugins
    manager.reload(packages_to_scan=packages_to_scan)

    # Run the server with our pre-bound socket
    # Use server.run instead of asyncio.run(server.serve()) to properly handle signals
    try:
        logger.debug("Starting Uvicorn server.run() with pre-bound socket")
        server.run(sockets=[sock])
        logger.debug("Uvicorn server.run() completed normally")
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, shutting down...")
        # This is a fallback in case our signal handler didn't catch it
    except Exception as e:
        logger.exception(f"Unexpected error running server: {e}")
    finally:
        logger.info("Server shutdown complete.")
