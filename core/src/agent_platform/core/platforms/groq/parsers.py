from collections.abc import AsyncGenerator
from logging import getLogger
from typing import TYPE_CHECKING, Any

from agent_platform.core.delta import GenericDelta
from agent_platform.core.delta.compute_delta import compute_generic_deltas
from agent_platform.core.platforms.base import PlatformParsers
from agent_platform.core.responses.content.audio import ResponseAudioContent
from agent_platform.core.responses.content.base import ResponseMessageContent
from agent_platform.core.responses.content.image import (
    ResponseImageContent,
)
from agent_platform.core.responses.content.text import ResponseTextContent
from agent_platform.core.responses.content.tool_use import ResponseToolUseContent
from agent_platform.core.responses.response import ResponseMessage, TokenUsage

if TYPE_CHECKING:
    from groq.types.chat import (
        ChatCompletion,
        ChatCompletionChunk,
        ChatCompletionMessageToolCall,
    )
    from groq.types.chat.chat_completion_chunk import Choice, ChoiceDeltaToolCall

logger = getLogger(__name__)


class GroqParsers(PlatformParsers):
    """Parsers that transform Groq types to agent-server prompt types."""

    def parse_text_content(self, content: str) -> ResponseTextContent:
        """Parses a platform-specific text content to an agent-server
        text content.

        Args:
            content: The content to parse.

        Returns:
            The parsed text content.
        """
        return ResponseTextContent(text=content)

    def parse_image_content(self, content: Any) -> ResponseImageContent:
        """Parses a platform-specific image content to an agent-server
        image content.

        Args:
            content: The content to parse.

        Returns:
            The parsed image content.
        """
        raise NotImplementedError("Image content not supported yet")

    def parse_audio_content(self, content: Any) -> ResponseAudioContent:
        """Parses a platform-specific audio content to an agent-server
        audio content.

        Args:
            content: The content to parse.

        Returns:
            The parsed audio content.
        """
        raise NotImplementedError("Audio content not supported yet")

    def parse_tool_use_content(
        self,
        content: "ChatCompletionMessageToolCall",
    ) -> ResponseToolUseContent:
        """Parses a platform-specific tool use content to an agent-server
        tool use content.

        Args:
            content: The content to parse.

        Returns:
            The parsed tool use content.
        """
        from json import dumps

        # UNIQUE SCENARIO (encountered during further testing)
        # The reasoning models are producing weird tool call JSON
        # occasionally, I've seen a { function_name: { args... } }
        # which, of course, breaks...
        # It's unclear if we should handle this here... as you could
        # have a function named foo with an argument named foo...
        as_tool_use = ResponseToolUseContent(
            tool_call_id=content.id,
            tool_name=content.function.name,
            tool_input_raw=content.function.arguments,
        )

        if as_tool_use.tool_name in as_tool_use.tool_input:
            logger.warning(
                "Tool name found in tool input: %s",
                as_tool_use.tool_name,
            )
            # If this is the _only_ key and it's a dict, we'll
            # "un-nest" the tool input
            all_keys = list(as_tool_use.tool_input.keys())
            if len(all_keys) == 1:
                content_at_name = as_tool_use.tool_input[all_keys[0]]
                if isinstance(content_at_name, dict):
                    logger.warning(
                        "Un-nesting tool input: %s",
                        content_at_name,
                    )
                    return ResponseToolUseContent(
                        tool_call_id=as_tool_use.tool_call_id,
                        tool_name=as_tool_use.tool_name,
                        tool_input_raw=dumps(content_at_name),
                    )

        return as_tool_use

    def parse_response(self, response: "ChatCompletion") -> ResponseMessage:
        """Parses an Groq response to an agent-server response.

        Args:
            response: The Groq response to parse.

        Returns:
            A ResponseMessage containing the parsed content and raw response.

        Raises:
            ValueError: If the response format is invalid or missing required fields.
        """
        response_messages = []

        for choice in response.choices:
            response_content = []

            # Handle text content if present
            if choice.message.content:
                response_content.append(self.parse_text_content(choice.message.content))

            # Handle tool calls if present
            if choice.message.tool_calls:
                for tool_call in choice.message.tool_calls:
                    response_content.append(self.parse_tool_use_content(tool_call))

            # Extract usage metrics
            token_usage = self._extract_token_usage(response)

            # Create the response message
            msg = ResponseMessage(
                role="agent",
                content=response_content,
                usage=token_usage,
                raw_response=response,
            )
            response_messages.append(msg)

        if len(response_messages) == 0:
            raise ValueError("No response messages found in Groq response")

        return response_messages[0]

    def _process_response_tool_calls(
        self,
        tool_calls: list["ChatCompletionMessageToolCall"],
        response_content: list[ResponseMessageContent],
    ) -> None:
        """Processes tool calls from a response."""
        for tool_call in tool_calls:
            response_content.append(
                ResponseToolUseContent(
                    tool_call_id=tool_call.id,
                    tool_name=tool_call.function.name,
                    tool_input_raw=tool_call.function.arguments,
                ),
            )

    def _extract_token_usage(self, response: "ChatCompletion") -> TokenUsage:
        """Extracts token usage from a response."""
        return TokenUsage(
            input_tokens=response.usage.prompt_tokens if response.usage else 0,
            output_tokens=response.usage.completion_tokens if response.usage else 0,
            total_tokens=response.usage.total_tokens if response.usage else 0,
        )

    async def parse_stream_event(
        self,
        event: "ChatCompletionChunk",
        message: dict[str, Any],
        last_message: dict[str, Any],
    ) -> AsyncGenerator[GenericDelta, None]:
        """Parses a single stream event from Groq into GenericDeltas."""
        # Initialize key parts of the message if they don't exist
        self._ensure_message_structure(message)

        # Process the event
        if len(event.choices) > 0:
            choice = event.choices[0]
            self._process_delta_content(choice, message)
            self._process_tool_calls(choice, message)
            message["stop_reason"] = choice.finish_reason

        # Process metadata
        self._process_event_metadata(event, message)

        # Calculate and yield deltas
        deltas = compute_generic_deltas(last_message, message)
        for delta in deltas:
            yield delta

    def _ensure_message_structure(self, message: dict[str, Any]) -> None:
        """Ensures the message has all required fields."""
        if "role" not in message:
            message["role"] = "agent"

        if "content" not in message:
            message["content"] = []

        # Collect values that don't directly map to ResponseMessage fields
        if "additional_response_fields" not in message:
            message["additional_response_fields"] = {}

    def _process_delta_content(self, choice: "Choice", message: dict[str, Any]) -> None:
        """Processes text content from the delta."""
        if choice.delta.content:
            # Find or create text content
            text_found = False
            for i, item in enumerate(message["content"]):
                if item.get("kind") == "text":
                    message["content"][i]["text"] += choice.delta.content
                    text_found = True
                    break

            if not text_found:
                message["content"].append(
                    {"kind": "text", "text": choice.delta.content},
                )

    def _process_tool_calls(self, choice: "Choice", message: dict[str, Any]) -> None:
        """Processes tool calls from the delta or message."""
        # Process tool calls in delta
        if choice.delta.tool_calls:
            self._process_delta_tool_calls(choice.delta.tool_calls, message)

    def _process_delta_tool_calls(
        self,
        tool_calls: list["ChoiceDeltaToolCall"],
        message: dict[str, Any],
    ) -> None:
        """Processes tool calls from a delta object."""
        tool_indices = []
        for i, item in enumerate(message["content"]):
            if item.get("kind") != "tool_use":
                continue
            tool_indices.append(i)

        for tool_call in tool_calls:
            tool_name = tool_call.function.name if tool_call.function else ""
            tool_input_raw = tool_call.function.arguments if tool_call.function else ""

            if tool_call.index >= len(tool_indices):
                message["content"].append(
                    {
                        "kind": "tool_use",
                        "tool_call_id": tool_call.id,
                        "tool_name": tool_name or "",
                        "tool_input_raw": tool_input_raw or "",
                    }
                )
            else:
                matching_tool_idx = tool_indices[tool_call.index]
                if tool_call.function:
                    message["content"][matching_tool_idx]["tool_name"] += tool_name or ""
                    message["content"][matching_tool_idx]["tool_input_raw"] += tool_input_raw or ""

    def _process_event_metadata(
        self,
        event: "ChatCompletionChunk",
        message: dict[str, Any],
    ) -> None:
        """Processes metadata from the event."""
        message["additional_response_fields"]["id"] = event.id
        message["additional_response_fields"]["model"] = event.model

        if event.usage:
            message["usage"] = {
                "input_tokens": event.usage.prompt_tokens,
                "output_tokens": event.usage.completion_tokens,
                "total_tokens": event.usage.total_tokens,
            }
