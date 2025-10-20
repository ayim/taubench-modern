import json
import os
from dataclasses import dataclass
from typing import Any, ClassVar

import structlog

from agent_platform.core.configurations.config_validation import (
    ConfigType,
    validate_config_type,
    validate_config_value,
)
from agent_platform.server.storage import StorageService

logger = structlog.get_logger(__name__)


@dataclass
class QuotaConfig:
    """Configuration for a single quota setting."""

    storage_key: ConfigType
    default_value: int
    description: str
    env_vars: list[str]


class QuotasService:
    """Singleton service for managing system quotas and limits."""

    _instance = None
    _config_values: dict[str, int]

    # Config type constants - using actual storage keys for strict typing
    WORK_ITEM_PAYLOAD_SIZE = ConfigType.MAX_WORK_ITEM_PAYLOAD_SIZE
    WORK_ITEM_FILE_ATTACHMENT_SIZE = ConfigType.MAX_WORK_ITEM_FILE_ATTACHMENT_SIZE
    MAX_AGENTS = ConfigType.MAX_AGENTS
    PARALLEL_WORK_ITEMS = ConfigType.MAX_PARALLEL_WORK_ITEMS
    MCP_SERVERS_PER_AGENT = ConfigType.MAX_MCP_SERVERS
    AGENT_THREAD_RETENTION_PERIOD_DAYS = ConfigType.AGENT_THREAD_RETENTION_PERIOD
    POSTGRES_POOL_MAX_SIZE = ConfigType.POSTGRES_POOL_MAX_SIZE

    # Storage key constants imported from config_validation (single source of truth)

    # Configuration mapping for all config types
    CONFIG_TYPES: ClassVar[dict[str, QuotaConfig]] = {
        WORK_ITEM_PAYLOAD_SIZE: QuotaConfig(
            storage_key=ConfigType.MAX_WORK_ITEM_PAYLOAD_SIZE,
            default_value=100,
            description="Maximum work item payload size in KB",
            env_vars=["SEMA4AI_AGENT_SERVER_MAX_WORK_ITEM_PAYLOAD_SIZE_IN_KB"],
        ),
        WORK_ITEM_FILE_ATTACHMENT_SIZE: QuotaConfig(
            storage_key=ConfigType.MAX_WORK_ITEM_FILE_ATTACHMENT_SIZE,
            default_value=100,
            description="Maximum work item file attachment size in MB",
            env_vars=["SEMA4AI_AGENT_SERVER_MAX_WORK_ITEM_FILE_ATTACHMENT_SIZE_IN_MB"],
        ),
        MAX_AGENTS: QuotaConfig(
            storage_key=ConfigType.MAX_AGENTS,
            default_value=100,
            description="Maximum number of agents",
            env_vars=["SEMA4AI_AGENT_SERVER_MAX_AGENTS"],
        ),
        PARALLEL_WORK_ITEMS: QuotaConfig(
            storage_key=ConfigType.MAX_PARALLEL_WORK_ITEMS,
            default_value=10,
            description="Maximum parallel work items in process",
            env_vars=["SEMA4AI_AGENT_SERVER_MAX_PARALLEL_WORK_ITEMS_IN_PROCESS"],
        ),
        MCP_SERVERS_PER_AGENT: QuotaConfig(
            storage_key=ConfigType.MAX_MCP_SERVERS,
            default_value=30,
            description="Maximum MCP servers per agent",
            env_vars=["SEMA4AI_AGENT_SERVER_MAX_MCP_SERVERS_IN_AGENT"],
        ),
        AGENT_THREAD_RETENTION_PERIOD_DAYS: QuotaConfig(
            storage_key=ConfigType.AGENT_THREAD_RETENTION_PERIOD,
            default_value=90,
            description="Retention period for agent threads in days",
            env_vars=["SEMA4AI_AGENT_SERVER_AGENT_THREAD_RETENTION_PERIOD"],
        ),
        POSTGRES_POOL_MAX_SIZE: QuotaConfig(
            storage_key=ConfigType.POSTGRES_POOL_MAX_SIZE,
            default_value=50,
            description="Maximum PostgreSQL connection pool size (applies to Psycopg/SQLAlchemy)",
            env_vars=["SEMA4AI_AGENT_SERVER_POSTGRES_POOL_MAX_SIZE", "POSTGRES_POOL_MAX_SIZE"],
        ),
    }

    def __init__(self):
        """Private constructor. Use get_instance() to get the singleton instance."""
        raise RuntimeError(
            """
            QuotasService is a singleton. Use QuotasService.get_instance()
            instead of direct instantiation.
            """
        )

    @classmethod
    def _create(cls) -> "QuotasService":
        """Private method to create the singleton instance internally."""
        # Bypass __init__ by creating the instance directly
        instance = cls.__new__(cls)

        # Initialize config values with defaults
        instance._config_values = {}
        for config_type, config in cls.CONFIG_TYPES.items():
            instance._config_values[config_type] = config.default_value

        return instance

    @classmethod
    async def get_instance(cls) -> "QuotasService":
        """Get the singleton instance of QuotasService."""
        if cls._instance is None:
            cls._instance = cls._create()
            await cls._instance._initialize_from_storage()
            # Apply environment variable overrides and persist them so that
            # the entire system uses a single, consistent source of truth.
            await cls._instance._apply_env_overrides_and_persist()
        return cls._instance

    async def _initialize_from_storage(self) -> None:
        """Load configuration values from storage and update instance variables.

        Uses default values if individual configs are corrupted, but fails fast on storage issues.

        Raises:
            Exception: If storage is unavailable or other critical infrastructure errors occur
        """
        # Let storage/database connection errors propagate - these are critical
        config_list = await StorageService.get_instance().list_all_configs()
        storage_key_to_config_type = {
            config.storage_key: config_type for config_type, config in self.CONFIG_TYPES.items()
        }

        for current_config in (item for item in config_list if item.namespace == "global"):
            storage_key = current_config.config_type
            if storage_key in storage_key_to_config_type:
                config_type = storage_key_to_config_type[storage_key]
                try:
                    # Fix a regression introduced in this PR [https://github.com/Sema4AI/agent-platform/pull/614]
                    # Before this PR, the config value was stored as a dict
                    # which had the following structure: {"current": VALUE}
                    if isinstance(current_config.config_value, dict):
                        default_value = self.CONFIG_TYPES[current_config.config_type].default_value
                        current_value = int(
                            current_config.config_value.get("current", default_value)
                        )
                    else:
                        current_value = int(current_config.config_value)

                    self._config_values[config_type] = current_value
                    logger.info(
                        "Loaded config from storage", storage_key=storage_key, value=current_value
                    )
                except (json.JSONDecodeError, KeyError, ValueError) as e:
                    default_value = self.CONFIG_TYPES[config_type].default_value
                    logger.error(
                        "Failed to parse config, using default value",
                        storage_key=storage_key,
                        config_value=current_config.config_value,
                        default_value=default_value,
                        error=str(e),
                    )
                    continue
            else:
                logger.error(
                    "Unknown config type encountered",
                    storage_key=storage_key,
                    config_value=current_config.config_value,
                )

    async def _apply_env_overrides_and_persist(self) -> None:
        """Scan env vars for quota overrides and persist effective values.

        For each quota, if any of its declared env vars is set, validate and persist
        the value using the same code path as user-set configs. This ensures that
        runtime side-effects (e.g., resizing Postgres pools) are applied.
        """
        applied_postgres_pool_from_env = False

        for config_key, quota_config in self.CONFIG_TYPES.items():
            config_type_enum: ConfigType = ConfigType(config_key)
            selected_env_value: str | None = None
            selected_env_var: str | None = None
            for env_var in quota_config.env_vars:
                value = os.getenv(env_var)
                if value is not None and value != "":
                    selected_env_value = value
                    selected_env_var = env_var
                    break

            if selected_env_value is None:
                continue

            try:
                new_int_value = validate_config_value(config_type_enum, selected_env_value)
                current_value = self._get_config_value(config_type_enum)

                # At this point, we have a valid env var value,
                # and it's not equal to the value of the same var in storage.
                # Prefer the env var value over the storage value.
                if new_int_value != current_value:
                    # For Postgres Pool size, setting a flag to
                    # apply either the env var value or the storage value.
                    if config_type_enum is self.POSTGRES_POOL_MAX_SIZE:
                        applied_postgres_pool_from_env = True
                    await self._set_config_value(config_type_enum, selected_env_value)
                    logger.info(
                        f"Applied env override for quota {config_type_enum}: "
                        f"new value {selected_env_value} from env var {selected_env_var}"
                    )
            except Exception as e:
                logger.error(
                    f"Invalid env override for quota {config_type_enum}; keeping existing value. "
                    f"Error: {e!s}"
                )

        # If no env override for pool size, apply the persisted/default value once
        if not applied_postgres_pool_from_env:
            current_pool_size = self._get_config_value(self.POSTGRES_POOL_MAX_SIZE)
            await self._validate_and_apply_postgres_pool_max_size(current_pool_size)

    async def _set_config_value(self, config_type: ConfigType, new_value: str) -> None:
        """Generic method to set a config value.

        Args:
            config_type: The type of configuration to set
            new_value: The new value as a string

        Raises:
            PlatformHTTPError: If the value is invalid for the given config type
        """
        # Validate both config type and value - this will raise PlatformHTTPError if invalid
        int_value = validate_config_value(config_type, new_value)

        config = self.CONFIG_TYPES[config_type]
        # Pre-validate against current pool min_size when updating postgres pool size
        if config_type is self.POSTGRES_POOL_MAX_SIZE:
            await self._validate_and_apply_postgres_pool_max_size(int_value)
        await StorageService.get_instance().set_config(config.storage_key, new_value)
        self._config_values[config_type] = int_value

    async def _validate_and_apply_postgres_pool_max_size(self, new_value: int) -> None:
        """Validate and apply the postgres pool max size."""
        storage = StorageService.get_instance()

        await storage.apply_pool_size(new_value)

    def _get_config_value(self, config_type: ConfigType) -> int:
        """Generic method to get a config value."""
        validate_config_type(config_type)

        return self._config_values[config_type]

    # Specific quota methods for backward compatibility and clarity
    async def set_max_work_item_payload_size(self, new_value: str) -> None:
        """Set maximum work item payload size in KB."""
        await self._set_config_value(self.WORK_ITEM_PAYLOAD_SIZE, new_value)

    def get_max_work_item_payload_size(self) -> int:
        """Get maximum work item payload size in KB."""
        return self._get_config_value(self.WORK_ITEM_PAYLOAD_SIZE)

    async def set_max_work_item_file_attachment_size(self, new_value: str) -> None:
        """Set maximum work item file attachment size in MB."""
        await self._set_config_value(self.WORK_ITEM_FILE_ATTACHMENT_SIZE, new_value)

    def get_max_work_item_file_attachment_size(self) -> int:
        """Get maximum work item file attachment size in MB."""
        return self._get_config_value(self.WORK_ITEM_FILE_ATTACHMENT_SIZE)

    async def set_max_agents(self, new_value: str) -> None:
        """Set maximum number of agents."""
        await self._set_config_value(self.MAX_AGENTS, new_value)

    def get_max_agents(self) -> int:
        """Get maximum number of agents."""
        return self._get_config_value(self.MAX_AGENTS)

    async def set_max_parallel_work_items_in_process(self, new_value: str) -> None:
        """Set maximum parallel work items in process."""
        await self._set_config_value(self.PARALLEL_WORK_ITEMS, new_value)

    def get_max_parallel_work_items_in_process(self) -> int:
        """Get maximum parallel work items in process."""
        return self._get_config_value(self.PARALLEL_WORK_ITEMS)

    async def set_max_mcp_servers_in_agent(self, new_value: str) -> None:
        """Set maximum MCP servers per agent."""
        await self._set_config_value(self.MCP_SERVERS_PER_AGENT, new_value)

    def get_max_mcp_servers_in_agent(self) -> int:
        """Get maximum MCP servers per agent."""
        return self._get_config_value(self.MCP_SERVERS_PER_AGENT)

    def get_agent_thread_retention_period(self) -> int:
        return self._get_config_value(self.AGENT_THREAD_RETENTION_PERIOD_DAYS)

    def get_postgres_pool_max_size(self) -> int:
        """Get maximum PostgreSQL/Postgres SQLAlchemy connection pool size."""
        return self._get_config_value(self.POSTGRES_POOL_MAX_SIZE)

    async def set_postgres_pool_max_size(self, new_value: str) -> None:
        """Set maximum PostgreSQL/Postgres SQLAlchemy connection pool size."""
        await self._set_config_value(self.POSTGRES_POOL_MAX_SIZE, new_value)

    def get_all_configs(self) -> dict[str, dict[str, Any]]:
        """Get all config values with their configurations."""
        return {
            config_type: {
                "value": self._config_values[config_type],
                "description": config.description,
                "storage_key": config.storage_key,
            }
            for config_type, config in self.CONFIG_TYPES.items()
        }

    async def set_config(self, config_type: ConfigType, new_value: str) -> None:
        """Set a config value by its type."""
        await self._set_config_value(config_type, new_value)

    def get_config(self, config_type: ConfigType) -> int:
        """Get a config value by its type."""
        return self._get_config_value(config_type)
