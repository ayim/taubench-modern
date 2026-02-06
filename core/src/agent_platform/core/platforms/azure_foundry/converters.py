from __future__ import annotations

import base64
from io import BytesIO
from typing import TYPE_CHECKING, Any, Literal

from structlog import get_logger

from agent_platform.core.kernel_interfaces.kernel_mixin import UsesKernelMixin
from agent_platform.core.platforms.azure_foundry.configs import (
    AzureFoundryContentLimits,
    AzureFoundryMimeTypeMap,
)
from agent_platform.core.platforms.base import PlatformConverters
from agent_platform.core.prompts import Prompt
from agent_platform.core.prompts.content.audio import PromptAudioContent
from agent_platform.core.prompts.content.document import PromptDocumentContent
from agent_platform.core.prompts.content.image import PromptImageContent
from agent_platform.core.prompts.content.reasoning import PromptReasoningContent
from agent_platform.core.prompts.content.text import PromptTextContent
from agent_platform.core.prompts.content.tool_result import PromptToolResultContent
from agent_platform.core.prompts.content.tool_use import PromptToolUseContent
from agent_platform.core.prompts.messages import PromptAgentMessage, PromptUserMessage
from agent_platform.core.tools.tool_definition import ToolDefinition

if TYPE_CHECKING:
    from agent_platform.core.platforms.azure_foundry.prompts import AzureFoundryPrompt

logger = get_logger(__name__)


