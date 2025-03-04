from dataclasses import dataclass, field
from typing import Literal

from agent_server_types_v2.prompts.messages import (
    PromptAgentMessage,
    PromptUserMessage,
)
from agent_server_types_v2.tools.tool_definition import ToolDefinition


@dataclass(frozen=True)
class Prompt:
    """Represents a complete prompt for an AI model interaction.

    This class encapsulates all components needed for an AI interaction, including
    the system instruction, temperature setting, and the conversation history.
    The conversation history must follow a strict user-agent interleaving pattern
    (starting with a user message, then alternating between groups of
    user and agent messages).
    """

    system_instruction: str = field(
        metadata={
            "description": (
                "Initial instruction that defines the AI's behavior and context"
            ),
        },
    )
    """Initial instruction that defines the AI's behavior and context"""

    messages: list[PromptUserMessage | PromptAgentMessage] = field(
        metadata={
            "description": (
                "Conversation history with strict user-agent interleaving "
                "(messages must alternate between groups of user and agent messages, "
                "starting with a user message)"
            ),
        },
    )
    """Conversation history with strict user-agent interleaving
    (messages must alternate between groups of user and agent messages,
    starting with a user message)"""

    tools: list[ToolDefinition] = field(
        default_factory=list,
        metadata={
            "description": (
                "Definitions of the tools provided to the model "
                "for use when generating responses"
            ),
        },
    )
    """Definitions of the tools provided to the model for use
    when generating responses"""

    tool_choice: Literal["auto", "any"] | str = field(
        default="auto",
        metadata={
            "description": (
                "The tool to use for the prompt; if not provided, "
                "the model will decide which tool to use. You may specificy 'auto', "
                "'any', or the name of a specific tool."
            ),
        },
    )
    """The tool to use for the prompt; if not provided, the model will
    decide which tool to use. You may specificy 'auto', 'any', or the name
    of a specific tool."""

    # TODO: add more useful documentation related to temperature, top_p, etc.
    # Maybe even a short doc somehwere on these concepts...

    temperature: float | None = field(
        default=None,
        metadata={
            "description": (
                "Sampling temperature for the model's responses "
                "(0.0 = deterministic, 1.0 = creative); if not provided, "
                "we'll default to 0.0 (unless sampling temperature is "
                "unsupported by the provider)"
            ),
        },
    )
    """Sampling temperature for the model's responses (0.0 = more deterministic,
    1.0 = more creative); if not provided, we'll default to 0.0 (unless sampling
    temperature is unsupported by the provider)"""

    seed: int | None = field(
        default=None,
        metadata={
            "description": (
                "Seed used in decoding. If not set, the request uses a randomly "
                "generated seed."
            ),
        },
    )
    """Seed used in decoding. If not set, the request uses a randomly generated seed."""

    max_output_tokens: int | None = field(
        default=None,
        metadata={
            "description": (
                "Maximum number of tokens to consider when sampling for this prompt."
            ),
        },
    )
    """Maximum number of tokens to consider when sampling for this prompt."""

    stop_sequences: list[str] | None = field(
        default=None,
        metadata={"description": "Stop sequences to use for this prompt."},
    )
    """Stop sequences to use for this prompt."""

    top_p: float | None = field(
        default=None,
        metadata={
            "description": (
                "The maximum cumulative probability of tokens to consider "
                "when sampling. Optional."
            ),
        },
    )
    """The maximum cumulative probability of tokens to consider
    when sampling. Optional."""

    # There are other common params like frequency_penalty, presence_penalty,
    # top_k or best_of, some APIs support a `candidate_count` or `n` param
    # (to sample multiple responses), etc. We can add them if/when needed.

    def __post_init__(self) -> None:
        """Validates the prompt structure after initialization.

        Ensures:
        1. Temperature is within valid range [0.0, 1.0].
        2. Messages sequence starts with a user message.

        Raises:
            ValueError: If temperature is out of range or first
                message is not from user.
        """
        # Validate temperature
        if self.temperature is not None:
            if not 0.0 <= self.temperature <= 1.0:
                raise ValueError(
                    f"Temperature must be between 0.0 and 1.0, got {self.temperature}",
                )

        # Validate message sequence starts with user
        if self.messages and not isinstance(self.messages[0], PromptUserMessage):
            raise ValueError("Message sequence must start with a user message")

        # Validate tool choice is valid
        if self.tool_choice not in ["auto", "any", *[tool.name for tool in self.tools]]:
            raise ValueError(
                f"Invalid tool choice: {self.tool_choice}. "
                f"Must be 'auto', 'any', or the name of a provided "
                f"tool.{' Available tools: ' + ', '.join(self.tools)}",
            )
