import json
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any, cast

from agent_platform.core.delta import GenericDelta
from agent_platform.core.delta.compute_delta import compute_generic_deltas
from agent_platform.core.platforms.base import PlatformParsers
from agent_platform.core.platforms.bedrock.configs import (
    BedrockMimeTypeMap,
    BedrockRoleMap,
)
from agent_platform.core.responses.content.audio import ResponseAudioContent
from agent_platform.core.responses.content.base import ResponseMessageContent
from agent_platform.core.responses.content.document import (
    ResponseDocumentContent,
    ResponseDocumentMimeTypes,
)
from agent_platform.core.responses.content.image import (
    ResponseImageContent,
    ResponseImageMimeTypes,
)
from agent_platform.core.responses.content.text import ResponseTextContent
from agent_platform.core.responses.content.tool_use import ResponseToolUseContent
from agent_platform.core.responses.response import ResponseMessage, TokenUsage
from agent_platform.core.streaming.error import StreamingError

if TYPE_CHECKING:
    from types_boto3_bedrock_runtime.type_defs import (
        ContentBlockOutputTypeDef,
        ContentBlockTypeDef,
        ConverseResponseTypeDef,
        ConverseStreamResponseTypeDef,
        DocumentBlockOutputTypeDef,
        DocumentBlockTypeDef,
        ImageBlockOutputTypeDef,
        ImageBlockTypeDef,
        ResponseMetadataTypeDef,
        ToolUseBlockOutputTypeDef,
        ToolUseBlockTypeDef,
    )


