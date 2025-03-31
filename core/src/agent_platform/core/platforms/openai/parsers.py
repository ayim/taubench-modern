"""OpenAI platform parsers."""

from collections.abc import AsyncGenerator
from typing import Any

from agent_platform.core.delta import GenericDelta
from agent_platform.core.platforms.base import PlatformParsers
from agent_platform.core.responses.content import (
    ResponseAudioContent,
    ResponseDocumentContent,
    ResponseImageContent,
    ResponseMessageContent,
    ResponseTextContent,
    ResponseToolUseContent,
)
from agent_platform.core.responses.response import ResponseMessage, TokenUsage


class OpenAIParsers(PlatformParsers):
    """OpenAI platform parsers."""

    def _parse_text_content(self, content: str) -> ResponseTextContent:
        """Parse text content from OpenAI response.

        Args:
            content: Text content from OpenAI response.

        Returns:
            ResponseTextContent: Parsed text content.
        """
        return ResponseTextContent(text=content)

    def _parse_image_content(self, item: dict[str, Any]) -> ResponseImageContent:
        """Parse image content from OpenAI response.

        Args:
            item: Image content item from OpenAI response.

        Returns:
            ResponseImageContent: Parsed image content.
        """
        return ResponseImageContent(
            mime_type="image/jpeg",
            value=item["image_url"]["url"],
            sub_type="url",
            detail=item["image_url"].get("detail", "high_res"),
        )

    def _parse_audio_content(self, item: dict[str, Any]) -> ResponseAudioContent:
        """Parse audio content from OpenAI response.

        Args:
            item: Audio content item from OpenAI response.

        Returns:
            ResponseAudioContent: Parsed audio content.
        """
        return ResponseAudioContent(
            mime_type="audio/wav",
            value=item["audio_url"]["url"],
            sub_type="url",
        )

    def _parse_document_content(self, item: dict[str, Any]) -> ResponseDocumentContent:
        """Parse document content from OpenAI response.

        Args:
            item: Document content item from OpenAI response.

        Returns:
            ResponseDocumentContent: Parsed document content.
        """
        return ResponseDocumentContent(
            mime_type="application/pdf",
            value=item["document_url"]["url"],
            name=item["document_url"]["name"],
            sub_type="url",
        )

    def _parse_function_call(
        self,
        item: dict[str, Any],
        choice_index: int,
    ) -> ResponseToolUseContent:
        """Parse function call content from OpenAI response.

        Args:
            item: Function call item from OpenAI response.
            choice_index: Index of the choice in the response.

        Returns:
            ResponseToolUseContent: Parsed function call content.
        """
        return ResponseToolUseContent(
            tool_call_id=str(choice_index),
            tool_name=item["function_call"]["name"],
            tool_input_raw=item["function_call"]["arguments"],
        )

    def _parse_tool_calls(
        self,
        message: dict[str, Any],
    ) -> list[ResponseToolUseContent]:
        """Parse tool calls from OpenAI message.

        Args:
            message: Message containing tool calls.

        Returns:
            list[ResponseToolUseContent]: List of parsed tool calls.
        """
        if "tool_calls" not in message:
            return []

        return [
            ResponseToolUseContent(
                tool_call_id=tool_call["id"],
                tool_name=tool_call["function"]["name"],
                tool_input_raw=tool_call["function"]["arguments"],
            )
            for tool_call in message["tool_calls"]
        ]

    def _parse_content_list(
        self,
        content: list[dict[str, Any]],
        choice_index: int,
    ) -> list[ResponseMessageContent]:
        """Parse content list from OpenAI response.

        Args:
            content: List of content items from OpenAI response.
            choice_index: Index of the choice in the response.

        Returns:
            list[ResponseMessageContent]: List of parsed content items.
        """
        parsed_content: list[ResponseMessageContent] = []
        for item in content:
            if item["type"] == "text":
                parsed_content.append(self._parse_text_content(item["text"]))
            elif item["type"] == "image_url":
                parsed_content.append(self._parse_image_content(item))
            elif item["type"] == "audio_url":
                parsed_content.append(self._parse_audio_content(item))
            elif item["type"] == "document_url":
                parsed_content.append(self._parse_document_content(item))
            elif item["type"] == "function_call":
                parsed_content.append(self._parse_function_call(item, choice_index))
        return parsed_content

    def _extract_usage(self, response: dict[str, Any]) -> TokenUsage:
        """Extract usage information from OpenAI response.

        Args:
            response: OpenAI response.

        Returns:
            TokenUsage: Extracted usage information.
        """
        usage_dict = response.get("usage", {})
        return TokenUsage(
            input_tokens=usage_dict.get("prompt_tokens", 0),
            output_tokens=usage_dict.get("completion_tokens", 0),
            total_tokens=usage_dict.get("total_tokens", 0),
        )

    def parse_response(self, response: dict[str, Any]) -> ResponseMessage:
        """Parse OpenAI response to ResponseMessage.

        Args:
            response: OpenAI response.

        Returns:
            ResponseMessage: Parsed response message.

        Raises:
            ValueError: If response is invalid.
        """
        if "choices" not in response or not response["choices"]:
            raise ValueError("No choices in response")

        choice = response["choices"][0]
        message = choice["message"]
        content = message.get("content")

        # Parse content based on type
        parsed_content: list[ResponseMessageContent] = []
        if isinstance(content, str):
            parsed_content.append(self._parse_text_content(content))
        elif isinstance(content, list):
            parsed_content.extend(self._parse_content_list(content, choice["index"]))

        # Add tool calls if present
        parsed_content.extend(self._parse_tool_calls(message))

        return ResponseMessage(
            content=parsed_content,
            role="agent",
            raw_response=response,
            stop_reason=choice.get("finish_reason"),
            usage=self._extract_usage(response),
            metrics=response.get("metrics", {}),
            metadata=response.get("metadata", {}),
            additional_response_fields=response.get("additional_fields", {}),
        )

    def _parse_stream_content_list(
        self,
        content: list[dict[str, Any]],
        choice_index: int,
    ) -> list[ResponseMessageContent]:
        """Parse content list from OpenAI stream response.

        Args:
            content: List of content items from OpenAI stream response.
            choice_index: Index of the choice in the response.

        Returns:
            list[ResponseMessageContent]: List of parsed content items.
        """
        parsed_content: list[ResponseMessageContent] = []
        for item in content:
            if item["type"] == "text":
                parsed_content.append(self._parse_text_content(item["text"]))
            elif item["type"] == "image_url":
                parsed_content.append(self._parse_image_content(item))
            elif item["type"] == "audio_url":
                parsed_content.append(self._parse_audio_content(item))
            elif item["type"] == "document_url":
                parsed_content.append(self._parse_document_content(item))
            elif item["type"] == "function_call":
                parsed_content.append(self._parse_function_call(item, choice_index))
        return parsed_content

    def parse_stream_response(
        self,
        response: dict[str, Any],
    ) -> list[ResponseMessageContent]:
        """Parse OpenAI stream response to list of ResponseMessageContent.

        Args:
            response: OpenAI stream response.

        Returns:
            list[ResponseMessageContent]: List of parsed response content.

        Raises:
            ValueError: If response is invalid.
        """
        if "choices" not in response or not response["choices"]:
            raise ValueError("No choices in response")

        choice = response["choices"][0]
        delta = choice["delta"]

        if "content" not in delta:
            return []

        content = delta["content"]
        if isinstance(content, str):
            return [self._parse_text_content(content)]
        elif isinstance(content, list):
            return self._parse_stream_content_list(content, choice["index"])
        else:
            return []

    def parse_text_content(self, content: Any) -> ResponseTextContent:
        """Parse OpenAI text content to ResponseTextContent.

        Args:
            content: OpenAI text content.

        Returns:
            ResponseTextContent: Parsed text content.

        Raises:
            ValueError: If content is invalid.
        """
        if isinstance(content, str):
            return ResponseTextContent(text=content)
        elif isinstance(content, dict) and "text" in content:
            return ResponseTextContent(text=content["text"])
        raise ValueError(f"Invalid text content format: {content}")

    def parse_image_content(self, content: Any) -> ResponseImageContent:
        """Parse OpenAI image content to ResponseImageContent.

        Args:
            content: OpenAI image content.

        Returns:
            ResponseImageContent: Parsed image content.

        Raises:
            ValueError: If content is invalid.
        """
        if not isinstance(content, dict):
            raise ValueError(f"Invalid image content format: {content}")

        # Handle nested image_url structure
        if "image_url" in content:
            image_url = content["image_url"]
            if not isinstance(image_url, dict) or "url" not in image_url:
                raise ValueError(f"Invalid image_url format: {image_url}")
            return ResponseImageContent(
                mime_type="image/jpeg",
                value=image_url["url"],
                sub_type="url",
                detail=image_url.get("detail", "high_res"),
            )

        # Handle direct url/base64 structure
        if "url" in content:
            return ResponseImageContent(
                mime_type="image/jpeg",
                value=content["url"],
                sub_type="url",
                detail=content.get("detail", "high_res"),
            )
        elif "base64" in content:
            return ResponseImageContent(
                mime_type="image/jpeg",
                value=content["base64"],
                sub_type="base64",
                detail=content.get("detail", "high_res"),
            )
        raise ValueError(f"Invalid image content format: {content}")

    def parse_audio_content(self, content: Any) -> ResponseAudioContent:
        """Parse OpenAI audio content to ResponseAudioContent.

        Args:
            content: OpenAI audio content.

        Returns:
            ResponseAudioContent: Parsed audio content.

        Raises:
            ValueError: If content is invalid.
        """
        if not isinstance(content, dict):
            raise ValueError(f"Invalid audio content format: {content}")

        if "url" in content:
            return ResponseAudioContent(
                mime_type="audio/wav",
                value=content["url"],
                sub_type="url",
            )
        elif "base64" in content:
            return ResponseAudioContent(
                mime_type="audio/wav",
                value=content["base64"],
                sub_type="base64",
            )
        raise ValueError(f"Invalid audio content format: {content}")

    def parse_tool_use_content(
        self,
        content: Any,
    ) -> ResponseToolUseContent:
        """Parse OpenAI tool use content to ResponseToolUseContent.

        Args:
            content: OpenAI tool use content.

        Returns:
            ResponseToolUseContent: Parsed tool use content.

        Raises:
            ValueError: If content is invalid.
        """
        if not isinstance(content, dict):
            raise ValueError(f"Invalid tool use content format: {content}")

        # Handle nested function structure
        if "function" in content:
            function = content["function"]
            if not isinstance(function, dict):
                raise ValueError(f"Invalid function format: {function}")
            if "name" not in function or "arguments" not in function:
                raise ValueError("Function must have name and arguments")
            return ResponseToolUseContent(
                tool_call_id=content.get("id", ""),
                tool_name=function["name"],
                tool_input_raw=function["arguments"],
            )

        # Handle direct structure
        if "name" not in content or "arguments" not in content:
            raise ValueError("Tool use content must have name and arguments")

        return ResponseToolUseContent(
            tool_call_id=content.get("id", ""),
            tool_name=content["name"],
            tool_input_raw=content["arguments"],
        )

    def parse_document_content(
        self,
        content: Any,
    ) -> ResponseDocumentContent:
        """Parse OpenAI document content to ResponseDocumentContent.

        Args:
            content: OpenAI document content.

        Returns:
            ResponseDocumentContent: Parsed document content.

        Raises:
            ValueError: If content is invalid.
        """
        if not isinstance(content, dict):
            raise ValueError(f"Invalid document content format: {content}")

        # Handle nested file structure
        if "file" in content:
            file = content["file"]
            if not isinstance(file, dict):
                raise ValueError(f"Invalid file format: {file}")
            if "url" not in file or "name" not in file:
                raise ValueError("File must have url and name")
            return ResponseDocumentContent(
                mime_type="application/pdf",
                value=file["url"],
                name=file["name"],
                sub_type="url",
            )

        # Handle direct structure
        if "url" not in content or "name" not in content:
            raise ValueError("Document content must have url and name")

        return ResponseDocumentContent(
            mime_type="application/pdf",
            value=content["url"],
            name=content["name"],
            sub_type="url",
        )

    def parse_content_item(self, item: Any) -> ResponseMessageContent:
        """Parse OpenAI content item to ResponseMessageContent.

        Args:
            item: OpenAI content item.

        Returns:
            ResponseMessageContent: Parsed content item.

        Raises:
            ValueError: If item is invalid.
        """
        if isinstance(item, str):
            return ResponseTextContent(text=item)
        elif isinstance(item, dict):
            if "type" not in item:
                raise ValueError("Content item must have type")

            if item["type"] == "text":
                return ResponseTextContent(text=item["text"])
            elif item["type"] == "image_url":
                return self.parse_image_content(item["image_url"])
            elif item["type"] == "audio_url":
                return self.parse_audio_content(item["audio_url"])
            elif item["type"] == "document_url":
                return self.parse_document_content(item["document_url"])
            elif item["type"] == "function_call":
                return self.parse_tool_use_content(item["function_call"])
            else:
                raise ValueError(f"Unknown content type: {item['type']}")
        else:
            raise ValueError(f"Invalid content item format: {item}")

    async def parse_stream_event(
        self,
        event: dict[str, Any],
        response: dict[str, Any],
        message: ResponseMessage,
        last_message: ResponseMessage,
    ) -> AsyncGenerator[GenericDelta, None]:
        """Parse a single stream event into GenericDeltas.

        Args:
            event: A single event from the stream.
            response: The full response object containing metadata.
            message: The current message state.
            last_message: The previous message state for computing deltas.

        Yields:
            GenericDeltas that update the ResponseMessage.
        """
        if "choices" not in event or not event["choices"]:
            return

        choice = event["choices"][0]
        delta = choice.get("delta", {})

        # Handle content updates
        if "content" in delta:
            content = delta["content"]
            if content is not None:
                yield GenericDelta(
                    op="concat_string",
                    path="/content/0/text",
                    value=content,
                )

        # Handle tool calls
        if "tool_calls" in delta:
            for tool_call in delta["tool_calls"]:
                tool_content = {
                    "tool_call_id": tool_call["id"],
                    "tool_name": tool_call["function"]["name"],
                    "tool_input_raw": tool_call["function"]["arguments"],
                }
                yield GenericDelta(
                    op="add",
                    path="/content/1",
                    value=tool_content,
                )

        # Handle usage and metrics
        if "usage" in response:
            yield GenericDelta(
                op="replace",
                path="/usage",
                value=TokenUsage(
                    input_tokens=response["usage"].get("prompt_tokens", 0),
                    output_tokens=response["usage"].get("completion_tokens", 0),
                    total_tokens=response["usage"].get("total_tokens", 0),
                ),
            )
        if "metrics" in response:
            yield GenericDelta(
                op="replace",
                path="/metrics",
                value=response["metrics"],
            )
