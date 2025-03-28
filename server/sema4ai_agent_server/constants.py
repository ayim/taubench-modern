import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from agent_server_types.configurations import Configuration

from sema4ai_agent_server.env_vars import (
    CONFIG_PATH,
    DATA_DIR,
    DB_TYPE,
    LOG_DIR,
    LOG_FILE_SIZE,
    LOG_LEVEL,
    LOG_MAX_BACKUP_FILES,
)

# Determine if we are running in a frozen environment (via PyInstaller)
IS_FROZEN = getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")
"""
True if the application is running in a frozen environment (e.g. via PyInstaller)
"""


def _normalized_path(path: str) -> Path:
    return Path(os.path.normpath(os.path.abspath(path)))


ROOT = _normalized_path(Path(__file__).parent.parent)
"""
The root directory of the application. You can find static files, like LICENSE,
in this directory.
"""

DEFAULT_CONFIG_FILE_NAME = "agent-server-config.json"


@dataclass(frozen=True)
class SystemConfig(Configuration):
    """System-wide configuration settings for the agent server.

    This configuration manages general settings like logging configuration,
    database type, and other non-path related settings.
    """

    # Server configuration
    host: str = field(default="127.0.0.1")
    port: int = field(default=8000)

    # Database configuration
    db_type: Literal["sqlite", "postgres"] = field(
        default_factory=lambda: DB_TYPE or "sqlite"
    )

    # Logging settings
    log_level: str = field(default_factory=lambda: (LOG_LEVEL or "INFO").upper())
    log_max_backup_files: int = field(
        default_factory=lambda: int(LOG_MAX_BACKUP_FILES or "5")
    )
    log_file_size: int = field(
        default_factory=lambda: int(LOG_FILE_SIZE or str(10 * 1_048_576))
    )

    def __post_init__(self) -> None:
        """Validate configuration settings."""
        # Validate db_type
        if self.db_type not in ("sqlite", "postgres"):
            raise ValueError(f"Invalid database type: {self.db_type}")

        # Validate port
        if not isinstance(self.port, int) or self.port < 0 or self.port > 65535:
            raise ValueError(f"Invalid port number: {self.port}")

    @property
    def debug_mode(self) -> bool:
        """Determine if debug mode is enabled based on log level."""
        return self.log_level in ["DEBUG", "TRACE"]


def default_config_path() -> Path:
    """Get the default configuration path for the agent server, which is
    either the value of the SEMA4AI_AGENT_SERVER_CONFIG_PATH environment variable or
    the current working directory.
    """
    potential_path = CONFIG_PATH or Path.cwd() / DEFAULT_CONFIG_FILE_NAME
    # if path is a directory, add the default config file name to it
    if potential_path.is_dir():
        potential_path = potential_path / DEFAULT_CONFIG_FILE_NAME
    return _normalized_path(potential_path)


def default_data_dir() -> Path:
    """Get the default data directory for the agent server, which is
    either the value of the SEMA4AI_AGENT_SERVER_DATA_DIR environment variable or
    the current working directory.
    """
    return _normalized_path(DATA_DIR or ".")


def default_log_dir() -> Path:
    """Get the default log directory for the agent server, which is
    either the value of the SEMA4AI_AGENT_SERVER_LOG_DIR environment variable or
    the current working directory.
    """
    return _normalized_path(LOG_DIR or ".")


@dataclass(frozen=True)
class SystemPaths(Configuration):
    """System path configuration for the agent server.

    This configuration manages all file system paths used by the server.
    """

    # Environment variable fallbacks
    data_dir: Path = field(default_factory=default_data_dir)

    log_dir: Path = field(default_factory=default_log_dir)

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
            self, "domain_database_path", self.data_dir / "agentserver.db"
        )
        object.__setattr__(self, "log_file_path", self.log_dir / "agent-server.log")
        object.__setattr__(self, "upload_dir", self.data_dir / "uploads")
        object.__setattr__(self, "config_dir", self.data_dir / "config")