class BedrockParsers(PlatformParsers):
    """Parsers that transform Bedrock types to agent-server prompt types."""

    def parse_text_content(self, content: str | bytes | dict) -> ResponseTextContent:
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
        content: "ImageBlockTypeDef | ImageBlockOutputTypeDef",
    ) -> ResponseImageContent:
        """Parses a platform-specific image content to an agent-server
        image content."""
        if not isinstance(content, dict):
            raise ValueError(f"Invalid image content format: {content}")

        image_format = content.get("format")
        if not image_format:
            raise ValueError("Image content must have a format")

        source = content.get("source", {})
        mime_type = cast(
            ResponseImageMimeTypes,
            BedrockMimeTypeMap.mime_type_map[image_format],
        )

        if "base64" in source:
            return ResponseImageContent(
                value=source["base64"],
                sub_type="base64",
                mime_type=mime_type,
            )
        elif "url" in source:
            return ResponseImageContent(
                value=source["url"],
                sub_type="url",
                mime_type=mime_type,
            )
        elif "bytes" in source:
            # Source bytes can be Union[str, bytes, IO[Any], StreamingBody]
            raw_bytes = None
            if isinstance(source["bytes"], str):
                raw_bytes = source["bytes"].encode("utf-8")
            elif isinstance(source["bytes"], bytes):
                raw_bytes = source["bytes"]
            elif isinstance(source["bytes"], bytearray):
                raw_bytes = bytes(source["bytes"])
            else:
                raise ValueError(f"Invalid image source format: {source}")

            return ResponseImageContent(
                value=raw_bytes,
                sub_type="raw_bytes",
                mime_type=mime_type,
            )
        raise ValueError(f"Invalid image source format: {source}")

    def parse_audio_content(self, content: str | bytes | dict) -> ResponseAudioContent:
        """Parses a platform-specific audio content to an agent-server
        audio content."""
        raise NotImplementedError("Audio content is not supported in Bedrock")

    def parse_tool_use_content(
        self,
        content: "ToolUseBlockTypeDef | ToolUseBlockOutputTypeDef",
    ) -> ResponseToolUseContent:
        """Parses a platform-specific tool use content to an agent-server
        tool use content."""
        if not isinstance(content, dict):
            raise ValueError(f"Invalid tool use content format: {content}")

        # Get tool call ID from 'toolUseId' key
        if not content.get("toolUseId"):
            raise ValueError(
                "Tool use content must have a tool call ID (toolUseId)",
            )

        # Ensure input is already a string as expected from the Bedrock API
        tool_input = content["input"]
        if not isinstance(tool_input, str):
            tool_input = json.dumps(tool_input)

        return ResponseToolUseContent(
            tool_call_id=content["toolUseId"],
            tool_name=content["name"],
            tool_input_raw=tool_input,
        )

    def parse_document_content(
        self,
        content: "DocumentBlockTypeDef | DocumentBlockOutputTypeDef",
    ) -> ResponseDocumentContent:
        """Parses a platform-specific document content to an agent-server
        document content."""
        if not isinstance(content, dict):
            raise ValueError(f"Invalid document content format: {content}")

        doc_format = content.get("format")
        if not doc_format:
            raise ValueError("Document content must have a format")

        source = content.get("source", {})
        name = content.get("name")
        if not name:
            raise ValueError("Document content must have a name")

        mime_type = cast(
            ResponseDocumentMimeTypes,
            BedrockMimeTypeMap.mime_type_map[doc_format],
        )

        if "base64" in source:
            return ResponseDocumentContent(
                value=source["base64"],
                sub_type="base64",
                name=name,
                mime_type=mime_type,
            )
        elif "url" in source:
            return ResponseDocumentContent(
                value=source["url"],
                sub_type="url",
                name=name,
                mime_type=mime_type,
            )
        elif "bytes" in source:
            # Source bytes can be Union[str, bytes, IO[Any], StreamingBody]
            raw_bytes = None
            if isinstance(source["bytes"], str):
                raw_bytes = source["bytes"].encode("utf-8")
            elif isinstance(source["bytes"], bytes):
                raw_bytes = source["bytes"]
            elif isinstance(source["bytes"], bytearray):
                raw_bytes = bytes(source["bytes"])
            else:
                raise ValueError(f"Invalid image source format: {source}")

            return ResponseDocumentContent(
                value=raw_bytes,
                sub_type="raw_bytes",
                name=name,
                mime_type=mime_type,
            )
        raise ValueError(f"Invalid document source format: {source}")

    def parse_content_item(
        self,
        item: "ContentBlockTypeDef | ContentBlockOutputTypeDef",
    ) -> ResponseMessageContent:
        """Parses a platform-specific content item to an agent-server content item."""
        if not isinstance(item, dict):
            raise ValueError(f"Invalid content item format: {item}")

        if "text" in item:
            return self.parse_text_content(item["text"])
        elif "image" in item:
            return self.parse_image_content(item["image"])
        elif "document" in item:
            return self.parse_document_content(item["document"])
        elif "toolUse" in item:
            return self.parse_tool_use_content(item["toolUse"])
        elif "guardContent" in item:
            # Handle guard content - for now just extract text if present
            # TODO: Handle guard content more robustly
            # guard = item["guardContent"]
            # if isinstance(guard, dict) and "text" in guard:
            #     return self.parse_text_content(guard["text"])
            pass

        raise ValueError(f"Unsupported content type in item: {item}")

    def parse_response(
        self,
        response: "ConverseResponseTypeDef",
    ) -> ResponseMessage:
        """Parses a Bedrock converse response to an agent-server model response.

        Args:
            response: The Bedrock converse response to parse.

        Returns:
            A ResponseMessage containing the parsed content and raw response.

        Raises:
            ValueError: If the response format is invalid or missing required fields.
        """
        if not isinstance(response, dict):
            raise ValueError(f"Invalid response format: {response}")

        output = response.get("output")
        if not output:
            raise ValueError("Response must contain 'output' field")

        message = output.get("message")
        if not message or not isinstance(message, dict):
            raise ValueError("Output must contain valid 'message' field")

        content_blocks = message.get("content", [])
        if not content_blocks:
            raise ValueError("Message must contain non-empty 'content' field")

        # Parse all content blocks from the message
        message_contents = []
        for content_block in content_blocks:
            message_contents.append(self.parse_content_item(content_block))

        # Extract usage information
        usage = response.get("usage", {})
        token_usage = TokenUsage(
            input_tokens=usage.get("inputTokens", 0),
            output_tokens=usage.get("outputTokens", 0),
            total_tokens=usage.get("totalTokens", 0),
        )

        # Extract metrics
        metrics = response.get("metrics", {})

        # Extract response metadata
        response_metadata: ResponseMetadataTypeDef | None = response.get(
            "ResponseMetadata",
        )
        metadata = {}
        if response_metadata:
            metadata = {
                "request_id": response_metadata.get("RequestId"),
                "http_status_code": response_metadata.get("HTTPStatusCode"),
                "http_headers": response_metadata.get("HTTPHeaders", {}),
                "retry_attempts": response_metadata.get("RetryAttempts"),
                "host_id": response_metadata.get("HostId"),
            }

        # Extract additional fields that don't fit in other categories
        additional_fields = {
            "trace": response.get("trace"),
            "performanceConfig": response.get("performanceConfig"),
        }

        return ResponseMessage(
            content=message_contents,
            role="agent",
            raw_response=response,
            stop_reason=response.get("stopReason"),
            usage=token_usage,
            metrics=dict(metrics),
            metadata=metadata,
            additional_response_fields=additional_fields,
        )

    def _check_stream_errors(self, event: dict) -> None:
        """Check for error events in the stream and raise appropriate exceptions.

        Args:
            event: The stream event to check.

        Raises:
            StreamingError: If an error event is encountered.
        """
        for error_type in [
            "internalServerException",
            "modelStreamErrorException",
            "validationException",
            "throttlingException",
            "serviceUnavailableException",
        ]:
            if error_type in event:
                error_msg = event[error_type].get(
                    "message",
                    f"Unknown {error_type}",
                )
                raise StreamingError(error_msg)

    def _handle_message_start(self, event: dict, message: dict) -> None:
        """Handle a message start event.

        Args:
            event: The message start event.
            message: The message state to update.
        """
        message["role"] = BedrockRoleMap.role_map[event["messageStart"]["role"]]
        message["content"] = []

    def _handle_content_block_start(self, event: dict, message: dict) -> None:
        """Handle a content block start event.

        Args:
            event: The content block start event.
            message: The message state to update.
        """
        if "toolUse" in event["contentBlockStart"]["start"]:
            tool_use = event["contentBlockStart"]["start"]["toolUse"]
            message["content"].append(
                {
                    "kind": "tool_use",
                    "tool_call_id": tool_use["toolUseId"],
                    "tool_name": tool_use["name"],
                    "tool_input_raw": "",
                },
            )

    def _handle_content_block_delta(self, event: dict, message: dict) -> None:
        """Handle a content block delta event.

        Args:
            event: The content block delta event.
            message: The message state to update.
        """
        delta = event["contentBlockDelta"]
        content_block_index = delta["contentBlockIndex"]
        if "text" in delta["delta"]:
            kind = "text"
        elif "toolUse" in delta["delta"]:
            kind = "tool_use"
        else:
            raise ValueError(
                f"Unsupported content block type: {delta['delta']}",
            )

        # Ensure we have enough content blocks
        while len(message["content"]) <= content_block_index:
            new_block = {"kind": kind}
            if kind == "text":
                new_block["text"] = ""
            else:
                new_block["tool_input_raw"] = ""
            message["content"].append(new_block)

        if delta.get("delta", {}).get("text"):
            # Append text to the current block
            message["content"][content_block_index]["text"] += delta["delta"]["text"]
        elif delta.get("delta", {}).get("toolUse"):
            # Append to tool use input
            # The Bedrock API returns tool inputs as string fragments that
            # we concatenate to build the complete JSON string
            tool_delta = delta["delta"]["toolUse"]
            if "input" in tool_delta:
                message["content"][content_block_index]["tool_input_raw"] += tool_delta["input"]

    def _handle_message_stop(self, event: dict, message: dict) -> None:
        """Handle a message stop event.

        Args:
            event: The message stop event.
            message: The message state to update.
        """
        if "stopReason" in event["messageStop"]:
            message["stop_reason"] = event["messageStop"]["stopReason"]
        if "additionalModelResponseFields" in event["messageStop"]:
            message["additional_response_fields"] = event["messageStop"][
                "additionalModelResponseFields"
            ]

    def _handle_metadata(
        self,
        event: dict,
        message: dict,
        response: "ConverseStreamResponseTypeDef | ConverseResponseTypeDef",
    ) -> None:
        """Handle a metadata event.

        Args:
            event: The metadata event.
            message: The message state to update.
            response: The full response object containing ResponseMetadata.
        """
        message["metadata"] = {
            "request_id": response.get("ResponseMetadata", {}).get("RequestId"),
            "http_status_code": response.get("ResponseMetadata", {}).get(
                "HTTPStatusCode",
            ),
            "http_headers": response.get("ResponseMetadata", {}).get("HTTPHeaders", {}),
            "retry_attempts": response.get("ResponseMetadata", {}).get("RetryAttempts"),
            "host_id": response.get("ResponseMetadata", {}).get("HostId"),
        }

        if "usage" in event["metadata"]:
            usage = event["metadata"]["usage"]
            message["usage"] = {
                "input_tokens": usage.get("inputTokens", 0),
                "output_tokens": usage.get("outputTokens", 0),
                "total_tokens": usage.get("totalTokens", 0),
            }

        if "metrics" in event["metadata"]:
            message["metrics"] = event["metadata"]["metrics"]

    async def parse_stream_event(
        self,
        event: dict,
        response: "ConverseStreamResponseTypeDef",
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
        # Check for errors first
        self._check_stream_errors(event)

        # Handle each event type
        if "messageStart" in event:
            self._handle_message_start(event, message)
        elif "contentBlockStart" in event:
            self._handle_content_block_start(event, message)
        elif "contentBlockDelta" in event:
            self._handle_content_block_delta(event, message)
        elif "messageStop" in event:
            self._handle_message_stop(event, message)
        elif "metadata" in event:
            self._handle_metadata(event, message, response)

        # Compute and yield deltas between message states
        deltas = compute_generic_deltas(last_message, message)
        for delta in deltas:
            yield delta
