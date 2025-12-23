from dataclasses import dataclass, field
from typing import Literal

from agent_platform.core.actions.action_utils import (
    get_spec_and_build_tool_definitions,
)
from agent_platform.core.mcp.mcp_types import MCPServerDetail
from agent_platform.core.tools.tool_definition import ToolDefinition
from agent_platform.core.utils import SecretString


@dataclass(frozen=True)
class ActionPackage:
    """Action package definition."""

    name: str = field(
        metadata={
            "description": "The name of the action package.",
        },
    )
    """The name of the action package."""

    organization: str = field(
        metadata={
            "description": "The organization of the action package.",
        },
    )
    """The organization of the action package."""

    version: str = field(
        metadata={
            "description": "The version of the action package.",
        },
    )
    """The version of the action package."""

    url: str | None = field(
        metadata={
            "description": "URL of the action server that hosts the action package.",
        },
        default=None,
    )
    """URL of the action server that hosts the action package."""

    api_key: SecretString | None = field(
        metadata={
            "description": "API Key of the action server that hosts the action package.",
        },
        default=None,
    )
    """API Key of the action server that hosts the action package."""

    allowed_actions: list[str] = field(
        metadata={
            "description": "Actions to enable in the action server that"
            " hosts the action package. An empty list"
            " implies all actions are enabled.",
        },
        default_factory=list,
    )
    """Actions to enable in the action server that hosts the action package.
    An empty list implies all actions are enabled."""

    whitelist: str = field(
        metadata={
            "description": "Comma separated list of actions to enable in"
            " the action server that hosts the action package. An empty"
            " string implies all actions are enabled. (LEGACY FIELD)",
        },
        default="",
    )
    """Comma separated list of actions to enable in the action server that
    hosts the action package. An empty string implies all actions are enabled.
    (LEGACY FIELD)"""

    def __post_init__(self):
        """Post-initialization hook."""
        if self.api_key is not None and isinstance(self.api_key, str):
            # Need to be careful setting in a frozen dataclass
            object.__setattr__(self, "api_key", SecretString(self.api_key))

        # LEGACY: anytime we have whitelist, upgrade it to allowed_actions
        # And set the whitelist to an empty string (eventually, we should
        # remove whitelist in favor of clients utilizing allowed_actions)
        if self.whitelist:
            # Don't know if legacy clients ever get funky with whitespace,
            # but let's not chance it.
            as_list = self.whitelist.strip().split(",")
            stripped_list = [item.strip() for item in as_list]
            # Remove empty strings
            filtered_list = [item for item in stripped_list if item]
            object.__setattr__(self, "allowed_actions", filtered_list)
            object.__setattr__(self, "whitelist", "")

    def copy(self) -> "ActionPackage":
        """Returns a deep copy of the action package."""
        return ActionPackage(
            name=self.name,
            organization=self.organization,
            version=self.version,
            url=self.url,
            api_key=(SecretString(self.api_key.get_secret_value()) if self.api_key is not None else None),
            # DO NOT copy legacy whitelist field, on post init
            # it was upgraded to allowed_actions
            allowed_actions=self.allowed_actions,
        )

    def model_dump(self) -> dict:
        """Serializes the action package to a dictionary.
        Useful for JSON serialization."""
        return {
            "name": self.name,
            "organization": self.organization,
            "version": self.version,
            "url": self.url,
            "api_key": (self.api_key.get_secret_value() if self.api_key is not None else None),
            # DO NOT copy legacy whitelist field, on post init
            # it was upgraded to allowed_actions
            "allowed_actions": self.allowed_actions,
        }

    async def to_tool_definitions(self, additional_headers: dict | None = None) -> list[ToolDefinition]:
        """Converts the action package to a list of tool definitions."""
        return await get_spec_and_build_tool_definitions(
            self.url or "",
            self.api_key.get_secret_value() if self.api_key is not None else "",
            self.allowed_actions,  # Use allowed_actions instead of whitelist here
            additional_headers,
        )

    @classmethod
    def model_validate(cls, data: dict) -> "ActionPackage":
        # 1. Work on a copy so we don't mutate the caller's object
        d = dict(data)

        # 2. Normalise api_key
        api = d.pop("api_key", None)
        if isinstance(api, str):
            d["api_key"] = SecretString(api)
        elif api is not None:
            d["api_key"] = api

        # 3. Handle legacy whitelist vs. allowed_actions
        if "allowed_actions" not in d:
            # keep whitelist if present; __post_init__ will upgrade it
            d.setdefault("whitelist", "")
        else:
            # ensure a list even if null/empty
            d["allowed_actions"] = d.get("allowed_actions") or []

        # 4. Fill in optional keys with defaults instead of raising
        d.setdefault("url", None)

        # 5. Drop any keys our dataclass doesn't accept
        valid_fields = {
            "name",
            "organization",
            "version",
            "url",
            "api_key",
            "allowed_actions",
            "whitelist",
        }
        cleaned = {k: v for k, v in d.items() if k in valid_fields}

        return cls(**cleaned)


# Classes for the action package details


@dataclass(frozen=True)
class ActionDetail:
    name: str


@dataclass(frozen=True)
class ActionPackageDetail:
    name: str
    actions: list[ActionDetail]
    version: str
    status: Literal["online", "offline"]

    # A message showing the reason for the status when offline
    status_details: str | None = None


@dataclass(frozen=True)
class AgentDetails:
    runbook: str
    action_packages: list[ActionPackageDetail]
    mcp_servers: list[MCPServerDetail]
