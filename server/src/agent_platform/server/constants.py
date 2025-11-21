import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from agent_platform.core.configurations import Configuration, FieldMetadata

# Determine if we are running in a frozen environment (via PyInstaller)
IS_FROZEN = getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")
"""
True if the application is running in a frozen environment (e.g. via PyInstaller)
"""


def _normalized_path(path: str | Path) -> Path:
    return Path(os.path.normpath(os.path.abspath(path)))


ROOT = _normalized_path(Path(__file__).parent.parent)
"""
The root directory of the application. You can find static files, like LICENSE,
in this directory.
"""

DEFAULT_CONFIG_FILE_NAME = "agent-server-config.yaml"


def _hyphenated_name(name: str) -> str:
    return name.lower().replace(" ", "-")


@dataclass(frozen=True)
class SystemConfig(Configuration):
    """System-wide configuration settings for the agent server.

    This configuration manages general settings like logging configuration,
    database type, and other non-path related settings.
    """

    # Server configuration
    name: str = field(
        default="Agent Server",
        metadata=FieldMetadata(
            description="The name of the agent server.",
            env_vars=["SEMA4AI_AGENT_SERVER_NAME"],
        ),
    )
    host: str = field(
        default="127.0.0.1",
        metadata=FieldMetadata(
            description="The host address of the agent server.",
            env_vars=["SEMA4AI_AGENT_SERVER_HOST"],
        ),
    )
    port: int = field(
        default=8000,
        metadata=FieldMetadata(
            description="The port number of the agent server.",
            env_vars=["SEMA4AI_AGENT_SERVER_PORT"],
        ),
    )
    parent_pid: int = field(
        default=0,
        metadata=FieldMetadata(
            description=(
                "The parent process ID of the agent server (when "
                "the given pid exits, the agent server will also exit)."
            ),
            env_vars=["SEMA4AI_AGENT_SERVER_PARENT_PID"],
        ),
    )
    use_data_dir_lock: bool = field(
        default=False,
        metadata=FieldMetadata(
            description=(
                "Whether to use a lock on the data directory. "
                "If True, the agent server will not start if the lock file exists."
            ),
            env_vars=["SEMA4AI_AGENT_SERVER_USE_DATA_DIR_LOCK"],
        ),
    )
    kill_lock_holder: bool = field(
        default=False,
        metadata=FieldMetadata(
            description=(
                "Whether to kill the lock holder of the data directory. "
                "If True, the agent server will kill the process holding the lock file "
                "when it starts up if the lock file exists."
            ),
            env_vars=["SEMA4AI_AGENT_SERVER_KILL_LOCK_HOLDER"],
        ),
    )
    ignore_config: bool = field(
        default=False,
        metadata=FieldMetadata(
            description=(
                "Whether to ignore the configuration file. "
                "If True, the agent server will not load the configuration file "
                "and will use the default values."
            ),
            env_vars=["SEMA4AI_AGENT_SERVER_IGNORE_CONFIG"],
        ),
    )

    # Database configuration
    db_type: Literal["sqlite", "postgres"] = field(
        default="sqlite",
        metadata=FieldMetadata(
            description="The type of database to use. Must be one of: 'sqlite', 'postgres'.",
            env_vars=["SEMA4AI_AGENT_SERVER_DB_TYPE", "DB_TYPE"],
        ),
    )

    # File manager configuration
    file_manager_type: Literal["local", "cloud"] = field(
        default="local",
        metadata=FieldMetadata(
            description="The type of file manager to use.",
            env_vars=[
                "SEMA4AI_AGENT_SERVER_FILE_MANAGER_TYPE",
                "S4_AGENT_SERVER_FILE_MANAGER_TYPE",
            ],
        ),
    )

    # Logging settings
    log_level: str = field(
        default="INFO",
        metadata=FieldMetadata(
            description=(
                "The log level to use. "
                "Must be one of: 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'."
            ),
            env_vars=["SEMA4AI_AGENT_SERVER_LOG_LEVEL", "LOG_LEVEL"],
        ),
    )
    log_max_backup_files: int = field(
        default=5,
        metadata=FieldMetadata(
            description=(
                "The maximum number of backup files to keep. "
                "If the number of backup files exceeds this value, the oldest "
                "backup file will be deleted."
            ),
            env_vars=[
                "SEMA4AI_AGENT_SERVER_LOG_MAX_BACKUP_FILES",
                "LOG_MAX_BACKUP_FILES",
            ],
        ),
    )
    log_file_size: int = field(
        default=10 * 1_048_576,  # 10MB
        metadata=FieldMetadata(
            description=(
                "The maximum size of the log file. "
                "If the log file exceeds this value, it will be rotated. "
                "The default value is 10MB."
            ),
            env_vars=["SEMA4AI_AGENT_SERVER_LOG_FILE_SIZE", "LOG_FILE_SIZE"],
        ),
    )

    # CORS settings
    cors_mode: Literal["all", None] = field(
        default=None,
        metadata=FieldMetadata(
            description=(
                "The mode for CORS settings. Can be 'all', or None. "
                "If 'all', all origins, methods, headers are allowed. "
                "If anything else, CORS is not enabled."
            ),
            env_vars=["SEMA4AI_AGENT_SERVER_CORS_MODE"],
        ),
    )

    # MCP configuration
    mcp_servers_config_file: str | None = field(
        default=None,
        metadata=FieldMetadata(
            description="Path to the configuration file containing MCP server definitions.",
            env_vars=["SEMA4AI_AGENT_SERVER_MCP_SERVERS_CONFIG_FILE"],
        ),
    )

    def __post_init__(self) -> None:
        """Validate configuration settings."""
        # Validate db_type
        if self.db_type not in ("sqlite", "postgres"):
            raise ValueError(f"Invalid database type: {self.db_type}")

        # Validate cors_mode
        if self.cors_mode not in ("all", None):
            raise ValueError(
                f"Invalid CORS mode: {self.cors_mode}. Must be one of: 'all', or None.",
            )

        # Validate port
        if not isinstance(self.port, int) or self.port < 0 or self.port > 65535:  # noqa: PLR2004
            raise ValueError(f"Invalid port number: {self.port}")

    @property
    def debug_mode(self) -> bool:
        """Determine if debug mode is enabled based on log level."""
        return self.log_level in ["DEBUG", "TRACE"]

    @property
    def hyphenated_name(self) -> str:
        """The hyphenated name of the agent server."""
        return _hyphenated_name(self.name)


