import json
from dataclasses import dataclass, field, fields
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import IO, TYPE_CHECKING, Any, Literal, TextIO, cast

from agent_platform.core.prompts.content.reasoning import PromptReasoningContent
from agent_platform.core.prompts.messages import (
    PromptAgentMessage,
    PromptMessage,
    PromptTextContent,
    PromptUserMessage,
)
from agent_platform.core.prompts.special import (
    ConversationHistorySpecialMessage,
    DocumentsSpecialMessage,
    MemoriesSpecialMessage,
    SpecialPromptMessage,
)
from agent_platform.core.tools.tool_definition import ToolDefinition

if TYPE_CHECKING:
    from agent_platform.core.kernel import Kernel
    from agent_platform.core.prompts.finalizers import BaseFinalizer


@dataclass
class Prompt:
    """Represents a complete prompt for an AI model interaction.

    This class encapsulates all components needed for an AI interaction, including
    the system instruction, temperature setting, and the conversation history.
    The conversation history must follow a strict user-agent interleaving pattern
    (starting with a user message, then alternating between groups of
    user and agent messages).
    """

    system_instruction: str | None = field(
        default=None,
        metadata={
            "description": ("Initial instruction that defines the AI's behavior and context"),
        },
    )
    """Initial instruction that defines the AI's behavior and context"""

    messages: list[
        PromptUserMessage
        | PromptAgentMessage
        | ConversationHistorySpecialMessage
        | DocumentsSpecialMessage
        | MemoriesSpecialMessage
    ] = field(
        default_factory=list,
        metadata={
            "description": (
                "Raw prompt messages, including special messages"
                "These will be converted to the proper message types "
                "when the prompt is formatted"
            ),
        },
    )
    """Raw prompt messages, including special messages
    (These will be converted to the proper message types
    when the prompt is formatted)"""

    tools: list[ToolDefinition] = field(
        default_factory=list,
        metadata={
            "description": ("Definitions of the tools provided to the model for use when generating responses"),
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
            "description": ("Seed used in decoding. If not set, the request uses a randomly generated seed."),
        },
    )
    """Seed used in decoding. If not set, the request uses a randomly generated seed."""

    max_output_tokens: int | None = field(
        default=None,
        metadata={
            "description": ("Maximum number of tokens to consider when sampling for this prompt."),
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
            "description": ("The maximum cumulative probability of tokens to consider when sampling. Optional."),
        },
    )
    """The maximum cumulative probability of tokens to consider
    when sampling. Optional."""

    minimize_reasoning: bool = field(
        default=False,
        metadata={
            "description": (
                "Whether to minimize reasoning in the prompt. This is useful when you want to "
                "speed up the response time of the model."
            ),
        },
    )
    """Whether to minimize reasoning in the prompt. This is useful when you want to
    speed up the response time of the model."""

    _finalized: bool = field(
        default=False,
        init=False,
        metadata={
            "description": (
                "Whether the prompt has been finalized. This is set to True after the prompt is finalized."
            ),
        },
    )
    """Whether the prompt has been finalized. This is set to True after
    the prompt is finalized."""

    # There are other common params like frequency_penalty, presence_penalty,
    # top_k or best_of, some APIs support a `candidate_count` or `n` param
    # (to sample multiple responses), etc. We can add them if/when needed.

    def __post_init__(self) -> None:
        """Validates the prompt structure after initialization.

        Ensures:
        1. Temperature is within valid range [0.0, 1.0].
        2. If messages is provided, it starts with a user message.
        3. Tool choice is valid.

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
                f"tool.{' Available tools: ' + ', '.join(tool.name for tool in self.tools)}",
            )

    def overwrite_last_content_with_text(self, text: str) -> None:
        """Overwrite the last content with the given text."""
        if not self.messages:
            raise ValueError("Prompt has no messages")

        if isinstance(self.messages[-1], PromptUserMessage):
            self.messages[-1] = PromptUserMessage(
                content=[
                    PromptTextContent(text=text),
                ],
            )
        else:
            self.messages[-1] = PromptAgentMessage(
                content=[
                    PromptTextContent(text=text),
                ],
            )

    async def finalize_messages(
        self,
        kernel: "Kernel | None" = None,
        prompt_finalizers: list["BaseFinalizer"] | None = None,
        finalizer_kwargs: dict["BaseFinalizer", dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> "Prompt":
        """Finalizes messages from the prompt.

        This method applies a chain of finalizers to the prompt's messages.
        The default chain includes:
        1. SpecialMessageFinalizer - hydrates special messages like
            ConversationHistorySpecialMessage
        2. TruncationFinalizer - ensures the prompt fits within model token limits

        Arguments:
            kernel: The kernel to use in hydrating special messages.
            prompt_finalizers: A list of finalizer functions to apply in sequence.
                Each finalizer takes a list of messages, the prompt, the kernel,
                and returns a list of messages. This allows for a chain of
                transformations like hydrating special messages followed by
                truncation.
            finalizer_kwargs: A dictionary mapping finalizer instances to their
                specific kwargs. This allows providing different parameters to
                different finalizers, e.g., {finalizer1: {"param1": value1}}.
            **kwargs: Additional arguments to pass to all finalizers, such as
                the platform and model information for token limit calculations.

        Returns:
            A Prompt with all special messages hydrated and any transformations
            applied by the finalizers.

        Example:
            ```python
            from agent_platform.core.prompts.finalizers import (
                SpecialMessageFinalizer,
                TruncationFinalizer,
            )

            # Create finalizers
            special_message_finalizer = SpecialMessageFinalizer()
            truncation_finalizer = TruncationFinalizer()

            # Use them in sequence when finalizing the prompt
            await prompt.finalize_messages(
                kernel=kernel,
                prompt_finalizers=[special_message_finalizer, truncation_finalizer],
                finalizer_kwargs={
                    special_message_finalizer: {"memory_limit": 5},
                    truncation_finalizer: {"token_budget_percentage": 0.7},
                },
                platform=platform,
                model="gpt-4",
            )
            ```
        """
        if self._finalized:
            return self

        # Process finalizers
        finalizers = []
        if prompt_finalizers is None:
            # If no finalizers are provided, use the default chain
            from agent_platform.core.prompts.finalizers import (
                SpecialMessageFinalizer,
                TruncationFinalizer,
            )

            finalizers = [
                SpecialMessageFinalizer(),
                TruncationFinalizer(),
            ]
        else:
            finalizers = list(prompt_finalizers)

        # Initialize finalizer_kwargs if not provided
        finalizer_kwargs = finalizer_kwargs or {}

        # Start with original messages
        new_messages = [message for message in self.messages if message.include]

        # Apply the chain of finalizers
        for finalizer in finalizers:
            # Get finalizer-specific kwargs if available
            specific_kwargs = finalizer_kwargs.get(finalizer, {})
            # Merge with global kwargs (global kwargs take precedence)
            merged_kwargs = {**specific_kwargs, **kwargs}

            # Call the finalizer with current messages (the type-checker doesn't
            # know that each finalizer handles its own message types).
            new_messages = await finalizer(new_messages, self, kernel, **merged_kwargs)  # type: ignore

        # Update the messages and finalized flag with properly typed messages
        # At this point we expect all special messages to have been processed
        # into regular message types
        final_messages = cast(
            list[
                PromptUserMessage
                | PromptAgentMessage
                | ConversationHistorySpecialMessage
                | DocumentsSpecialMessage
                | MemoriesSpecialMessage
            ],
            new_messages,
        )

        # Update the messages and finalized flag
        self.messages = final_messages
        self._finalized = True

        return self

    @property
    def finalized_messages(self) -> list[PromptUserMessage | PromptAgentMessage]:
        """The messages from the prompt after they have been finalized."""
        if not self._finalized:
            raise ValueError("Prompt has not been finalized")

        return [message for message in self.messages if isinstance(message, PromptUserMessage | PromptAgentMessage)]

    def extend_messages(
        self,
        messages: list[PromptUserMessage | PromptAgentMessage],
    ) -> None:
        """Extend the conversation history with new messages.

        Arguments:
            messages: List of messages to add to the conversation history.
        """
        if self._finalized:
            raise ValueError(
                "Cannot extend messages after the prompt has been finalized",
            )

        self.messages.extend(messages)

    def format_with_values(self, **kwargs: Any) -> "Prompt":
        """Format the prompt with the given values.

        Uses jinja2 to format the prompt.

        Arguments:
            **kwargs: The values to format the prompt with.

        Returns:
            Prompt: The formatted prompt.
        """
        import jinja2

        if self._finalized:
            raise ValueError("Cannot format a finalized prompt")

        if self.system_instruction:
            self.system_instruction = jinja2.Template(self.system_instruction).render(**kwargs)

        for message in self.messages:
            if message.include_expr:
                rendered_value = jinja2.Template(message.include_expr).render(**kwargs)
                message.include = rendered_value.strip().lower() == "true"

            if isinstance(message, SpecialPromptMessage):
                # For now, there's no formatting for special messages
                # maybe someday you could like set the number of turns to
                # include via your state using param substitution... but
                # not today
                continue

            for content in message.content:
                # TODO: other bits of content need formatting?
                if isinstance(content, PromptTextContent):
                    content.text = jinja2.Template(content.text).render(**kwargs)

        return self

    def with_tools(self, *tools: ToolDefinition) -> "Prompt":
        """Add tools to the prompt.

        Arguments:
            tools: The tools to add to the prompt.

        Returns:
            Prompt: The prompt with the tools added.
        """
        self.tools = list(tools)
        return self

    def with_minimized_reasoning(self) -> "Prompt":
        """Minimize reasoning in the prompt.

        This is useful when you want to speed up the response time of the model.
        """
        self.minimize_reasoning = True
        return self

    def to_pretty_yaml(self, width: int = 100, include: list[str] | None = None) -> str:
        """Convert the prompt to a pretty YAML string.

        Args:
            width: Maximum line width for formatting
            include: Optional list of field names to include. If None, includes all fields.
                    Examples: ["messages"], ["system_instruction", "messages"]
        """
        from agent_platform.core.prompts.debug import to_pretty_yaml

        return to_pretty_yaml(self, width, include)

    def count_tokens_approx(self) -> int:
        """Approximate the number of tokens in the prompt.

        This method uses each content type's own token counting method and adds
        tokens for the system instructions and any tools provided to the model.
        """
        # Start w/ a small fudge factor
        token_count = 100

        # Count system instruction if present
        if self.system_instruction:
            # Count tokens for the system instruction text
            token_count += PromptTextContent.count_tokens_in_text(self.system_instruction)

        # Count messages (skipping special messages)
        index_of_latest_user_message = -1
        for i, msg in enumerate(self.messages):
            if isinstance(msg, PromptUserMessage):
                index_of_latest_user_message = i

        for i, msg in enumerate(self.messages):
            if isinstance(msg, PromptUserMessage | PromptAgentMessage):
                token_count += 30  # Role indicators/other small overhead per message
                # Count tokens in each content item
                for content in msg.content:
                    # TODO: when we get to Claude 4 thinking and thinking in Gemini 2.5,
                    # make sure it's aligned with this logic (and if not, adjust). It doesn't
                    # really make sense to ever keep the "reasoning scratchpad" generated in
                    # response to anything but the most recent user message, but we should
                    # just confirm as we add more reasoner models.
                    skip_reasoning = (
                        index_of_latest_user_message == -1 or i < index_of_latest_user_message
                    ) and isinstance(content, PromptReasoningContent)
                    if skip_reasoning:
                        # Do _not_ count reasoning content before the latest user message
                        # if it will be ignored.
                        continue
                    # Use the content's own token counting method
                    token_count += content.count_tokens_approx()

        # Count tools
        if self.tools:
            token_count += 20 * len(self.tools)  # Small fudge factor for tools
            for tool in self.tools:
                token_count += PromptTextContent.count_tokens_in_text(
                    f"Tool: {tool.name}\n"
                    f"Description: {tool.description}\n"
                    f"Parameters: {json.dumps(tool.input_schema, indent=2)}"
                )

        return token_count

    @classmethod
    def model_validate(cls, data: dict) -> "Prompt":
        """Validate and convert a dictionary into a Prompt instance."""
        data = data.copy()

        raw_messages = data.pop("messages", [])
        messages = []
        for message in raw_messages:
            # We can have special messages, which aren't yet "finalized"
            # into regular PromptUserMessage or PromptAgentMessage types
            if message.get("role", "").startswith("$"):
                messages.append(SpecialPromptMessage.model_validate(message))
            else:
                # Or we can have regular messages, which are already in the
                # proper PromptUserMessage or PromptAgentMessage types
                messages.append(PromptMessage.model_validate(message))

        raw_tools = data.pop("tools", [])
        tools = []
        for tool in raw_tools:
            tools.append(ToolDefinition.model_validate(tool))

        data["messages"] = messages
        data["tools"] = tools

        return cls(**data)

    @classmethod
    def load_yaml(
        cls,
        path_or_file: str | IO[str] | Path | TextIO | Traversable,
    ) -> "Prompt":
        """Load a prompt from a YAML file.

        Arguments:
            path: Path to the YAML file.

        Returns:
            Prompt: The loaded prompt.
        """
        from ruamel.yaml import YAML, YAMLError

        yaml = YAML()

        # Load the YAML file
        data = None
        try:
            if isinstance(path_or_file, str | Path):
                with open(path_or_file, encoding="utf-8") as file:
                    data = yaml.load(file)
            elif isinstance(path_or_file, Traversable):
                data = yaml.load(path_or_file.read_text(encoding="utf-8"))
            else:  # file-like object (TextIO)
                data = yaml.load(path_or_file)
        except FileNotFoundError as e:
            raise FileNotFoundError(f"Prompt file not found: {path_or_file}") from e
        except YAMLError as e:
            raise YAMLError(f"Error loading YAML file: {path_or_file}") from e

        # Make sure we got some data and it's a dict
        if not data or not isinstance(data, dict):
            raise ValueError(f"Invalid prompt file: {path_or_file}")

        # Get the field names of the Prompt class
        prompt_fields = {f.name for f in fields(cls)}

        # Filter the loaded YAML data to only include valid Prompt fields
        filtered_data = {key: value for key, value in data.items() if key in prompt_fields}

        return cls.model_validate(filtered_data)
