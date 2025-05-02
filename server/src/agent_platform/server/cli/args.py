"""Defines the CLI arguments for the Agent Server."""

import argparse
from dataclasses import dataclass
from os import PathLike

import structlog

import agent_platform.server
from agent_platform.server.constants import DEFAULT_CONFIG_FILE_NAME, SystemConfig
from agent_platform.server.log_config import disable_logging

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


# Note: that at parse time, the SystemConfig values will not be loaded, so we would
# be getting the default values here.
@dataclass
class ServerArgs:
    name: str = SystemConfig.name
    host: str = SystemConfig.host
    port: int = SystemConfig.port
    version: bool = False
    license: bool = False
    parent_pid: int = SystemConfig.parent_pid
    use_data_dir_lock: bool = SystemConfig.use_data_dir_lock
    kill_lock_holder: bool = SystemConfig.kill_lock_holder
    config_path: PathLike | None = None
    data_dir: PathLike | None = None
    log_dir: PathLike | None = None
    ignore_config: bool = SystemConfig.ignore_config
    export_config: PathLike | None = None
    log_level: str = SystemConfig.log_level


def set_no_logging(args: ServerArgs) -> None:
    """Disables logging across the server when certain arguments are provided."""
    # Config output is not included here because it may be useful to the user to see
    # how the config was loaded, but we could add it.
    no_logging_args = [
        args.license,
        args.export_config,
    ]
    if any(no_logging_args):
        disable_logging()


def parse_args() -> ServerArgs:
    """Parse the CLI arguments for the Agent Server."""
    parser = argparse.ArgumentParser(
        prog="agent-server",
        description="Run the Sema4.ai Agent Server.",
    )
    parser.add_argument(
        "--host",
        type=str,
        default=SystemConfig.host,
        help=(
            "Host address to run the HTTP server on. "
            f"Default is from config or '{SystemConfig.host}'."
        ),
    )
    parser.add_argument(
        "--port",
        type=int,
        default=SystemConfig.port,
        help=(
            f"Port to run the HTTP server on. Default is from config or "
            f"{SystemConfig.port}."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"Sema4.ai Agent Server v{agent_platform.server.__version__}",
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
        default=SystemConfig.parent_pid,
        help="Parent PID of the agent server (when the given pid exits, "
        "the agent server will also exit).",
    )
    parser.add_argument(
        "--use-data-dir-lock",
        action="store_true",
        help="Use a lock file to prevent multiple instances of the agent server "
        "from running in the same data directory.",
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
        help=(
            f"Path to the config file or directory. If a directory is provided, any "
            f".yaml, .yml, or .json file in the directory will be loaded. "
            f"Search order if not specified: "
            f"1. SEMA4AI_AGENT_SERVER_CONFIG_PATH environment variable "
            f"2. SEMA4AI_AGENT_SERVER_HOME/{DEFAULT_CONFIG_FILE_NAME} "
            f"3. SEMA4AI_STUDIO_HOME/{DEFAULT_CONFIG_FILE_NAME} "
            f"4. File '{DEFAULT_CONFIG_FILE_NAME}' in the current working directory"
        ),
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default=None,
        help=(
            "Path to the data directory. If not provided, the environment variable "
            "SEMA4AI_AGENT_SERVER_DATA_DIR or SEMA4AI_STUDIO_DATA_DIR will be used, "
            "in that order. If none of the above are set, the current working "
            "directory will be used."
        ),
    )
    parser.add_argument(
        "--log-dir",
        type=str,
        default=None,
        help=(
            "Path to the log directory. If not provided, the environment variable "
            "SEMA4AI_AGENT_SERVER_LOG_DIR or SEMA4AI_STUDIO_LOG_DIR will be used, "
            "in that order. If none of the above are set, the current working "
            "directory will be used."
        ),
    )
    parser.add_argument(
        "--ignore-config",
        action="store_true",
        help="Ignore the configuration file and use the defaults, CLI "
        "arguments or environment variables.",
    )
    parser.add_argument(
        "--export-config",
        type=str,
        nargs="?",
        const=True,
        default=False,
        help="Output the current configuration as YAML with documentation comments. "
        "If a value is provided, the configuration will be written to that file path. "
        "If the specified file path is a directory, the default filename will be used. "
        "If no value is provided, the configuration will be printed to stdout.",
    )
    parser.add_argument(
        "--name",
        type=str,
        default=SystemConfig.name,
        help=f"Name of the agent server process, defaults to '{SystemConfig.name}'.",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default=SystemConfig.log_level,
        help=f"Log level to use, defaults to '{SystemConfig.log_level}'.",
    )
    args = parser.parse_args()
    logger.debug(f"Parsed command-line arguments: {vars(args)}")
    return ServerArgs(**vars(args))
