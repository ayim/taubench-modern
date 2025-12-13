from dataclasses import dataclass, field
from typing import Any

from agent_platform.core.payloads.initiate_stream import ToolDefinitionPayload
from agent_platform.core.payloads.upsert_agent import UpsertAgentPayload
from agent_platform.core.thread.base import ThreadMessage


@dataclass
class EphemeralStreamPayload:
    """Payload for ephemeral agent runs."""

    agent: UpsertAgentPayload
    name: str | None = None
    messages: list[ThreadMessage] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    client_tools: list[ToolDefinitionPayload] = field(default_factory=list)
    override_model_id: str | None = field(default=None)

    @classmethod
    def model_validate(cls, data: Any) -> "EphemeralStreamPayload":
        # Use UpsertAgentPayload's model_validate to handle nested object conversion
        agent_data = data["agent"]

        return EphemeralStreamPayload(
            agent=UpsertAgentPayload.model_validate(agent_data),
            name=data.get("name"),
            messages=[ThreadMessage.model_validate(m) for m in data.get("messages", [])],
            metadata=data.get("metadata", {}),
            client_tools=[ToolDefinitionPayload.model_validate(t) for t in data.get("client_tools", [])],
            override_model_id=data.get("override_model_id", None),
        )