def default_config_path() -> Path:
    """Get the default configuration path for the agent server.

    This path can be overridden by setting the SEMA4AI_AGENT_SERVER_CONFIG_PATH
    environment variable.

    Returns:
        The default path to the configuration file.
    """
    # Default is the current working directory with the default config file name
    potential_path = Path.cwd() / DEFAULT_CONFIG_FILE_NAME

    return _normalized_path(potential_path)


@dataclass(frozen=True)
class SystemPaths(Configuration):
    """System path configuration for the agent server.

    This configuration manages all file system paths used by the server.
    """

    # Environment variable fallbacks
    data_dir: Path = field(
        default=Path("."),
        metadata=FieldMetadata(
            description="Base directory for all data storage",
            env_vars=[
                "SEMA4AI_AGENT_SERVER_DATA_DIR",
                "SEMA4AI_AGENT_SERVER_HOME",
                "S4_AGENT_SERVER_HOME",
                "SEMA4AI_STUDIO_HOME",
            ],
        ),
    )

    log_dir: Path = field(
        default=Path("."),
        metadata=FieldMetadata(
            description="Directory for storing log files",
            env_vars=[
                "SEMA4AI_AGENT_SERVER_LOG_DIR",
                "SEMA4AI_STUDIO_LOG",
                "SEMA4AI_STUDIO_HOME",
            ],
        ),
    )

    agent_trace_dir: Path | None = field(
        default=None,
        metadata=FieldMetadata(
            description="Directory for storing agent trace files",
            env_vars=[
                "SEMA4AI_AGENT_SERVER_AGENT_TRACE_DIR",
            ],
        ),
    )

    # Derived paths
    vector_database_path: Path = field(init=False)
    domain_database_path: Path = field(init=False)
    log_file_path: Path = field(init=False)
    upload_dir: Path = field(init=False)
    config_dir: Path = field(init=False)

    def __post_init__(self) -> None:
        """Initialize derived paths after the main paths are set."""
        # We need to use object.__setattr__ because the dataclass is frozen
        object.__setattr__(self, "vector_database_path", self.data_dir / "chroma_db")
        object.__setattr__(
            self,
            "domain_database_path",
            self.data_dir / "agentserver.db",
        )
        object.__setattr__(self, "log_file_path", self.log_dir / "agent-server.log")
        object.__setattr__(self, "upload_dir", self.data_dir / "uploads")
        object.__setattr__(self, "config_dir", self.data_dir / "config")


WORK_ITEMS_SYSTEM_USER_SUB = "tenant:work-items:system:system_user"
EVALS_SYSTEM_USER_SUB = "tenant:evals:system:system_user"
PREINSTALLED_AGENTS_SYSTEM_USER_SUB = "tenant:preinstalled-agents:system:system_user"
