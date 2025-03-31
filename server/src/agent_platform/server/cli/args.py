"""Defines the CLI arguments for the Agent Server."""

import argparse
from dataclasses import dataclass
from os import PathLike

import structlog

import agent_platform.server

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


@dataclass
class ServerArgs:
    host: str = "127.0.0.1"
    port: int = 8000
    version: bool = False
    license: bool = False
    parent_pid: int = 0
    use_data_dir_lock: bool = False
    kill_lock_holder: bool = False
    config_path: PathLike | None = None
    data_dir: PathLike | None = None
    log_dir: PathLike | None = None
    ignore_config: bool = False
    show_config: bool = False
    export_config: bool = False


def parse_args() -> ServerArgs:
    """Parse the CLI arguments for the Agent Server."""
    parser = argparse.ArgumentParser(description="Run the Sema4.ai Agent Server.")
    parser.add_argument(
        "--host",
        type=str,
        help=(
            "Host address to run the HTTP server on. "
            "Default is from config or '0.0.0.0'."
        ),
    )
    parser.add_argument(
        "--port",
        type=int,
        help=("Port to run the HTTP server on. Default is from config or 8000."),
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
        default=0,
        help="Parent PID of the agent server (when the given pid exits, "
        "the agent server will also exit).",
    )
    parser.add_argument(
        "--use-data-dir-lock",
        action="store_true",
        help="Use a lock file to prevent multiple instances of the agent server "
        "from running in the same data directory (defined by the "
        "SEMA4AI_AGENT_SERVER_HOME or SEMA4AI_STUDIO_HOME environment variable).",
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
        "SEMA4AI_AGENT_SERVER_HOME or SEMA4AI_STUDIO_HOME environment variable, "
        "in that order. If none of the above are set, the server defaults are used.",
    )
    parser.add_argument(
        "--log-dir",
        type=str,
        default=None,
        help="Path to the log directory. If not provided, defaults to the "
        "SEMA4AI_AGENT_SERVER_HOME or SEMA4AI_STUDIO_HOME environment variable, "
        "in that order. If none of the above are set, the server defaults are used.",
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
        help="Show the current configuration and exit. Shows defaults for any "
        "missing values and provides usage information.",
    )
    parser.add_argument(
        "--export-config",
        action="store_true",
        help="Export the current configuration as JSON without any additional text. "
        "Useful for shell redirection (e.g., --export-config > config.json)",
    )
    args = parser.parse_args()
    logger.debug(f"Parsed command-line arguments: {vars(args)}")
    return ServerArgs(**vars(args))
