import json
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Literal

from agent_platform.core.responses.content.tool_use import ResponseToolUseContent
from agent_platform.core.thread.content.base import ThreadMessageContent

if TYPE_CHECKING:
    from agent_platform.core.tools.tool_definition import ToolDefinition


@dataclass
class ThreadToolUsageContent(ThreadMessageContent):
    """Represents a tool usage in the thread.

    This class handles tool usage: both the call, status, results, and possibly
    error associated with the tool call.
    """

    name: str = field(metadata={"description": "The name of the tool to call"})
    """The name of the tool to call"""

    tool_call_id: str = field(metadata={"description": "The ID of the tool call"})
    """The ID of the tool call"""

    arguments_raw: str = field(
        metadata={"description": "The raw arguments (JSON string) passed to the tool"},
    )
    """The raw arguments (JSON string) passed to the tool"""

    sub_type: Literal[
        "kernel-internal",
        "aa-internal",
        "action-external",
        "mcp-external",
        "provider-side",
        "client-side",
        "unknown",
    ] = field(
        default="unknown",
        metadata={"description": "The sub-type of the tool call, if it has one"},
    )
    """The sub-type of the tool call, if it has one"""

    status: Literal["running", "finished", "failed", "pending", "streaming"] = field(
        default="pending",
        metadata={
            "description": "The status of the tool call, either 'running', "
            "'finished', 'failed', 'pending', or 'streaming'",
        },
    )
    """The status of the tool call, either 'running', 'finished', 'failed',
    'pending', or 'streaming'
    """

    result: str | None = field(
        default=None,
        metadata={"description": "The result of the tool call, if it has finished"},
    )
    """The result of the tool call, if it has finished"""

    error: str | None = field(
        default=None,
        metadata={
            "description": "The error message of the tool call, if it has failed",
        },
    )
    """The error message of the tool call, if it has failed"""

    discovered_at: datetime | None = field(
        default=None,
        metadata={
            "description": "The timestamp when the tool call was discovered in stream or response",
        },
    )
    """The timestamp when the tool call was discovered in stream or response"""

    pending_at: datetime | None = field(
        default=None,
        metadata={
            "description": "The timestamp when the tool call was pending (fully formed, not yet executed)",
        },
    )
    """The timestamp when the tool call was pending (fully formed, not yet executed)"""

    started_at: datetime | None = field(
        default=None,
        metadata={"description": "The timestamp when the tool call started"},
    )
    """The timestamp when the tool call started"""

    ended_at: datetime | None = field(
        default=None,
        metadata={"description": "The timestamp when the tool call ended"},
    )
    """The timestamp when the tool call ended"""

    action_server_run_id: str | None = field(
        default=None,
        metadata={"description": "The run ID from the action server"},
    )
    """The run ID from the action server"""

    metadata: dict[str, Any] = field(
        default_factory=dict,
        metadata={"description": "The metadata of the tool call"},
    )
    """The metadata of the tool call"""

    kind: str = field(
        default="tool_call",
        metadata={"description": "Content kind: always 'tool_call'"},
        init=False,
    )
    """Content kind: always 'tool_call'"""

    def __post_init__(self) -> None:
        """Validates the content type and text content after initialization.

        Raises:
            AssertionError: If the type field doesn't match the literal "text".
            ValueError: If the tool_name field is empty.
        """
        assert self.kind == "tool_call"

        if not self.name:
            raise ValueError("Tool name cannot be empty")

    def as_text_content(self) -> str:
        """Converts the text content to a text content component."""
        as_markdown = f"Tool call: {self.name} ({self.tool_call_id})"
        if self.status == "finished":
            as_markdown += f"\nResult: {self.result}"
        elif self.status == "failed":
            as_markdown += f"\nError: {self.error}"
        return as_markdown

    def model_dump(self) -> dict:
        """Serializes the tool usage content to a dictionary. Useful
        for JSON serialization.
        """
        return {
            **super().model_dump(),
            "name": self.name,
            "tool_call_id": self.tool_call_id,
            "arguments_raw": self.arguments_raw,
            "sub_type": self.sub_type,
            "status": self.status,
            "result": self.result,
            "error": self.error,
            # TODO: This is a hack to get around the fact that the started_at and
            # ended_at fields are sometimes not datetime objects. Need to fix this
            "started_at": (self.started_at.isoformat() if isinstance(self.started_at, datetime) else None),
            "ended_at": (self.ended_at.isoformat() if isinstance(self.ended_at, datetime) else None),
            "action_server_run_id": self.action_server_run_id,
            "metadata": deepcopy(self.metadata),
        }

    def model_dump_json(self) -> str:
        """Serializes the tool usage content to a JSON string."""
        return json.dumps(self.model_dump())

    @classmethod
    def model_validate(cls, data: dict) -> "ThreadToolUsageContent":
        """Create a thread tool usage content from a dictionary."""
        data = data.copy()
        if "started_at" in data and isinstance(data["started_at"], str):
            data["started_at"] = datetime.fromisoformat(data["started_at"])
        if "ended_at" in data and isinstance(data["ended_at"], str):
            data["ended_at"] = datetime.fromisoformat(data["ended_at"])
        return cls(**data)

    @classmethod
    def from_response_tool_use(
        cls,
        response_tool_use: ResponseToolUseContent,
        metadata: dict[str, Any] | None = None,
        tool_def: "ToolDefinition | None" = None,
    ) -> "ThreadToolUsageContent":
        """Create a thread tool usage content from a response tool use content."""
        from agent_platform.core.kernel_interfaces.thread_state import (
            _get_sub_type_from_tool_category,
        )

        return cls(
            name=response_tool_use.tool_name,
            tool_call_id=response_tool_use.tool_call_id,
            arguments_raw=response_tool_use.tool_input_raw,
            sub_type=_get_sub_type_from_tool_category(tool_def),
            metadata=metadata or {},
        )


ThreadMessageContent.register_content_kind("tool_call", ThreadToolUsageContent)
