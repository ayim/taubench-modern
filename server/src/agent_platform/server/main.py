import sys
from typing import Any  # Add typing imports for type annotations

import structlog

from agent_platform.server.cli.args import ServerArgs, parse_args
from agent_platform.server.cli.configurations import (
    parse_config_path_args,
    print_config,
)
from agent_platform.server.cli.license import print_license
from agent_platform.server.cli.lifecycle import ServerLifecycleManager
from agent_platform.server.configuration_manager import (
    init_configurations,
)
from agent_platform.server.log_config import setup_logging

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
                # Check connection structure to extract port safely
                if isinstance(conn.laddr, tuple):
                    # Check if tuple has enough elements to access index 1
                    if len(conn.laddr) > 1 and conn.laddr[1] == port:
                        return True
                else:
                    # For named tuple or object-like structure, use try/except
                    try:
                        laddr: Any = conn.laddr  # Type hint to avoid linter errors
                        if laddr.port == port:
                            return True
                    except AttributeError:
                        # This connection doesn't have the expected structure
                        continue
            except (PermissionError, OSError) as e:
                logger.warning(f"Could not use psutil to check port {port}: {e}")
                logger.warning("Port availability checks may be less reliable")
                continue
    except Exception as e:
        logger.warning(
            f"Could not use psutil to check ports, port checks may be unreliable: {e}",
        )
        return False

    # If we got here and found no active connections using this port,
    # it's likely available
    return False


def main():
    args: ServerArgs = parse_args()

    if args.license:
        print_license()

    config_path, is_config_path = parse_config_path_args(args)

    # Prepare configuration overrides
    config_key = "agent_platform.server.constants.SystemPaths"
    overrides = {config_key: {}}
    if args.data_dir:
        overrides[config_key]["data_dir"] = args.data_dir
    if args.log_dir:
        overrides[config_key]["log_dir"] = args.log_dir

    # Step 1: Initialize only the essential configurations needed for startup
    # This allows us to import constants and set up paths before loading
    # the full application
    init_configurations(
        config_path,
        config_modules=["agent_platform.server.constants"],
        overrides=overrides,
    )

    # Now we can import the constants and other modules that rely on them.
    from agent_platform.server.constants import SystemPaths

    setup_logging()

    # Log configuration information
    config_status = "using defaults" if not is_config_path else "from file"
    logger.info(
        f"Initialized essential configurations: config_path={config_path} "
        f"({config_status}), data_dir={SystemPaths.data_dir}, "
        f"log_dir={SystemPaths.log_dir}",
    )

    # Debug point to ensure we're getting past the show-config check
    logger.debug("Past initial argument checks, proceeding with configuration")

    # Handle show-config or export-config action
    if args.show_config or args.export_config:
        print_config(
            "show" if args.show_config else "export",
            should_exit=True,
        )
    logger.debug("Continuing with server initialization (not in show-config mode)")

    # Create and run the server lifecycle manager
    lifecycle_manager = ServerLifecycleManager(args)
    exit_code = lifecycle_manager.run()
    sys.exit(exit_code)
