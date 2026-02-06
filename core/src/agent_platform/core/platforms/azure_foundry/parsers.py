import json
from collections.abc import AsyncGenerator
from typing import Any

from agent_platform.core.delta import GenericDelta
from agent_platform.core.delta.compute_delta import compute_generic_deltas
from agent_platform.core.platforms.base import PlatformParsers
from agent_platform.core.responses.content.audio import ResponseAudioContent
from agent_platform.core.responses.content.base import ResponseMessageContent
from agent_platform.core.responses.content.document import ResponseDocumentContent
from agent_platform.core.responses.content.image import ResponseImageContent
from agent_platform.core.responses.content.reasoning import ResponseReasoningContent
from agent_platform.core.responses.content.text import ResponseTextContent
from agent_platform.core.responses.content.tool_use import ResponseToolUseContent
from agent_platform.core.responses.response import ResponseMessage, TokenUsage
from agent_platform.core.streaming.error import StreamingError


class AzureFoundryParsers(PlatformParsers):
    """Parsers that transform Azure Foundry/Anthropic types to agent-server prompt types."""

    def parse_text_content(self, content: str | bytes | dict) -> ResponseTextContent:
        """Parses a platform-specific text content to an agent-server text content."""
        if isinstance(content, str):
            return ResponseTextContent(text=content)
        elif isinstance(content, bytes):
            return ResponseTextContent(text=content.decode("utf-8"))
        elif isinstance(content, dict) and "text" in content:
            return ResponseTextContent(text=content["text"])
        raise ValueError(f"Invalid text content format: {content}")

    def parse_reasoning_content(self, content: dict) -> ResponseReasoningContent:
        """Parses a platform-specific reasoning content to an agent-server reasoning content."""
        thinking = content.get("thinking", "")
        signature = content.get("signature", None)

        return ResponseReasoningContent(
            reasoning=thinking,
            signature=signature,
            redacted_content=None,
        )

    def parse_image_content(self, content: dict) -> ResponseImageContent:
        """Parses a platform-specific image content to an agent-server image content."""
        if not isinstance(content, dict):
            raise ValueError(f"Invalid image content format: {content}")

        source = content.get("source", {})
        source_type = source.get("type")

        if source_type == "base64":
            return ResponseImageContent(
                value=source.get("data", ""),
                sub_type="base64",
                mime_type=source.get("media_type", "image/png"),
            )
        elif source_type == "url":
            return ResponseImageContent(
                value=source.get("url", ""),
                sub_type="url",
                mime_type="image/png",  # URL images don't have explicit media type
            )
        raise ValueError(f"Invalid image source format: {source}")

    def parse_audio_content(self, content: str | bytes | dict) -> ResponseAudioContent:
        """Parses a platform-specific audio content to an agent-server audio content."""
        raise NotImplementedError("Audio content is not supported in Azure Foundry/Anthropic API")

    def parse_tool_use_content(self, content: dict) -> ResponseToolUseContent:
        """Parses a platform-specific tool use content to an agent-server tool use content."""
        if not isinstance(content, dict):
            raise ValueError(f"Invalid tool use content format: {content}")

        tool_call_id = content.get("id")
        if not tool_call_id:
            raise ValueError("Tool use content must have an id")

        tool_input = content.get("input", {})
        if not isinstance(tool_input, str):
            tool_input = json.dumps(tool_input)

        return ResponseToolUseContent(
            tool_call_id=tool_call_id,
            tool_name=content.get("name", ""),
            tool_input_raw=tool_input,
        )

    def parse_document_content(self, content: dict) -> ResponseDocumentContent:
        """Parses a platform-specific document content to an agent-server document content."""
        if not isinstance(content, dict):
            raise ValueError(f"Invalid document content format: {content}")

        source = content.get("source", {})
        source_type = source.get("type")

        if source_type == "base64":
            return ResponseDocumentContent(
                value=source.get("data", ""),
                sub_type="base64",
                name=content.get("name", "document"),
                mime_type=source.get("media_type", "application/pdf"),
            )
        elif source_type == "url":
            return ResponseDocumentContent(
                value=source.get("url", ""),
                sub_type="url",
                name=content.get("name", "document"),
                mime_type="application/pdf",
            )
        raise ValueError(f"Invalid document source format: {source}")

    def parse_content_item(self, item: dict) -> ResponseMessageContent:
        """Parses a platform-specific content item to an agent-server content item."""
        if not isinstance(item, dict):
            raise ValueError(f"Invalid content item format: {item}")

        content_type = item.get("type")

        if content_type == "text":
            return self.parse_text_content(item)
        elif content_type == "thinking":
            return self.parse_reasoning_content(item)
        elif content_type == "image":
            return self.parse_image_content(item)
        elif content_type == "document":
            return self.parse_document_content(item)
        elif content_type == "tool_use":
            return self.parse_tool_use_content(item)

        raise ValueError(f"Unsupported content type: {content_type}")

    def parse_response(self, response: dict) -> ResponseMessage:
        """Parses an Anthropic Messages API response to an agent-server model response.

        Args:
            response: The Anthropic response to parse.

        Returns:
            A ResponseMessage containing the parsed content and raw response.

        Raises:
            ValueError: If the response format is invalid or missing required fields.
        """
        if not isinstance(response, dict):
            raise ValueError(f"Invalid response format: {response}")

        content_blocks = response.get("content", [])
        if not content_blocks:
            raise ValueError("Response must contain non-empty 'content' field")

        # Parse all content blocks from the response
        message_contents = []
        for content_block in content_blocks:
            message_contents.append(self.parse_content_item(content_block))

        # Extract usage information
        usage = response.get("usage", {})
        token_usage = TokenUsage(
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            total_tokens=usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
        )

        # Map stop_reason to agent-server format
        stop_reason = response.get("stop_reason")

        return ResponseMessage(
            content=message_contents,
            role="agent",
            raw_response=response,
            stop_reason=stop_reason,
            usage=token_usage,
            metrics={},
            metadata={
                "id": response.get("id"),
                "model": response.get("model"),
            },
            additional_response_fields={},
        )

    def _check_stream_errors(self, event: dict) -> None:
        """Check for error events in the stream and raise appropriate exceptions.

        Args:
            event: The stream event to check.

        Raises:
            StreamingError: If an error event is encountered.
        """
        if event.get("type") == "error":
            error = event.get("error", {})
            error_msg = error.get("message", "Unknown streaming error")
            raise StreamingError(error_msg)

    def _handle_message_start(self, event: dict, message: dict) -> None:
        """Handle a message_start event.

        Args:
            event: The message_start event.
            message: The message state to update.
        """
        msg = event.get("message", {})
        message["role"] = "agent"
        message["content"] = []
        message["metadata"] = {
            "id": msg.get("id"),
            "model": msg.get("model"),
        }

    def _handle_content_block_start(self, event: dict, message: dict) -> None:
        """Handle a content_block_start event.

        Args:
            event: The content_block_start event.
            message: The message state to update.
        """
        content_block = event.get("content_block", {})
        block_type = content_block.get("type")

        if block_type == "tool_use":
            message["content"].append(
                {
                    "kind": "tool_use",
                    "tool_call_id": content_block.get("id", ""),
                    "tool_name": content_block.get("name", ""),
                    "tool_input_raw": "",
                },
            )
        elif block_type == "text":
            message["content"].append(
                {
                    "kind": "text",
                    "text": content_block.get("text", ""),
                },
            )
        elif block_type == "thinking":
            message["content"].append(
                {
                    "kind": "reasoning",
                    "reasoning": content_block.get("thinking", ""),
                    "signature": content_block.get("signature", ""),
                },
            )

    def _handle_content_block_delta(self, event: dict, message: dict) -> None:
        """Handle a content_block_delta event.

        Args:
            event: The content_block_delta event.
            message: The message state to update.
        """
        index = event.get("index", 0)
        delta = event.get("delta", {})
        delta_type = delta.get("type")

        # Ensure we have enough content blocks
        while len(message["content"]) <= index:
            message["content"].append({"kind": "text", "text": ""})

        if delta_type == "text_delta":
            if message["content"][index].get("kind") != "text":
                message["content"][index] = {"kind": "text", "text": ""}
            message["content"][index]["text"] += delta.get("text", "")
        elif delta_type == "input_json_delta":
            if message["content"][index].get("kind") != "tool_use":
                message["content"][index] = {
                    "kind": "tool_use",
                    "tool_call_id": "",
                    "tool_name": "",
                    "tool_input_raw": "",
                }
            message["content"][index]["tool_input_raw"] += delta.get("partial_json", "")
        elif delta_type == "thinking_delta":
            if message["content"][index].get("kind") != "reasoning":
                message["content"][index] = {"kind": "reasoning", "reasoning": "", "signature": ""}
            message["content"][index]["reasoning"] += delta.get("thinking", "")
        elif delta_type == "signature_delta":
            if message["content"][index].get("kind") == "reasoning":
                message["content"][index]["signature"] = delta.get("signature", "")

    def _handle_message_delta(self, event: dict, message: dict) -> None:
        """Handle a message_delta event.

        Args:
            event: The message_delta event.
            message: The message state to update.
        """
        delta = event.get("delta", {})
        if "stop_reason" in delta:
            message["stop_reason"] = delta["stop_reason"]

        usage = event.get("usage", {})
        if usage:
            message["usage"] = {
                "input_tokens": usage.get("input_tokens", 0),
                "output_tokens": usage.get("output_tokens", 0),
                "total_tokens": usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
            }

    async def parse_stream_event(
        self,
        event: dict,
        response: Any,
        message: dict[str, Any],
        last_message: dict[str, Any],
    ) -> AsyncGenerator[GenericDelta, None]:
        """Parses a single stream event into GenericDeltas.

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
        # Check for errors first
        self._check_stream_errors(event)

        event_type = event.get("type")

        # Handle each event type
        if event_type == "message_start":
            self._handle_message_start(event, message)
        elif event_type == "content_block_start":
            self._handle_content_block_start(event, message)
        elif event_type == "content_block_delta":
            self._handle_content_block_delta(event, message)
        elif event_type == "message_delta":
            self._handle_message_delta(event, message)

        # Compute and yield deltas between message states
        deltas = compute_generic_deltas(last_message, message)
        for delta in deltas:
            yield delta
