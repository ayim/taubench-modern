import json
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
from agent_platform.core.streaming.error import StreamingError


class CortexParsers(PlatformParsers):
    """Parsers that transform Cortex types to agent-server prompt types."""

    def parse_text_content(self, content: Any) -> ResponseTextContent:
        """Parses a platform-specific text content to an agent-server
        text content."""
        if isinstance(content, str):
            return ResponseTextContent(text=content)
        elif isinstance(content, bytes):
            return ResponseTextContent(text=content.decode("utf-8"))
        elif isinstance(content, dict) and "text" in content:
            return ResponseTextContent(text=content["text"])
        raise ValueError(f"Invalid text content format: {content}")

    def parse_image_content(
        self,
        content: Any,
    ) -> ResponseImageContent:
        """Parses a platform-specific image content to an agent-server
        image content."""
        raise NotImplementedError("Image content is not supported in Cortex")

    def parse_audio_content(self, content: Any) -> ResponseAudioContent:
        """Parses a platform-specific audio content to an agent-server
        audio content."""
        raise NotImplementedError("Audio content is not supported in Cortex")

    def parse_tool_use_content(
        self,
        content: Any,
    ) -> ResponseToolUseContent:
        """Parses a platform-specific tool use content to an agent-server
        tool use content."""
        if not isinstance(content, dict):
            raise ValueError(f"Invalid tool use content format: {content}")

        # Get tool call ID from 'tool_use_id' key
        if not content.get("tool_use_id"):
            raise ValueError(
                "Tool use content must have a tool call ID (tool_use_id)",
            )

        # Ensure input is already a string as expected from the Bedrock API
        tool_input = content["input"]
        if not isinstance(tool_input, str):
            tool_input = json.dumps(tool_input)

        return ResponseToolUseContent(
            tool_call_id=content["tool_use_id"],
            tool_name=content["name"],
            tool_input_raw=tool_input,
        )

    def parse_document_content(
        self,
        content: Any,
    ) -> ResponseDocumentContent:
        """Parses a platform-specific document content to an agent-server
        document content."""
        raise NotImplementedError("Document content is not supported in Cortex")

    def parse_content_item(
        self,
        item: Any,
    ) -> ResponseMessageContent:
        """Parses a platform-specific content item to an agent-server content item."""
        if not isinstance(item, dict) or "type" not in item:
            raise ValueError(f"Invalid content item format: {item}")

        if item["type"] == "text":
            return self.parse_text_content(item["text"])
        elif item["type"] == "image":
            return self.parse_image_content(item["image"])
        elif item["type"] == "document":
            return self.parse_document_content(item["document"])
        elif item["type"] == "tool_use":
            return self.parse_tool_use_content(item["tool_use"])

        raise ValueError(f"Unsupported content type in item: {item}")

    def parse_response(
        self,
        response: Any,
    ) -> ResponseMessage:
        """Parses a Bedrock converse response to an agent-server model response.

        Args:
            response: The Cortex converse response to parse.

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
            if "content" in message:
                message_content = message["content"]
                response_content.append(
                    ResponseTextContent(text=message["content"]),
                )

            for item in message["content_list"] if "content_list" in message else []:
                # Ignore if repeated in content_list
                if "text" in item and item["text"] == message_content:
                    continue
                response_content.append(self.parse_content_item(item))

            response = ResponseMessage(
                role="agent",
                content=response_content,
                usage=(
                    TokenUsage(
                        input_tokens=0,
                        output_tokens=0,
                        total_tokens=0,
                    )
                    if "usage" not in response
                    else (
                        TokenUsage(
                            input_tokens=response["usage"].get("prompt_tokens", 0),
                            output_tokens=response["usage"].get("completion_tokens", 0),
                            total_tokens=response["usage"].get("total_tokens", 0),
                        )
                    )
                ),
            )
            response_messages.append(response)

        if len(response_messages) == 0:
            raise ValueError("No response messages found in Cortex response")

        return response_messages[0]

    async def parse_stream_event(
        self,
        event_line: str,
        message: dict[str, Any],
        last_message: dict[str, Any],
    ) -> AsyncGenerator[GenericDelta, None]:
        """Parses a single stream event into GenericDeltas.

        This method will:
        1. Parse a single event from Bedrock's ConverseStreamOutputTypeDef
        2. Update the response message state based on the event
        3. Compute and yield deltas between message states

        Args:
            event: A single event from the stream.
            response: The full response object containing metadata.
            message: The current accumulated message state.
            last_message: The previous message state for computing deltas.

        Yields:
            GenericDeltas that update the ResponseMessage.

        Raises:
            StreamingError: If an error event is encountered.
        """
        if not event_line or not event_line.strip():
            return

        # Handle each event type
        if event_line == "data: [DONE]":
            event_line = "{}"
        elif event_line.startswith("data: "):
            event_line = event_line[6:]

        # Try to parse the event line as JSON
        try:
            event = json.loads(event_line)
            self._handle_delta_content_list(event, message)
            self._handle_delta_usage(event, message)
        except json.JSONDecodeError as exc:
            raise StreamingError(f"Invalid JSON event: {event_line}") from exc

        if "role" not in message:
            message["role"] = "agent"

        # Compute and yield deltas between message states
        deltas = compute_generic_deltas(last_message, message)
        for delta in deltas:
            yield delta

    def _handle_delta_content_list(  # noqa: C901, PLR0912
        self,
        event: dict,
        message: dict,
    ) -> None:
        """Handle a delta content list event.

        Args:
            event: The delta content list event.
            message: The message state to update.
        """
        delta = event.get("choices", [{}])[0].get("delta", {})
        if "content_list" not in delta:
            return

        last_item_type = None
        if "content" in message and len(message["content"]) > 0:
            last_item_type = message["content"][-1]["kind"]

        for content_item in delta["content_list"]:
            # First, we need to deduce the type of the item
            item_type = None
            if "type" in content_item and content_item["type"] == "text":
                item_type = "text"
            elif "tool_use_id" in content_item or "input" in content_item:
                item_type = "tool_use"
            else:
                raise ValueError(f"Unsupported content item type: {content_item}")

            # If the item type has changed, we need to start a new message
            # content block
            if item_type != last_item_type:
                if "content" not in message:
                    message["content"] = []
                message["content"].append({"kind": item_type})

            if item_type == "tool_use" and last_item_type == "tool_use":
                if "tool_call_id" in message["content"][-1]:
                    if (
                        "tool_use_id" in content_item
                        and message["content"][-1]["tool_call_id"] != content_item["tool_use_id"]
                    ):
                        # This is a new tool use! (Parallel tool calls)
                        # Do NOT append to the last item, start a new one
                        message["content"].append({"kind": item_type})

            # Now, we can parse the item
            if item_type == "text":
                if "text" not in message["content"][-1]:
                    message["content"][-1]["text"] = ""
                message["content"][-1]["text"] += content_item["text"]
                # They now send us an empty text block with usage, so if we just
                # added empty text, pop this item off the list
                if message["content"][-1]["text"] == "":
                    message["content"].pop()
            elif item_type == "tool_use":
                if "tool_use_id" in content_item:
                    message["content"][-1]["tool_call_id"] = content_item["tool_use_id"]
                if "name" in content_item:
                    message["content"][-1]["tool_name"] = content_item["name"]
                if "tool_input_raw" not in message["content"][-1]:
                    message["content"][-1]["tool_input_raw"] = ""
                message["content"][-1]["tool_input_raw"] += (
                    content_item["input"] if "input" in content_item else ""
                )

    def _handle_delta_usage(self, event: dict, message: dict) -> None:
        """Handle a delta usage event.

        Args:
            event: The delta usage event.
            message: The message state to update.
        """
        if "usage" not in event:
            return

        message["usage"] = {
            "input_tokens": event["usage"].get("prompt_tokens", 0),
            "output_tokens": event["usage"].get("completion_tokens", 0),
            "total_tokens": event["usage"].get("total_tokens", 0),
        }
