import sys

import structlog
from agent_platform import server

from agent_platform.server.cli import (
    ServerArgs,
    ServerLifecycleManager,
    parse_args,
    parse_config_path_args,
    print_config,
    print_license,
    print_openapi_spec,
    set_no_logging,
)
from agent_platform.server.configuration_manager import (
    ConfigurationService,
)
from agent_platform.server.log_config import setup_logging

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def main(run_server: bool = True) -> None:
    """Run the server.

    Args:
        run_server: Whether to run the server (otherwise just return after setup)

    Raises:
        SystemExit: With the exit code from the server lifecycle manager
    """
    # Set up basic logging with environment variables before any configuration
    setup_logging(default_mode=True)

    args: ServerArgs = parse_args()

    # Disable logging if certain arguments are provided
    set_no_logging(args)
    setup_logging(default_mode=True, log_level=args.log_level)

    logger.info(f"{args.name.title()} version {server.__version__} starting...")

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
    if overrides == {config_key: {}}:
        overrides = None

    # Step 1: Initialize only the essential configurations needed for startup
    # This allows us to import constants and set up paths before loading
    # the full application
    ConfigurationService.initialize(
        config_path,
        config_modules=["agent_platform.server.constants"],
        overrides=overrides,
    )

    # Now we can import the constants and other modules that rely on them.
    from agent_platform.server.constants import SystemPaths

    # Set up full logging with system configuration
    setup_logging(default_mode=False)

    # Log configuration information
    config_status = "using defaults" if not is_config_path else "from file"
    logger.info(
        f"Initialized essential configurations: config_path={config_path} "
        f"({config_status}), data_dir={SystemPaths.data_dir}, "
        f"log_dir={SystemPaths.log_dir}",
    )

    # Debug point to ensure we're getting past the show-config check
    logger.debug("Past initial argument checks, proceeding with configuration")

    # Handle config output or schema export actions
    if args.export_config:
        print_config(should_exit=True, export_path=args.export_config)

    if args.generate_openapi_spec_only:
        print_openapi_spec(
            should_exit=True,
            private_path=args.private_openapi_file,
            public_path=args.public_openapi_file,
        )

    if sys.platform == "win32":
        # Fix: psycopg.pool - WARNING:  error connecting in 'pool-1': Psycopg cannot use the
        # 'ProactorEventLoop' to run in async mode. Please use a compatible event loop,
        # for instance by setting 'asyncio.set_event_loop_policy(WindowsSelectorEventLoopPolicy())'
        import asyncio

        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    # Create and run the server lifecycle manager
    lifecycle_manager = ServerLifecycleManager(args)
    exit_code = lifecycle_manager.run(run_server=run_server)
    sys.exit(exit_code)
