import os
from pathlib import Path

import structlog
from fastapi import FastAPI

from agent_platform.server.app import create_app
from agent_platform.server.cli import parse_config_path_args
from agent_platform.server.cli.args import ServerArgs
from agent_platform.server.cli.configurations import load_full_config
from agent_platform.server.configuration_manager import ConfigurationService
from agent_platform.server.log_config import setup_logging


def create_dev_app() -> FastAPI:  # noqa: PLR0915
    """Development factory function for uvicorn --factory with proper setup.

    This replicates the essential setup from main.py but gets configuration
    from environment variables since uvicorn --factory doesn't pass CLI args:

    Environment variables supported:
    - AGENT_SERVER_LOG_LEVEL: Log level (default: INFO)
    - AGENT_SERVER_DATA_DIR: Data directory path
    - AGENT_SERVER_LOG_DIR: Log directory path
    - AGENT_SERVER_CONFIG_PATH: Configuration file path
    - AGENT_SERVER_IGNORE_CONFIG: Ignore config file (true/false)

    Usage: uvicorn agent_platform.server.dev:create_dev_app --factory --reload
    """

    # Step 1: Basic logging setup (same as main.py)
    setup_logging(default_mode=True)

    logger = structlog.get_logger(__name__)
    logger.info("Starting development server setup...")

    # Step 2: Create ServerArgs from environment variables (simulating CLI parsing)
    # This allows dev mode to respect the same preferences as normal mode
    data_dir_str = os.getenv("AGENT_SERVER_DATA_DIR")
    log_dir_str = os.getenv("AGENT_SERVER_LOG_DIR")
    config_path_str = os.getenv("AGENT_SERVER_CONFIG_PATH")

    args = ServerArgs(
        log_level=os.getenv("AGENT_SERVER_LOG_LEVEL", "INFO"),
        data_dir=Path(data_dir_str) if data_dir_str else None,
        log_dir=Path(log_dir_str) if log_dir_str else None,
        config_path=Path(config_path_str) if config_path_str else None,
        ignore_config=os.getenv("AGENT_SERVER_IGNORE_CONFIG", "false").lower() == "true",
        host="127.0.0.1",  # These don't matter for factory mode
        port=8000,  # uvicorn will override these anyway
    )

    # Step 3: Set up logging with user's preferred log level (same as main.py)
    setup_logging(default_mode=True, log_level=args.log_level)
    # Step 4: Handle configuration path (same logic as main.py)
    config_path, is_config_path = parse_config_path_args(args)
    # Step 5: Prepare configuration overrides (same as main.py)
    config_key = "agent_platform.server.constants.SystemPaths"
    overrides = {config_key: {}}

    # Set default data dir for dev mode if none specified
    if not args.data_dir:
        dev_data_dir = Path("/tmp/agent-server-dev")
        dev_data_dir.mkdir(parents=True, exist_ok=True)
        overrides[config_key]["data_dir"] = str(dev_data_dir)
        logger.info(f"Using default dev data directory: {dev_data_dir}")
    else:
        overrides[config_key]["data_dir"] = str(args.data_dir)

    if args.log_dir:
        overrides[config_key]["log_dir"] = str(args.log_dir)

    # Clean up overrides if empty (same as main.py)
    if overrides == {config_key: {}}:
        overrides = None

    # Step 6: Initialize configuration (same as main.py)
    try:
        ConfigurationService.initialize(
            config_path if not args.ignore_config else None,
            config_modules=["agent_platform.server.constants"],
            overrides=overrides,
        )

        config_status = "using defaults" if not is_config_path else "from file"
        if args.ignore_config:
            config_status = "ignoring config file"

        logger.info(f"Configuration initialized: config_path={config_path} ({config_status})")

    except Exception as e:
        logger.error(f"Configuration initialization failed: {e}")
        # Fall back to basic setup to prevent startup failure
        if not os.environ.get("DATA_DIR"):
            dev_data_dir = Path("/tmp/agent-server-dev")
            dev_data_dir.mkdir(parents=True, exist_ok=True)
            os.environ["DATA_DIR"] = str(dev_data_dir)

    # Step 7: Import SystemPaths after configuration (same as main.py)
    try:
        from agent_platform.server.constants import SystemPaths

        # Ensure directories exist
        SystemPaths.data_dir.mkdir(parents=True, exist_ok=True)
        if hasattr(SystemPaths, "log_dir"):
            SystemPaths.log_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Using data directory: {SystemPaths.data_dir}")
        logger.info(f"Using log directory: {getattr(SystemPaths, 'log_dir', 'default')}")

    except Exception as e:
        logger.warning(f"SystemPaths setup warning: {e}")

    # Step 8: Full logging setup (same as main.py)
    try:
        setup_logging(default_mode=False)
        logger.info("Full logging configuration applied")
    except Exception as e:
        logger.warning(f"Full logging setup failed, using fallback: {e}")
        # Keep the basic logging we already set up

    # Step 8.5: Load full configuration including OTELConfig (same as main.py lifecycle)
    # This is critical for telemetry and other Configuration classes to be initialized
    # with environment variables before the app starts
    logger.info("Loading full configuration...")
    load_full_config()
    logger.info("Full configuration loaded")

    # Step 9: Create FastAPI application
    logger.info("Creating FastAPI application...")
    app = create_app()
    logger.info("Development server setup complete!")

    return app
