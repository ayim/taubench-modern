import base64
import re
from io import BytesIO
from typing import TYPE_CHECKING, Any, Literal, cast

from agent_platform.core.kernel_interfaces.kernel_mixin import UsesKernelMixin
from agent_platform.core.platforms.base import PlatformConverters
from agent_platform.core.platforms.bedrock.configs import (
    BedrockContentLimits,
    BedrockMimeTypeMap,
)
from agent_platform.core.platforms.bedrock.prompts import BedrockPrompt
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
    from types_boto3_bedrock_runtime.type_defs import (
        ContentBlockTypeDef,
        DocumentBlockTypeDef,
        ImageBlockTypeDef,
        InferenceConfigurationTypeDef,
        MessageTypeDef,
        SystemContentBlockTypeDef,
        ToolChoiceTypeDef,
        ToolTypeDef,
    )


class BedrockConverters(PlatformConverters, UsesKernelMixin):
    """Converters that transform agent-server prompt types to Bedrock types."""

    async def _verify_image_dimensions(self, image_data: bytes) -> None:
        """Verify that an image meets Bedrock's dimension requirements.

        Args:
            image_data: Raw image bytes to verify.

        Raises:
            ValueError: If the image dimensions exceed Bedrock's limits.
        """
        from PIL import Image

        try:
            img = Image.open(BytesIO(image_data))
            width, height = img.size

            if width > BedrockContentLimits.max_image_width:
                raise ValueError(
                    f"Image width {width}px exceeds maximum allowed "
                    f"{BedrockContentLimits.max_image_width}px",
                )
            if height > BedrockContentLimits.max_image_height:
                raise ValueError(
                    f"Image height {height}px exceeds maximum allowed "
                    f"{BedrockContentLimits.max_image_height}px",
                )
        except Exception as e:
            raise ValueError(f"Failed to verify image dimensions: {e}") from e

    async def _verify_image_size(self, image_data: bytes) -> None:
        """Verify that an image meets Bedrock's size requirements.

        Args:
            image_data: Raw image bytes to verify.

        Raises:
            ValueError: If the image size exceeds Bedrock's limits.
        """
        size = len(image_data)
        if size > BedrockContentLimits.max_image_size:
            raise ValueError(
                f"Image size {size} bytes exceeds maximum allowed "
                f"{BedrockContentLimits.max_image_size} bytes",
            )

    async def _verify_image_count(
        self,
        content_blocks: list["ContentBlockTypeDef"],
    ) -> None:
        """Verify that the number of images in content blocks doesn't exceed limits.

        Args:
            content_blocks: List of content blocks to check.

        Raises:
            ValueError: If the number of images exceeds Bedrock's limits.
        """
        image_count = sum(1 for block in content_blocks if "image" in block)
        if image_count > BedrockContentLimits.max_image_count:
            raise ValueError(
                f"Number of images {image_count} exceeds maximum allowed "
                f"{BedrockContentLimits.max_image_count}",
            )

    async def _verify_document_size(self, document_data: bytes) -> None:
        """Verify that a document meets Bedrock's size requirements.

        Args:
            document_data: Raw document bytes to verify.

        Raises:
            ValueError: If the document size exceeds Bedrock's limits.
        """
        size = len(document_data)
        if size > BedrockContentLimits.max_document_size:
            raise ValueError(
                f"Document size {size} bytes exceeds maximum allowed "
                f"{BedrockContentLimits.max_document_size} bytes",
            )

    async def _verify_document_count(
        self,
        content_blocks: list["ContentBlockTypeDef"],
    ) -> None:
        """Verify that the number of documents in content blocks doesn't exceed limits.

        Args:
            content_blocks: List of content blocks to check.

        Raises:
            ValueError: If the number of documents exceeds Bedrock's limits.
        """
        doc_count = sum(1 for block in content_blocks if "document" in block)
        if doc_count > BedrockContentLimits.max_document_count:
            raise ValueError(
                f"Number of documents {doc_count} exceeds maximum allowed "
                f"{BedrockContentLimits.max_document_count}",
            )

    async def _verify_document_name(self, name: str) -> None:
        """Verify that a document name meets Bedrock's requirements.

        Args:
            name: The document name to verify.

        Raises:
            ValueError: If the document name contains invalid characters or formatting.
        """
        # Check for consecutive whitespace
        if re.search(r"\s{2,}", name):
            raise ValueError(
                "Document name cannot contain consecutive whitespace characters",
            )

        # Check for valid characters (alphanumeric, single spaces, hyphens,
        # parentheses, square brackets)
        if not re.match(r"^[a-zA-Z0-9\s\-\(\)\[\]]+$", name):
            raise ValueError(
                "Document name can only contain alphanumeric characters, "
                "single spaces, hyphens, parentheses, and square brackets",
            )

    async def convert_text_content(
        self,
        content: PromptTextContent,
    ) -> "ContentBlockTypeDef":
        """Converts text content to Bedrock format."""
        from types_boto3_bedrock_runtime.type_defs import ContentBlockTypeDef

        return ContentBlockTypeDef(text=content.text)

    async def convert_image_content(
        self,
        content: PromptImageContent,
    ) -> "ContentBlockTypeDef":
        """Converts image content to Bedrock format.

        Raises:
            ValueError: If the image exceeds Bedrock's size or dimension limits.
        """
        from types_boto3_bedrock_runtime.type_defs import ContentBlockTypeDef

        # Convert to ImageBlockTypeDef and wrap in ContentBlockTypeDef
        image_block = await self._convert_to_image_block(content)
        return ContentBlockTypeDef(image=image_block)

    async def convert_audio_content(
        self,
        content: PromptAudioContent,
    ) -> "ContentBlockTypeDef":
        """Converts audio content to Bedrock format."""
        raise NotImplementedError("Audio content is not supported in Bedrock")

    async def convert_tool_use_content(
        self,
        content: PromptToolUseContent,
    ) -> "ContentBlockTypeDef":
        """Converts tool use content to Bedrock format."""
        from types_boto3_bedrock_runtime.type_defs import (
            ContentBlockTypeDef,
            ToolUseBlockTypeDef,
        )

        tool_use = ToolUseBlockTypeDef(
            toolUseId=content.tool_call_id,
            name=content.tool_name,
            input=content.tool_input,
        )
        return ContentBlockTypeDef(toolUse=tool_use)

    async def _convert_to_image_block(
        self,
        content: PromptImageContent,
    ) -> "ImageBlockTypeDef":
        """Converts image content to Bedrock ImageBlockTypeDef format.

        Args:
            content: The image content to convert.

        Returns:
            An ImageBlockTypeDef suitable for Bedrock API.

        Raises:
            ValueError: If the image exceeds Bedrock's size or dimension limits.
        """
        from types_boto3_bedrock_runtime.literals import ImageFormatType
        from types_boto3_bedrock_runtime.type_defs import ImageBlockTypeDef

        converted_format = cast(
            ImageFormatType,
            BedrockMimeTypeMap.reverse_mapping().get(content.mime_type),
        )
        if converted_format is None:
            raise ValueError(f"Unsupported MIME type: {content.mime_type}")
        if converted_format not in {"gif", "jpeg", "png", "webp"}:
            raise ValueError(f"Unsupported image format: {converted_format}")

        if content.sub_type == "url":
            if not isinstance(content.value, str):
                raise ValueError("URL image value must be a string")
            # TODO: Implement URL image source (fetch and get bytes)
            raise NotImplementedError("URL image source is not supported in Bedrock")
        elif content.sub_type == "base64":
            if not isinstance(content.value, str):
                raise ValueError("Base64 image value must be a string")
            # Verify the base64 data
            decoded = None
            try:
                decoded = base64.b64decode(content.value)
                await self._verify_image_size(decoded)
                await self._verify_image_dimensions(decoded)
            except Exception as e:
                raise ValueError(f"Invalid base64 image data: {e}") from e
            return ImageBlockTypeDef(
                format=converted_format,
                source={"bytes": decoded},
            )
        else:  # raw_bytes
            if not isinstance(content.value, bytes):
                raise ValueError("Raw bytes image value must be bytes")
            await self._verify_image_size(content.value)
            await self._verify_image_dimensions(content.value)
            return ImageBlockTypeDef(
                format=converted_format,
                source={
                    "bytes": base64.b64encode(content.value).decode(),
                },
            )

    async def _convert_to_document_block(
        self,
        content: PromptDocumentContent,
    ) -> "DocumentBlockTypeDef":
        """Converts document content to Bedrock DocumentBlockTypeDef format.

        Args:
            content: The document content to convert.

        Returns:
            A DocumentBlockTypeDef suitable for Bedrock API.

        Raises:
            ValueError: If the document exceeds Bedrock's size limits or has invalid
                name format.
            NotImplementedError: If the content type is not supported
                (e.g. UploadedFile).
        """
        from types_boto3_bedrock_runtime.literals import DocumentFormatType
        from types_boto3_bedrock_runtime.type_defs import DocumentBlockTypeDef

        converted_format = cast(
            DocumentFormatType,
            BedrockMimeTypeMap.reverse_mapping().get(content.mime_type),
        )
        if converted_format is None:
            raise ValueError(f"Unsupported MIME type: {content.mime_type}")
        if converted_format not in {"csv", "doc", "docx", "html", "md", "pdf", "txt"}:
            raise ValueError(f"Unsupported document format: {converted_format}")

        # Verify document name format
        await self._verify_document_name(content.name)

        if content.sub_type == "url":
            if not isinstance(content.value, str):
                raise ValueError("URL document value must be a string")
            # TODO: Implement URL document source (fetch and get bytes)
            raise NotImplementedError("URL document source is not supported in Bedrock")
        elif content.sub_type == "base64":
            if not isinstance(content.value, str):
                raise ValueError("Base64 document value must be a string")
            document_data = base64.b64decode(content.value)
            await self._verify_document_size(document_data)
            return DocumentBlockTypeDef(
                format=converted_format,
                name=content.name,
                source={"bytes": document_data},
            )
        elif content.sub_type == "raw_bytes":
            if not isinstance(content.value, bytes):
                raise ValueError("Raw bytes document value must be bytes")
            await self._verify_document_size(content.value)
            return DocumentBlockTypeDef(
                format=converted_format,
                name=content.name,
                source={"bytes": base64.b64encode(content.value).decode()},
            )
        else:  # UploadedFile
            # TODO: handle UploadedFile once the kernel.files interface is implemented.
            raise NotImplementedError("No interface exists for UploadedFile")

    async def convert_tool_result_content(
        self,
        content: PromptToolResultContent,
    ) -> "ContentBlockTypeDef":
        """Converts tool result content to Bedrock format.

        Handles text, image, audio, and document content types, converting each to the
        appropriate Bedrock format.
        """
        from types_boto3_bedrock_runtime.type_defs import (
            ContentBlockTypeDef,
            ToolResultBlockTypeDef,
            ToolResultContentBlockTypeDef,
        )

        result_content: list[ToolResultContentBlockTypeDef] = []

        for content_item in content.content:
            if isinstance(content_item, PromptTextContent):
                result_content.append(
                    ToolResultContentBlockTypeDef(text=content_item.text),
                )
            elif isinstance(content_item, PromptImageContent):
                # Convert to proper ImageBlockTypeDef
                image_block = await self._convert_to_image_block(content_item)
                result_content.append(ToolResultContentBlockTypeDef(image=image_block))
            elif isinstance(content_item, PromptDocumentContent):
                # Convert to proper DocumentBlockTypeDef
                document_block = await self._convert_to_document_block(content_item)
                result_content.append(
                    ToolResultContentBlockTypeDef(document=document_block),
                )
            elif isinstance(content_item, PromptAudioContent):
                raise NotImplementedError("Audio content is not supported in Bedrock")
            else:
                raise ValueError(f"Unsupported content type: {type(content_item)}")

        tool_result = ToolResultBlockTypeDef(
            toolUseId=content.tool_call_id,
            content=result_content,
            status="success" if not content.is_error else "error",
        )
        return ContentBlockTypeDef(toolResult=tool_result)

    async def convert_document_content(
        self,
        content: PromptDocumentContent,
    ) -> "ContentBlockTypeDef":
        """Converts document content to Bedrock format.

        Raises:
            ValueError: If the document exceeds Bedrock's size limits or has invalid
                name format.
        """
        from types_boto3_bedrock_runtime.type_defs import ContentBlockTypeDef

        # Convert to DocumentBlockTypeDef and wrap in ContentBlockTypeDef
        document_block = await self._convert_to_document_block(content)
        return ContentBlockTypeDef(document=document_block)

    async def convert_reasoning_content(
        self,
        content: PromptReasoningContent,
    ) -> "ContentBlockTypeDef":
        """Converts reasoning content to Bedrock format."""
        from types_boto3_bedrock_runtime.type_defs import (
            ContentBlockTypeDef,
            ReasoningContentBlockTypeDef,
            ReasoningTextBlockTypeDef,
        )

        reasoning_content: ReasoningContentBlockTypeDef

        if content.reasoning is not None or content.signature is not None:
            reasoning_text_kwargs: dict[str, str] = {
                "text": content.reasoning or "",
                "signature": content.signature or "",
            }
            reasoning_content = ReasoningContentBlockTypeDef(
                reasoningText=ReasoningTextBlockTypeDef(**reasoning_text_kwargs),
            )
        elif content.redacted_content is not None:
            reasoning_content = ReasoningContentBlockTypeDef(
                redactedContent=content.redacted_content,
            )
        else:
            reasoning_content = ReasoningContentBlockTypeDef(
                reasoningText=ReasoningTextBlockTypeDef(text="", signature=""),
            )

        return ContentBlockTypeDef(reasoningContent=reasoning_content)

    async def _reverse_role_map(self, role: str) -> Literal["user", "assistant"]:
        """Reverse the role map.

        Args:
            role: The role to reverse.

        Returns:
            The corresponding Bedrock role name.

        Raises:
            ValueError: If the role is not found in the map.
        """
        match role:
            case "user":
                return "user"
            case "agent":
                return "assistant"
            case _:
                raise ValueError(f"Role '{role}' not mapped to Bedrock role")

    async def _convert_messages(  # noqa: C901
        self,
        messages: list[PromptUserMessage | PromptAgentMessage],
    ) -> list["MessageTypeDef"]:
        """Convert prompt messages to Bedrock message format.

        Args:
            messages: List of prompt messages to convert.

        Returns:
            List of converted Bedrock messages.

        Raises:
            ValueError: If any content in the messages exceeds Bedrock's limits.
        """
        from types_boto3_bedrock_runtime.type_defs import (
            ContentBlockTypeDef,
            MessageTypeDef,
        )

        converted_messages: list[MessageTypeDef] = []

        for message in messages:
            content_blocks: list[ContentBlockTypeDef] = []
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
                        # No empty thinking blocks (say, same thread, we have an empty thought from
                        # a non-thinking model, and then flop to a thinking model)
                        if content.reasoning is not None or content.redacted_content is not None:
                            content_blocks.append(await self.convert_reasoning_content(content))
                    case _:
                        raise ValueError(f"Unsupported content type: {type(content)}")

            # Within a content block list, tool use needs to get sorted to the _end_ of the
            # content block list
            content_blocks.sort(key=lambda x: "toolUse" in x)

            # Verify content limits
            await self._verify_image_count(content_blocks)
            await self._verify_document_count(content_blocks)

            converted_messages.append(
                MessageTypeDef(
                    role=await self._reverse_role_map(message.role),
                    content=content_blocks,
                ),
            )

        return converted_messages

    async def _convert_system_instruction(
        self,
        system_instruction: str | None,
    ) -> list["SystemContentBlockTypeDef"]:
        """Convert system instruction to Bedrock system format.

        Args:
            system_instruction: System instruction to convert.

        Returns:
            List containing single system content block with the instruction.
        """
        from types_boto3_bedrock_runtime.type_defs import SystemContentBlockTypeDef

        if system_instruction is None:
            return []

        return [SystemContentBlockTypeDef(text=system_instruction)]

    async def _build_inference_config(
        self,
        temperature: float | None,
        max_output_tokens: int | None,
        stop_sequences: list[str] | None,
        top_p: float | None,
    ) -> "InferenceConfigurationTypeDef | None":
        """Build Bedrock inference configuration from prompt parameters.

        Args:
            temperature: Temperature parameter for sampling.
            max_output_tokens: Maximum tokens to generate.
            stop_sequences: Sequences that stop generation.
            top_p: Top-p sampling parameter.

        Returns:
            Inference configuration if any parameters are set, None otherwise.
        """
        from types_boto3_bedrock_runtime.type_defs import InferenceConfigurationTypeDef

        config = InferenceConfigurationTypeDef()
        if temperature is not None:
            config["temperature"] = temperature
        if max_output_tokens is not None:
            config["maxTokens"] = max_output_tokens
        if stop_sequences is not None:
            config["stopSequences"] = stop_sequences
        if top_p is not None:
            config["topP"] = top_p

        return None if not config else config

    async def _convert_tools(
        self,
        tools: list[ToolDefinition],
    ) -> list["ToolTypeDef"]:
        """Convert tool definitions to Bedrock tool format.

        Args:
            tools: List of tool definitions to convert.

        Returns:
            List of converted Bedrock tools.
        """
        from types_boto3_bedrock_runtime.type_defs import (
            ToolSpecificationTypeDef,
            ToolTypeDef,
        )

        converted_tools: list[ToolTypeDef] = []
        for tool in tools:
            tool_spec = ToolSpecificationTypeDef(
                name=tool.name,
                description=tool.description,
                inputSchema={"json": tool.input_schema},
            )
            converted_tools.append(ToolTypeDef(toolSpec=tool_spec))
        return converted_tools

    async def _convert_tool_choice(
        self,
        tool_choice: Literal["auto", "any"] | str,
        tools: list[ToolDefinition],
    ) -> "ToolChoiceTypeDef":
        """Convert tool choice to Bedrock format.

        Args:
            tool_choice: The tool choice setting ("auto", "any", or specific tool name).
            tools: List of available tools for validation.

        Returns:
            Converted Bedrock tool choice configuration.

        Raises:
            ValueError: If tool_choice is invalid or references non-existent tool.
        """
        from types_boto3_bedrock_runtime.type_defs import (
            SpecificToolChoiceTypeDef,
            ToolChoiceTypeDef,
        )

        if tool_choice == "auto":
            return ToolChoiceTypeDef(auto={})
        elif tool_choice == "any":
            return ToolChoiceTypeDef(any={})
        else:
            return ToolChoiceTypeDef(tool=SpecificToolChoiceTypeDef(name=tool_choice))

    async def convert_prompt(
        self,
        prompt: Prompt,
        model_id: str | None = None,
    ) -> BedrockPrompt:
        """Converts a prompt to Bedrock format.

        Args:
            prompt: The prompt to convert.

        Returns:
            A BedrockPrompt instance with all converted fields.

        Raises:
            ValueError: If any content in the prompt exceeds Bedrock's limits.
        """
        is_thinking_model = model_id and "thinking" in model_id

        messages = await self._convert_messages(prompt.finalized_messages)
        system = await self._convert_system_instruction(prompt.system_instruction)
        inference_config = await self._build_inference_config(
            prompt.temperature if not is_thinking_model else None,
            prompt.max_output_tokens,
            prompt.stop_sequences,
            prompt.top_p if not is_thinking_model else None,
        )

        # Convert tools if present
        tool_config = None
        if prompt.tools:
            from types_boto3_bedrock_runtime.type_defs import ToolConfigurationTypeDef

            tool_config = ToolConfigurationTypeDef(
                tools=await self._convert_tools(prompt.tools),
                toolChoice=await self._convert_tool_choice(
                    prompt.tool_choice,
                    prompt.tools,
                ),
            )

        overrides = self._build_model_request_overrides(
            model_id,
            minimize_reasoning=prompt.minimize_reasoning,
        )

        return BedrockPrompt(
            messages=messages,
            system=system,
            inference_config=inference_config,
            tool_config=tool_config,
            additional_model_request_fields=overrides,
        )

    def _build_model_request_overrides(
        self,
        model_id: str | None,
        minimize_reasoning: bool,
    ) -> dict[str, Any] | None:
        """Build provider-specific request overrides for thinking models."""

        if model_id is None:
            return None

        if minimize_reasoning:
            return None

        overrides = {
            "thinking": {
                "type": "enabled",
                "budget_tokens": 2048,
            },
            "anthropic_beta": ["interleaved-thinking-2025-05-14"],
        }

        if model_id.endswith("-high"):
            overrides["thinking"]["budget_tokens"] = 16384
        elif model_id.endswith("-medium"):
            overrides["thinking"]["budget_tokens"] = 8192
        elif model_id.endswith("-low"):
            overrides["thinking"]["budget_tokens"] = 4096
        else:
            return None

        return overrides
