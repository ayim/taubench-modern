from dataclasses import dataclass, field

from agent_server_types_v2.prompts.messages import PromptAgentMessage


@dataclass(frozen=True)
class ModelResponse:
    """Represents the response from a model."""

    messages: list[PromptAgentMessage] = field(metadata={"description": "The response messages from the model"})
    """The response messages from the model"""

    # TODO: usage data? safety filter blocks? etc?