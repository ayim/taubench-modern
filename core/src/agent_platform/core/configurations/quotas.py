import json
from dataclasses import dataclass
from typing import Any, ClassVar

import structlog

from agent_platform.core.configurations.config_validation import (
    STORAGE_KEY_MAX_AGENTS,
    STORAGE_KEY_MAX_MCP_SERVERS,
    STORAGE_KEY_MAX_PARALLEL_WORK_ITEMS,
    STORAGE_KEY_MAX_WORK_ITEM_FILE_ATTACHMENT_SIZE,
    STORAGE_KEY_MAX_WORK_ITEM_PAYLOAD_SIZE,
    ConfigType,
    validate_config_type,
)
from agent_platform.server.storage import StorageService

logger = structlog.get_logger(__name__)


@dataclass
class QuotaConfig:
    """Configuration for a single quota setting."""

    storage_key: str
    default_value: int
    description: str


class QuotasService:
    """Singleton service for managing system quotas and limits."""

    _instance = None
    _config_values: dict[str, int]

    # Config type constants - using actual storage keys for strict typing
    WORK_ITEM_PAYLOAD_SIZE = STORAGE_KEY_MAX_WORK_ITEM_PAYLOAD_SIZE
    WORK_ITEM_FILE_ATTACHMENT_SIZE = STORAGE_KEY_MAX_WORK_ITEM_FILE_ATTACHMENT_SIZE
    MAX_AGENTS = STORAGE_KEY_MAX_AGENTS
    PARALLEL_WORK_ITEMS = STORAGE_KEY_MAX_PARALLEL_WORK_ITEMS
    MCP_SERVERS_PER_AGENT = STORAGE_KEY_MAX_MCP_SERVERS

    # Storage key constants imported from config_validation (single source of truth)

    # Configuration mapping for all config types
    CONFIG_TYPES: ClassVar[dict[str, QuotaConfig]] = {
        WORK_ITEM_PAYLOAD_SIZE: QuotaConfig(
            storage_key=STORAGE_KEY_MAX_WORK_ITEM_PAYLOAD_SIZE,
            default_value=100,
            description="Maximum work item payload size in KB",
        ),
        WORK_ITEM_FILE_ATTACHMENT_SIZE: QuotaConfig(
            storage_key=STORAGE_KEY_MAX_WORK_ITEM_FILE_ATTACHMENT_SIZE,
            default_value=100,
            description="Maximum work item file attachment size in MB",
        ),
        MAX_AGENTS: QuotaConfig(
            storage_key=STORAGE_KEY_MAX_AGENTS,
            default_value=100,
            description="Maximum number of agents",
        ),
        PARALLEL_WORK_ITEMS: QuotaConfig(
            storage_key=STORAGE_KEY_MAX_PARALLEL_WORK_ITEMS,
            default_value=10,
            description="Maximum parallel work items in process",
        ),
        MCP_SERVERS_PER_AGENT: QuotaConfig(
            storage_key=STORAGE_KEY_MAX_MCP_SERVERS,
            default_value=30,
            description="Maximum MCP servers per agent",
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

        for current_config in config_list:
            storage_key = current_config.config_type
            if storage_key in storage_key_to_config_type:
                config_type = storage_key_to_config_type[storage_key]
                try:
                    config_value_json = json.loads(current_config.config_value)
                    current_value = int(config_value_json["current"])
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

    async def _set_config_value(self, config_type: ConfigType, new_value: str) -> None:
        """Generic method to set a config value."""
        validate_config_type(config_type)

        config = self.CONFIG_TYPES[config_type]
        int_value = int(new_value)

        await StorageService.get_instance().set_config(config.storage_key, new_value)
        self._config_values[config_type] = int_value

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
