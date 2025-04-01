"""Module for parsing CLI arguments associated with Agent Server configuration."""

import json
import sys
from os import PathLike
from pathlib import Path
from typing import Literal

import structlog

from agent_platform.server.agent_architectures.arch_manager import AgentArchManager
from agent_platform.server.cli.args import ServerArgs
from agent_platform.server.configuration_manager import get_configuration_manager
from agent_platform.server.constants import default_config_path

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def get_config_path(config_path: PathLike | None) -> Path:
    """Get the configuration path from the CLI arguments."""
    if config_path is None:
        return default_config_path()
    return Path(config_path)


def parse_config_path_args(
    args: ServerArgs,
    exit_on_error: bool = False,
) -> tuple[Path, bool]:
    """Check the configuration arguments, returning the parsed config path
    and whether it exists.

    Args:
        args: The CLI arguments.
        exit_on_error: Whether to exit the program on error.

    Returns:
        The parsed config path and whether it exists.
    """
    if args.config_path is None:
        config_path = default_config_path()
    else:
        config_path = get_config_path(args.config_path)
    is_config_path = config_path.exists()
    if not is_config_path:
        logger.error(f"Configuration file not found: {config_path}")
        if exit_on_error:
            sys.exit(1)
    return config_path, is_config_path


def load_full_config(
    load_trusted_architectures: bool = True,
    additional_packages: list[str] | None = None,
) -> None:
    """Load the full configuration.

    Args:
        load_trusted_architectures: Whether to load trusted architectures.
        additional_packages: Additional packages to scan for configurations.
    """
    manager = get_configuration_manager()
    if additional_packages is None:
        additional_packages = []
    packages_to_scan = [
        "agent_platform.core",
        "agent_platform.server",
        *additional_packages,
    ]
    if load_trusted_architectures:
        arch_manager = AgentArchManager(
            wheels_path="./todo-for-out-of-process/wheels",
            websocket_addr="todo://think-about-out-of-process",
        )
        packages_to_scan.extend(
            [name for name, _ in arch_manager.in_process_allowlist],
        )
    # TODO: add out-of-process architectures
    manager.reload(packages_to_scan=packages_to_scan)


def print_config(mode: Literal["show", "export"], should_exit: bool = True) -> None:
    """Print the configuration."""
    logger.debug(
        f"{'--show-config' if mode == 'show' else '--export-config'} "
        f"flag detected, displaying {mode} ",
        f"configuration{'' if not should_exit else ' and exiting'}",
    )

    # Get the complete configuration
    load_full_config()
    manager = get_configuration_manager()
    complete_config = manager.get_complete_config()

    if mode == "export":
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
            "2. The server looks for the configuration file in the following order:",
        )
        print(
            "   - Path specified by SEMA4AI_AGENT_SERVER_CONFIG_PATH "
            "environment variable",
        )
        print("   - SEMA4AI_AGENT_SERVER_HOME/agent-server-config.json")
        print("   - SEMA4AI_STUDIO_HOME/agent-server-config.json")
        print("   - Current working directory")
        print("\n3. To create or modify a configuration file:")
        print(
            "   a. Use --export-config > agent-server-config.json to create a template",
        )
        print("   b. Save it as a JSON file (e.g., agent-server-config.json)")
        print("   c. Place it in one of the locations listed above")
        print("   d. Edit the file to customize your settings")
        print(
            "\n4. The configuration file supports partial updates - "
            "you only need to specify",
        )
        print(
            "   the settings you want to override. Default values will be used for any",
        )
        print("   unspecified settings.")
        print(
            "\n5. Configuration changes require editing the file and "
            "restarting the server.",
        )
        print("   Runtime configuration updates are not supported.")
        print(
            "\n6. For development/testing, you can also use the --config-path argument",
        )
        print("   to specify a custom configuration file location.")
    if should_exit:
        sys.exit(0)
