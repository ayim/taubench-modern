from collections.abc import AsyncGenerator
from typing import Any

from agent_platform.core.delta import GenericDelta
from agent_platform.core.delta.compute_delta import compute_generic_deltas
from agent_platform.core.platforms.base import PlatformParsers
from agent_platform.core.responses.content.audio import ResponseAudioContent
from agent_platform.core.responses.content.base import ResponseMessageContent
from agent_platform.core.responses.content.document import (
    ResponseDocumentContent,
)
from agent_platform.core.responses.content.image import (
    ResponseImageContent,
)
from agent_platform.core.responses.content.text import ResponseTextContent
from agent_platform.core.responses.content.tool_use import ResponseToolUseContent
from agent_platform.core.responses.response import ResponseMessage, TokenUsage


class OpenAIParsers(PlatformParsers):
    """Parsers that transform OpenAI types to agent-server prompt types."""

    def parse_text_content(self, content: Any) -> ResponseTextContent:
        """Parses a platform-specific text content to an agent-server
        text content.

        Args:
            content: The content to parse.

        Returns:
            The parsed text content.
        """
        if isinstance(content, str):
            return ResponseTextContent(text=content)
        elif isinstance(content, bytes):
            return ResponseTextContent(text=content.decode("utf-8"))
        elif isinstance(content, dict) and "text" in content:
            return ResponseTextContent(text=content["text"])
        raise ValueError(f"Invalid text content format: {content}")

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

    def parse_tool_use_content(self, content: Any) -> ResponseToolUseContent:
        """Parses a platform-specific tool use content to an agent-server
        tool use content.

        Args:
            content: The content to parse.

        Returns:
            The parsed tool use content.
        """
        if not isinstance(content, dict):
            raise ValueError(f"Invalid tool use content format: {content}")

        tool_use_id = content.get("id")
        if not tool_use_id:
            raise ValueError("tool_use_id is required")

        tool_name = content.get("function", {}).get("name")
        if not tool_name:
            raise ValueError("tool_name is required")

        tool_input = content.get("function", {}).get("arguments")
        if not tool_input:
            raise ValueError("tool_input is required")

        return ResponseToolUseContent(
            tool_call_id=tool_use_id,
            tool_name=tool_name,
            tool_input_raw=tool_input,
        )

    def parse_document_content(self, content: Any) -> ResponseDocumentContent:
        """Parses a platform-specific document content to an agent-server
        document content.

        Args:
            content: The content to parse.

        Returns:
            The parsed document content.
        """
        raise NotImplementedError("Document content not supported yet")

    def parse_content_item(self, content: Any) -> ResponseMessageContent:
        """Parses a platform-specific content item to an agent-server
        content item.

        Args:
            content: The content to parse.

        Returns:
            The parsed content item.
        """
        if not isinstance(content, dict) or "type" not in content:
            raise ValueError(f"Invalid content item format: {content}")

        if content["type"] == "text":
            return self.parse_text_content(content["text"])
        elif content["type"] == "image":
            return self.parse_image_content(content["image"])
        elif content["type"] == "audio":
            return self.parse_audio_content(content["audio"])
        elif content["type"] == "function":  # OpenAI uses "function" for tool use
            return self.parse_tool_use_content(content)

        raise ValueError(f"Unsupported content type in item: {content}")

    def parse_response(self, response: Any) -> ResponseMessage:
        """Parses an OpenAI response to an agent-server response.

        Args:
            response: The OpenAI response to parse.

        Returns:
            A ResponseMessage containing the parsed content and raw response.

        Raises:
            ValueError: If the response format is invalid or missing required fields.
        """
        response_messages = []
        choices = self._extract_choices(response)

        for choice in choices:
            message = self._extract_message(choice)
            if not message:
                continue

            response_content = []
            content, tool_calls = self._extract_content_and_tool_calls(message)

            # Handle text content if present
            if content:
                response_content.append(ResponseTextContent(text=content))

            # Handle tool calls if present
            if tool_calls:
                self._process_response_tool_calls(tool_calls, response_content)

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
            raise ValueError("No response messages found in OpenAI response")

        return response_messages[0]

    def _extract_choices(self, response: Any) -> list[Any]:
        """Extracts choices from the response."""
        if isinstance(response, dict):
            return response.get("choices", [])
        # Handle OpenAI ChatCompletion object
        return response.choices if hasattr(response, "choices") else []

    def _extract_message(self, choice: Any) -> Any:
        """Extracts message from a choice."""
        if isinstance(choice, dict):
            return choice.get("message")
        # Handle OpenAI Choice object
        return choice.message if hasattr(choice, "message") else None

    def _extract_content_and_tool_calls(
        self,
        message: Any,
    ) -> tuple[str | None, list[Any]]:
        """Extracts content and tool calls from a message."""
        if isinstance(message, dict):
            content = message.get("content")
            tool_calls = message.get("tool_calls", [])
        else:
            # Handle OpenAI Message object
            content = message.content if hasattr(message, "content") else None
            tool_calls = message.tool_calls if hasattr(message, "tool_calls") else []

        return content, tool_calls

    def _process_response_tool_calls(
        self,
        tool_calls: list[Any],
        response_content: list[ResponseMessageContent],
    ) -> None:
        """Processes tool calls from a response."""
        for tool_call in tool_calls:
            tool_id, name, arguments = self._extract_tool_call_data(tool_call)

            # Make sure tool_id is a string
            tool_id_str = str(tool_id) if tool_id is not None else ""
            response_content.append(
                ResponseToolUseContent(
                    tool_call_id=tool_id_str,
                    tool_name=name,
                    tool_input_raw=arguments,
                ),
            )

    def _extract_tool_call_data(self, tool_call: Any) -> tuple[Any, str, str]:
        """Extracts data from a tool call."""
        if isinstance(tool_call, dict):
            tool_id = tool_call.get("id")
            function = tool_call.get("function", {})
            name = function.get("name", "")
            arguments = function.get("arguments", "{}")
        else:
            # Handle OpenAI ToolCall object
            tool_id = tool_call.id if hasattr(tool_call, "id") else None
            function = tool_call.function if hasattr(tool_call, "function") else None
            if function is not None:
                name = function.name if hasattr(function, "name") else ""
                arguments = (
                    function.arguments if hasattr(function, "arguments") else "{}"
                )
            else:
                name = ""
                arguments = "{}"

        return tool_id, name, arguments

    def _extract_token_usage(self, response: Any) -> TokenUsage:
        """Extracts token usage from a response."""
        if isinstance(response, dict):
            usage = response.get("usage", {})
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)
            total_tokens = usage.get("total_tokens", 0)
        else:
            # Handle OpenAI Usage object
            usage = response.usage if hasattr(response, "usage") else None
            if usage is None:
                input_tokens = 0
                output_tokens = 0
                total_tokens = 0
            else:
                input_tokens = (
                    usage.prompt_tokens if hasattr(usage, "prompt_tokens") else 0
                )
                output_tokens = (
                    usage.completion_tokens
                    if hasattr(usage, "completion_tokens")
                    else 0
                )
                total_tokens = (
                    usage.total_tokens if hasattr(usage, "total_tokens") else 0
                )

        return TokenUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
        )

    async def parse_stream_event(
        self,
        event: Any,
        message: dict[str, Any],
        last_message: dict[str, Any],
    ) -> AsyncGenerator[GenericDelta, None]:
        """Parses a single stream event from OpenAI into GenericDeltas."""
        # Initialize key parts of the message if they don't exist
        self._ensure_message_structure(message)

        # Process the event
        if hasattr(event, "choices") and event.choices:
            choice = event.choices[0]
            self._process_delta_content(choice, message)
            self._process_tool_calls(choice, message)
            self._process_finish_reason(choice, message)

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

    def _process_delta_content(self, choice: Any, message: dict[str, Any]) -> None:
        """Processes text content from the delta."""
        if (
            hasattr(choice, "delta")
            and hasattr(choice.delta, "content")
            and choice.delta.content
        ):
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

    def _process_tool_calls(self, choice: Any, message: dict[str, Any]) -> None:
        """Processes tool calls from the delta or message."""
        # Process tool calls in delta
        if (
            hasattr(choice, "delta")
            and hasattr(choice.delta, "tool_calls")
            and choice.delta.tool_calls
        ):
            self._process_delta_tool_calls(choice.delta.tool_calls, message)

        # Process tool calls in complete message (some API versions)
        if hasattr(choice, "message") and hasattr(choice.message, "tool_calls"):
            self._process_message_tool_calls(choice.message.tool_calls, message)

    def _process_delta_tool_calls(
        self,
        tool_calls: list[Any],
        message: dict[str, Any],
    ) -> None:
        """Processes tool calls from a delta object."""
        for tool_call in tool_calls:
            # Handle tool call with ID
            tool_id = (
                tool_call.id if hasattr(tool_call, "id") and tool_call.id else None
            )

            if tool_id:
                self._process_tool_call_with_id(tool_call, tool_id, message)
            # Handle tool call without ID (function details only)
            elif hasattr(tool_call, "function") and (
                hasattr(tool_call.function, "name")
                or hasattr(tool_call.function, "arguments")
            ):
                self._process_tool_call_without_id(tool_call, message)

    def _process_tool_call_with_id(
        self,
        tool_call: Any,
        tool_id: str,
        message: dict[str, Any],
    ) -> None:
        """Processes a tool call that has an ID."""
        # Look for an existing tool use content with this ID
        tool_found = False
        for i, item in enumerate(message["content"]):
            if item.get("kind") == "tool_use" and item.get("tool_call_id") == tool_id:
                tool_found = True
                # Update tool use content
                if hasattr(tool_call, "function"):
                    self._update_existing_tool_function(
                        tool_call.function,
                        message["content"][i],
                    )
                break

        if not tool_found:
            # Create a new tool use content
            tool_content = {
                "kind": "tool_use",
                "tool_call_id": tool_id,
                "tool_name": "",
                "tool_input_raw": "",
            }

            # Add initial data if available
            if hasattr(tool_call, "function"):
                self._update_existing_tool_function(
                    tool_call.function,
                    tool_content,
                )

            message["content"].append(tool_content)

    def _update_existing_tool_function(
        self,
        function: Any,
        tool_content: dict[str, Any],
    ) -> None:
        """Updates tool content with function data."""
        if hasattr(function, "name") and function.name:
            tool_content["tool_name"] = function.name

        if hasattr(function, "arguments") and function.arguments:
            # Initialize if not present
            if "tool_input_raw" not in tool_content:
                tool_content["tool_input_raw"] = ""

            # Accumulate arguments
            tool_content["tool_input_raw"] += function.arguments

    def _process_tool_call_without_id(
        self,
        tool_call: Any,
        message: dict[str, Any],
    ) -> None:
        """Processes a tool call that has no ID but has function details."""
        # Find any existing tool use content to update
        found = False
        for i, item in enumerate(message["content"]):
            if item.get("kind") == "tool_use":
                if hasattr(tool_call.function, "name") and tool_call.function.name:
                    message["content"][i]["tool_name"] = tool_call.function.name

                if (
                    hasattr(tool_call.function, "arguments")
                    and tool_call.function.arguments
                ):
                    if "tool_input_raw" not in message["content"][i]:
                        message["content"][i]["tool_input_raw"] = ""
                    message["content"][i]["tool_input_raw"] += (
                        tool_call.function.arguments
                    )
                found = True
                break

        # If no tool use content exists, create one with a placeholder ID
        if (
            not found
            and hasattr(tool_call.function, "arguments")
            and tool_call.function.arguments
        ):
            tool_name = ""
            if hasattr(tool_call.function, "name") and tool_call.function.name:
                tool_name = tool_call.function.name

            # Create with a placeholder ID if none exists
            tool_content = {
                "kind": "tool_use",
                "tool_call_id": "call_default",
                "tool_name": tool_name,
                "tool_input_raw": tool_call.function.arguments,
            }
            message["content"].append(tool_content)

    def _process_message_tool_calls(
        self,
        tool_calls: list[Any],
        message: dict[str, Any],
    ) -> None:
        """Processes tool calls from a complete message object."""
        for tool_call in tool_calls:
            if hasattr(tool_call, "id") and hasattr(tool_call, "function"):
                tool_found = False
                for i, item in enumerate(message["content"]):
                    if (
                        item.get("kind") == "tool_use"
                        and item.get("tool_call_id") == tool_call.id
                    ):
                        tool_found = True
                        # Update with complete data
                        message["content"][i]["tool_name"] = tool_call.function.name
                        message["content"][i]["tool_input_raw"] = (
                            tool_call.function.arguments
                        )
                        break

                if not tool_found:
                    # Create new with complete data
                    tool_content = {
                        "kind": "tool_use",
                        "tool_call_id": tool_call.id,
                        "tool_name": tool_call.function.name,
                        "tool_input_raw": tool_call.function.arguments,
                    }
                    message["content"].append(tool_content)

    def _process_finish_reason(self, choice: Any, message: dict[str, Any]) -> None:
        """Processes the finish reason from the event."""
        if hasattr(choice, "finish_reason") and choice.finish_reason:
            message["stop_reason"] = choice.finish_reason

            # If we're done with a tool call, double check the content
            if choice.finish_reason == "tool_calls":
                self._ensure_tool_calls_complete(choice, message)

    def _ensure_tool_calls_complete(self, choice: Any, message: dict[str, Any]) -> None:
        """Ensures tool calls have complete information."""
        # Check if we have any tool use without arguments
        for i, item in enumerate(message["content"]):
            if item.get("kind") == "tool_use" and not item.get("tool_input_raw"):
                # If we're missing arguments but have an ID, try to find them
                if hasattr(choice, "message") and hasattr(choice.message, "tool_calls"):
                    for tc in choice.message.tool_calls:
                        if tc.id == item.get("tool_call_id") and hasattr(
                            tc.function,
                            "arguments",
                        ):
                            message["content"][i]["tool_input_raw"] = (
                                tc.function.arguments
                            )

    def _process_event_metadata(self, event: Any, message: dict[str, Any]) -> None:
        """Processes metadata from the event."""
        if hasattr(event, "id"):
            message["additional_response_fields"]["id"] = event.id

        if hasattr(event, "model"):
            message["additional_response_fields"]["model"] = event.model

        if hasattr(event, "usage") and event.usage:
            message["usage"] = {
                "input_tokens": getattr(event.usage, "prompt_tokens", 0),
                "output_tokens": getattr(event.usage, "completion_tokens", 0),
                "total_tokens": getattr(event.usage, "total_tokens", 0),
            }

    def _handle_delta_content_list(self, event: dict, message: dict) -> None:
        """Handle a delta content list event.

        Args:
            event: The delta content list event.
            message: The message state to update.
        """
        delta = event.get("choices", [{}])[0].get("delta", {})

        for content_item in delta["content_list"]:
            # Determine how to handle the content item based on its properties
            if "type" in content_item and content_item["type"] == "text":
                # Handle text content
                # Implementation here
                pass
            elif "tool_use_id" in content_item or "input" in content_item:
                # Handle tool use content
                # Implementation here
                pass
            else:
                raise ValueError(f"Unsupported content item type: {content_item}")