class AzureFoundryConverters(PlatformConverters, UsesKernelMixin):
    """Converters that transform agent-server prompt types to Azure Foundry/Anthropic types."""

    async def _verify_image_dimensions(self, image_data: bytes) -> None:
        """Verify that an image meets dimension requirements.

        Args:
            image_data: Raw image bytes to verify.

        Raises:
            ValueError: If the image dimensions exceed limits.
        """
        from PIL import Image

        try:
            img = Image.open(BytesIO(image_data))
            width, height = img.size

            if width > AzureFoundryContentLimits.max_image_width:
                raise ValueError(
                    f"Image width {width}px exceeds maximum allowed {AzureFoundryContentLimits.max_image_width}px",
                )
            if height > AzureFoundryContentLimits.max_image_height:
                raise ValueError(
                    f"Image height {height}px exceeds maximum allowed {AzureFoundryContentLimits.max_image_height}px",
                )
        except Exception as e:
            raise ValueError(f"Failed to verify image dimensions: {e}") from e

    async def _verify_image_size(self, image_data: bytes) -> None:
        """Verify that an image meets size requirements.

        Args:
            image_data: Raw image bytes to verify.

        Raises:
            ValueError: If the image size exceeds limits.
        """
        size = len(image_data)
        if size > AzureFoundryContentLimits.max_image_size:
            raise ValueError(
                f"Image size {size} bytes exceeds maximum allowed {AzureFoundryContentLimits.max_image_size} bytes",
            )

    async def _verify_image_count(
        self,
        content_blocks: list[dict[str, Any]],
    ) -> None:
        """Verify that the number of images in content blocks doesn't exceed limits.

        Args:
            content_blocks: List of content blocks to check.

        Raises:
            ValueError: If the number of images exceeds limits.
        """
        image_count = sum(1 for block in content_blocks if block.get("type") == "image")
        if image_count > AzureFoundryContentLimits.max_image_count:
            raise ValueError(
                f"Number of images {image_count} exceeds maximum allowed {AzureFoundryContentLimits.max_image_count}",
            )

    async def _verify_document_size(self, document_data: bytes) -> None:
        """Verify that a document meets size requirements.

        Args:
            document_data: Raw document bytes to verify.

        Raises:
            ValueError: If the document size exceeds limits.
        """
        size = len(document_data)
        if size > AzureFoundryContentLimits.max_document_size:
            max_size = AzureFoundryContentLimits.max_document_size
            raise ValueError(f"Document size {size} bytes exceeds maximum allowed {max_size} bytes")

    async def _verify_document_count(
        self,
        content_blocks: list[dict[str, Any]],
    ) -> None:
        """Verify that the number of documents in content blocks doesn't exceed limits.

        Args:
            content_blocks: List of content blocks to check.

        Raises:
            ValueError: If the number of documents exceeds limits.
        """
        doc_count = sum(1 for block in content_blocks if block.get("type") == "document")
        if doc_count > AzureFoundryContentLimits.max_document_count:
            max_count = AzureFoundryContentLimits.max_document_count
            raise ValueError(f"Number of documents {doc_count} exceeds maximum allowed {max_count}")

    async def convert_text_content(
        self,
        content: PromptTextContent,
    ) -> dict[str, Any]:
        """Converts text content to Anthropic format."""
        return {"type": "text", "text": content.text}

    async def convert_image_content(
        self,
        content: PromptImageContent,
    ) -> dict[str, Any]:
        """Converts image content to Anthropic format.

        Raises:
            ValueError: If the image exceeds size or dimension limits.
        """
        media_type = content.mime_type
        if media_type not in AzureFoundryMimeTypeMap.mime_type_map.values():
            # Try to map from format type
            reverse_map = AzureFoundryMimeTypeMap.reverse_mapping()
            if media_type not in reverse_map:
                raise ValueError(f"Unsupported image MIME type: {media_type}")

        if content.sub_type == "url":
            if not isinstance(content.value, str):
                raise ValueError("URL image value must be a string")
            return {
                "type": "image",
                "source": {
                    "type": "url",
                    "url": content.value,
                },
            }
        elif content.sub_type == "base64":
            if not isinstance(content.value, str):
                raise ValueError("Base64 image value must be a string")
            # Verify the base64 data
            try:
                decoded = base64.b64decode(content.value)
                await self._verify_image_size(decoded)
                await self._verify_image_dimensions(decoded)
            except Exception as e:
                raise ValueError(f"Invalid base64 image data: {e}") from e
            return {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": content.value,
                },
            }
        else:  # raw_bytes
            if not isinstance(content.value, bytes):
                raise ValueError("Raw bytes image value must be bytes")
            await self._verify_image_size(content.value)
            await self._verify_image_dimensions(content.value)
            encoded = base64.b64encode(content.value).decode("utf-8")
            return {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": encoded,
                },
            }

    async def convert_audio_content(
        self,
        content: PromptAudioContent,
    ) -> dict[str, Any]:
        """Converts audio content - not supported in Anthropic API."""
        raise NotImplementedError("Audio content is not supported in Azure Foundry/Anthropic API")

    async def convert_tool_use_content(
        self,
        content: PromptToolUseContent,
    ) -> dict[str, Any]:
        """Converts tool use content to Anthropic format."""
        return {
            "type": "tool_use",
            "id": content.tool_call_id,
            "name": content.tool_name,
            "input": content.tool_input,
        }

    async def convert_tool_result_content(
        self,
        content: PromptToolResultContent,
    ) -> dict[str, Any]:
        """Converts tool result content to Anthropic format."""
        result_content: list[dict[str, Any]] = []

        for content_item in content.content:
            if isinstance(content_item, PromptTextContent):
                result_content.append({"type": "text", "text": content_item.text})
            elif isinstance(content_item, PromptImageContent):
                result_content.append(await self.convert_image_content(content_item))
            elif isinstance(content_item, PromptAudioContent):
                raise NotImplementedError("Audio content is not supported in Azure Foundry/Anthropic API")
            else:
                raise ValueError(f"Unsupported content type: {type(content_item)}")

        return {
            "type": "tool_result",
            "tool_use_id": content.tool_call_id,
            "content": result_content,
            "is_error": content.is_error,
        }

    async def convert_document_content(
        self,
        content: PromptDocumentContent,
    ) -> dict[str, Any]:
        """Converts document content to Anthropic format.

        Raises:
            ValueError: If the document exceeds size limits.
        """
        media_type = content.mime_type

        if content.sub_type == "url":
            if not isinstance(content.value, str):
                raise ValueError("URL document value must be a string")
            return {
                "type": "document",
                "source": {
                    "type": "url",
                    "url": content.value,
                },
            }
        elif content.sub_type == "base64":
            if not isinstance(content.value, str):
                raise ValueError("Base64 document value must be a string")
            document_data = base64.b64decode(content.value)
            await self._verify_document_size(document_data)
            return {
                "type": "document",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": content.value,
                },
            }
        elif content.sub_type == "raw_bytes":
            if not isinstance(content.value, bytes):
                raise ValueError("Raw bytes document value must be bytes")
            await self._verify_document_size(content.value)
            encoded = base64.b64encode(content.value).decode("utf-8")
            return {
                "type": "document",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": encoded,
                },
            }
        else:
            raise NotImplementedError(f"Document sub_type '{content.sub_type}' is not supported")

    async def convert_reasoning_content(
        self,
        content: PromptReasoningContent,
    ) -> dict[str, Any]:
        """Converts reasoning content to Anthropic format."""
        if content.redacted_content is not None:
            return {
                "type": "thinking",
                "thinking": content.redacted_content,
            }

        return {
            "type": "thinking",
            "thinking": content.reasoning or "",
            "signature": content.signature,
        }

    async def _reverse_role_map(self, role: str) -> Literal["user", "assistant"]:
        """Reverse the role map.

        Args:
            role: The role to reverse.

        Returns:
            The corresponding Anthropic role name.

        Raises:
            ValueError: If the role is not found in the map.
        """
        match role:
            case "user":
                return "user"
            case "agent":
                return "assistant"
            case _:
                raise ValueError(f"Role '{role}' not mapped to Anthropic role")

    async def _convert_messages(
        self,
        messages: list[PromptUserMessage | PromptAgentMessage],
    ) -> list[dict[str, Any]]:
        """Convert prompt messages to Anthropic message format.

        Args:
            messages: List of prompt messages to convert.

        Returns:
            List of converted Anthropic messages.

        Raises:
            ValueError: If any content in the messages exceeds limits.
        """
        converted_messages: list[dict[str, Any]] = []

        for message in messages:
            content_blocks: list[dict[str, Any]] = []
            for content in message.content:
                match content:
                    case PromptTextContent():
                        content_blocks.append(await self.convert_text_content(content))
                    case PromptImageContent():
                        content_blocks.append(await self.convert_image_content(content))
                    case PromptAudioContent():
                        content_blocks.append(await self.convert_audio_content(content))
                    case PromptToolUseContent():
                        content_blocks.append(await self.convert_tool_use_content(content))
                    case PromptToolResultContent():
                        content_blocks.append(await self.convert_tool_result_content(content))
                    case PromptDocumentContent():
                        content_blocks.append(await self.convert_document_content(content))
                    case PromptReasoningContent():
                        # No empty thinking blocks
                        if content.reasoning is not None or content.redacted_content is not None:
                            content_blocks.append(await self.convert_reasoning_content(content))
                    case _:
                        raise ValueError(f"Unsupported content type: {type(content)}")

            # Verify content limits
            await self._verify_image_count(content_blocks)
            await self._verify_document_count(content_blocks)

            converted_messages.append(
                {
                    "role": await self._reverse_role_map(message.role),
                    "content": content_blocks,
                },
            )

        return converted_messages

    async def _convert_tools(
        self,
        tools: list[ToolDefinition],
    ) -> list[dict[str, Any]]:
        """Convert tool definitions to Anthropic tool format.

        Args:
            tools: List of tool definitions to convert.

        Returns:
            List of converted Anthropic tools.
        """
        converted_tools: list[dict[str, Any]] = []
        for tool in tools:
            converted_tools.append(
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.input_schema,
                }
            )
        return converted_tools

    async def _convert_tool_choice(
        self,
        tool_choice: Literal["auto", "any"] | str,
        tools: list[ToolDefinition],
    ) -> dict[str, Any]:
        """Convert tool choice to Anthropic format.

        Args:
            tool_choice: The tool choice setting ("auto", "any", or specific tool name).
            tools: List of available tools for validation.

        Returns:
            Converted Anthropic tool choice configuration.
        """
        if tool_choice == "auto":
            return {"type": "auto"}
        elif tool_choice == "any":
            return {"type": "any"}
        else:
            return {"type": "tool", "name": tool_choice}

    async def convert_prompt(
        self,
        prompt: Prompt,
        model_id: str | None = None,
    ) -> AzureFoundryPrompt:
        """Converts a prompt to Azure Foundry/Anthropic format.

        Args:
            prompt: The prompt to convert.
            model_id: The model ID for the request.

        Returns:
            An AzureFoundryPrompt instance with all converted fields.

        Raises:
            ValueError: If any content in the prompt exceeds limits.
        """
        from agent_platform.core.platforms.azure_foundry.prompts import AzureFoundryPrompt

        is_thinking_model = model_id and "thinking" in model_id

        messages = await self._convert_messages(prompt.finalized_messages)
        system = prompt.system_instruction

        # Build tool configuration if present
        tools = None
        tool_choice = None
        if prompt.tools:
            tools = await self._convert_tools(prompt.tools)
            tool_choice = await self._convert_tool_choice(prompt.tool_choice, prompt.tools)

        # Build thinking configuration for thinking models
        thinking = None
        betas = ["interleaved-thinking-2025-05-14"]
        if is_thinking_model and not prompt.minimize_reasoning:
            budget_tokens = 2048
            if model_id and model_id.endswith("-high"):
                budget_tokens = 16384
            elif model_id and model_id.endswith("-medium"):
                budget_tokens = 8192
            elif model_id and model_id.endswith("-low"):
                budget_tokens = 4096

            thinking = {
                "type": "enabled",
                "budget_tokens": budget_tokens,
            }

        return AzureFoundryPrompt(
            messages=messages,
            system=system,
            max_tokens=prompt.max_output_tokens,
            temperature=prompt.temperature if not is_thinking_model else None,
            top_p=prompt.top_p if not is_thinking_model else None,
            stop_sequences=prompt.stop_sequences,
            tools=tools,
            tool_choice=tool_choice,
            thinking=thinking,
            betas=betas if is_thinking_model else None,
        )
