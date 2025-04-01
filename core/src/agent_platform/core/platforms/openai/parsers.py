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
        for choice in response["choices"]:
            if "message" not in choice:
                continue

            response_content = []

            message = choice["message"]
            message_content = ""
            if message.get("content"):
                response_content.append(
                    ResponseTextContent(text=message["content"]),
                )

            usage = response.get("usage", {})
            token_usage = TokenUsage(
                input_tokens=usage.get("prompt_tokens", 0),
                output_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
            )

            response = ResponseMessage(
                role="agent",
                content=response_content,
                usage=token_usage,
            )
            response_messages.append(response)

        if len(response_messages) == 0:
            raise ValueError("No response messages found in OpenAI response")

        return response_messages[0]

    async def parse_stream_event(
        self,
        event: Any,
        message: dict[str, Any],
        last_message: dict[str, Any],
    ) -> AsyncGenerator[GenericDelta, None]:
        """Parses a single stream event from OpenAI into GenericDeltas."""
        # Initialize key parts of the message if they don't exist
        if "role" not in message:
            message["role"] = "agent"

        if "content" not in message:
            message["content"] = []

        # Collect values that don't directly map to ResponseMessage fields
        if "additional_response_fields" not in message:
            message["additional_response_fields"] = {}

        # Handle different event types from OpenAI completions
        if hasattr(event, "choices") and event.choices:
            choice = event.choices[0]

            # Handle delta content (text content)
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

            # Handle delta tool calls
            if (
                hasattr(choice, "delta")
                and hasattr(choice.delta, "tool_calls")
                and choice.delta.tool_calls
            ):
                for tool_call in choice.delta.tool_calls:
                    # Find the existing tool call or create a new one
                    tool_id = (
                        tool_call.id
                        if hasattr(tool_call, "id") and tool_call.id
                        else None
                    )

                    if tool_id:
                        # Look for an existing tool use content with this ID
                        tool_found = False
                        for i, item in enumerate(message["content"]):
                            if (
                                item.get("kind") == "tool_use"
                                and item.get("tool_call_id") == tool_id
                            ):
                                tool_found = True
                                # Update tool use content
                                if hasattr(tool_call, "function"):
                                    if (
                                        hasattr(tool_call.function, "name")
                                        and tool_call.function.name
                                    ):
                                        message["content"][i]["tool_name"] = (
                                            tool_call.function.name
                                        )

                                    if (
                                        hasattr(tool_call.function, "arguments")
                                        and tool_call.function.arguments
                                    ):
                                        # Add to the tool input raw field
                                        if (
                                            "tool_input_raw"
                                            not in message["content"][i]
                                        ):
                                            message["content"][i]["tool_input_raw"] = ""

                                        # Accumulate arguments
                                        message["content"][i]["tool_input_raw"] += (
                                            tool_call.function.arguments
                                        )

                                break

                        if not tool_found and tool_id:
                            # Create a new tool use content with exactly the fields expected by ResponseToolUseContent
                            tool_content = {
                                "kind": "tool_use",
                                "tool_call_id": tool_id,
                                "tool_name": "",
                                "tool_input_raw": "",
                            }

                            # Add initial data if available
                            if hasattr(tool_call, "function"):
                                if (
                                    hasattr(tool_call.function, "name")
                                    and tool_call.function.name
                                ):
                                    tool_content["tool_name"] = tool_call.function.name

                                if (
                                    hasattr(tool_call.function, "arguments")
                                    and tool_call.function.arguments
                                ):
                                    tool_content["tool_input_raw"] = (
                                        tool_call.function.arguments
                                    )

                            message["content"].append(tool_content)
                    # Handle the case where we get tool function details without an ID
                    # This can happen with some versions of the API
                    elif hasattr(tool_call, "function") and (
                        hasattr(tool_call.function, "name")
                        or hasattr(tool_call.function, "arguments")
                    ):
                        # Find any existing tool use content that doesn't have complete details
                        found = False
                        for i, item in enumerate(message["content"]):
                            if item.get("kind") == "tool_use":
                                if (
                                    hasattr(tool_call.function, "name")
                                    and tool_call.function.name
                                ):
                                    message["content"][i]["tool_name"] = (
                                        tool_call.function.name
                                    )

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

                        # If no tool use content exists, create one
                        if (
                            not found
                            and hasattr(tool_call.function, "arguments")
                            and tool_call.function.arguments
                        ):
                            tool_name = ""
                            if (
                                hasattr(tool_call.function, "name")
                                and tool_call.function.name
                            ):
                                tool_name = tool_call.function.name

                            # Create with a placeholder ID if none exists
                            tool_content = {
                                "kind": "tool_use",
                                "tool_call_id": "call_default",
                                "tool_name": tool_name,
                                "tool_input_raw": tool_call.function.arguments,
                            }
                            message["content"].append(tool_content)

            # Handle message object directly (some API versions send a complete message)
            if hasattr(choice, "message") and hasattr(choice.message, "tool_calls"):
                for tool_call in choice.message.tool_calls:
                    if hasattr(tool_call, "id") and hasattr(tool_call, "function"):
                        tool_found = False
                        for i, item in enumerate(message["content"]):
                            if (
                                item.get("kind") == "tool_use"
                                and item.get("tool_call_id") == tool_call.id
                            ):
                                tool_found = True
                                # Update with complete data
                                message["content"][i]["tool_name"] = (
                                    tool_call.function.name
                                )
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

            # Handle finish reason
            if hasattr(choice, "finish_reason") and choice.finish_reason:
                message["stop_reason"] = choice.finish_reason
                # If we're done with a tool call, double check the content
                if choice.finish_reason == "tool_calls":
                    # Check if we have any tool use without arguments
                    for i, item in enumerate(message["content"]):
                        if item.get("kind") == "tool_use" and not item.get(
                            "tool_input_raw",
                        ):
                            # If we're missing arguments but have an ID, try to find the arguments
                            # in the message or additional data
                            if hasattr(choice, "message") and hasattr(
                                choice.message,
                                "tool_calls",
                            ):
                                for tc in choice.message.tool_calls:
                                    if tc.id == item.get("tool_call_id") and hasattr(
                                        tc.function,
                                        "arguments",
                                    ):
                                        message["content"][i]["tool_input_raw"] = (
                                            tc.function.arguments
                                        )

        # Handle other event fields - store in additional_response_fields instead of top level
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

        # Calculate and yield deltas
        deltas = compute_generic_deltas(last_message, message)
        for delta in deltas:
            yield delta

    def _handle_delta_content_list(self, event: dict, message: dict) -> None:
        """Handle a delta content list event.

        Args:
            event: The delta content list event.
            message: The message state to update.
        """
        delta = event.get("choices", [{}])[0].get("delta", {})

        last_item_type = None
        if "content" in message:
            last_item_type = message["content"][-1]["type"]

        for content_item in delta["content_list"]:
            # First, we need to deduce the type of the item
            item_type = None
            if "type" in content_item and content_item["type"] == "text":
                item_type = "text"
            elif "tool_use_id" in content_item or "input" in content_item:
                item_type = "tool_use"
            else:
                raise ValueError(f"Unsupported content item type: {content_item}")
