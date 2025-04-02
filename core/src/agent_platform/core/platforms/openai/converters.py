from collections.abc import Sequence
from typing import Literal, cast

from agent_platform.core.kernel_interfaces.kernel_mixin import UsesKernelMixin
from agent_platform.core.platforms.base import PlatformConverters
from agent_platform.core.platforms.openai.configs import OpenAIRoleMap
from agent_platform.core.platforms.openai.prompts import OpenAIPrompt
from agent_platform.core.platforms.openai.types import (
    OpenAIPromptContent,
    OpenAIPromptMessage,
    OpenAIPromptToolResults,
    OpenAIPromptToolSpec,
    OpenAIPromptToolUse,
)
from agent_platform.core.prompts import (
    Prompt,
    PromptAgentMessage,
    PromptAudioContent,
    PromptImageContent,
    PromptMessageContent,
    PromptTextContent,
    PromptToolResultContent,
    PromptToolUseContent,
    PromptUserMessage,
)
from agent_platform.core.prompts.content.document import PromptDocumentContent
from agent_platform.core.tools.tool_definition import ToolDefinition


class OpenAIConverters(PlatformConverters, UsesKernelMixin):
    """Converters that transform agent-server prompt types to OpenAI types."""

    async def convert_text_content(
        self,
        content: PromptTextContent,
    ) -> OpenAIPromptContent:
        """Converts text content to OpenAI format."""
        return OpenAIPromptContent(
            type="text",
            text=content.text,
        )

    async def convert_image_content(
        self,
        content: PromptImageContent,
    ) -> OpenAIPromptContent:
        """Converts image content to OpenAI format."""
        raise NotImplementedError("Image not supported yet")

    async def convert_audio_content(
        self,
        content: PromptAudioContent,
    ) -> OpenAIPromptContent:
        """Converts audio content to OpenAI format."""
        raise NotImplementedError("Audio not supported yet")

    async def convert_tool_use_content(
        self,
        content: PromptToolUseContent,
    ) -> OpenAIPromptContent:
        """Converts tool use content to OpenAI format."""
        return OpenAIPromptContent(
            type="tool_use",
            tool_use=OpenAIPromptToolUse(
                tool_use_id=content.tool_call_id,
                name=content.tool_name,
                input=content.tool_input,
            ),
        )

    async def convert_tool_result_content(
        self,
        content: PromptToolResultContent,
    ) -> OpenAIPromptContent:
        """Converts tool result content to OpenAI format."""
        result_content: list[OpenAIPromptContent] = []

        for content_item in content.content:
            if isinstance(content_item, PromptTextContent):
                result_content.append(
                    OpenAIPromptContent(type="text", text=content_item.text),
                )
            elif isinstance(content_item, PromptImageContent):
                raise NotImplementedError("Image not supported yet")
            elif isinstance(content_item, PromptAudioContent):
                raise NotImplementedError("Audio not supported yet")
            elif isinstance(content_item, PromptDocumentContent):
                raise NotImplementedError("Document not supported yet")
            else:
                raise ValueError(f"Unsupported content type: {type(content_item)}")

        return OpenAIPromptContent(
            type="tool_results",
            tool_results=OpenAIPromptToolResults(
                tool_use_id=content.tool_call_id,
                name=content.tool_name,
                content=result_content,
            ),
        )

    async def convert_document_content(
        self,
        content: PromptDocumentContent,
    ) -> OpenAIPromptContent:
        """Converts document content to OpenAI format."""
        raise NotImplementedError("Document not supported yet")

    async def _reverse_role_map(self, role: str) -> Literal["user", "assistant"]:
        """Reverse the role map.

        Args:
            role: The role to reverse.

        Returns:
            The corresponding OpenAI role name.

        Raises:
            ValueError: If the role is not found in the map.
        """
        for openai_role, our_role in OpenAIRoleMap.class_items():
            if our_role == role:
                return cast(Literal["user", "assistant"], openai_role)
        raise ValueError(f"Role '{role}' not found in OpenAIRoleMap")

    async def _convert_messages(
        self,
        messages: list[PromptUserMessage | PromptAgentMessage],
    ) -> list[OpenAIPromptMessage]:
        """Convert prompt messages to OpenAI message format.

        Args:
            messages: The list of prompt messages to convert.

        Returns:
            The list of OpenAI messages.
        """
        converted_messages: list[OpenAIPromptMessage] = []

        for message in messages:
            content_blocks = await self._convert_message_content(message.content)
            openai_message = await self._create_openai_message(
                message.role,
                content_blocks,
            )
            converted_messages.append(openai_message)

        return converted_messages

    async def _convert_message_content(
        self,
        content_list: Sequence[PromptMessageContent],
    ) -> list[OpenAIPromptContent]:
        """Convert prompt message content to OpenAI content blocks.

        Args:
            content_list: The list of content to convert.

        Returns:
            The list of OpenAI content blocks.
        """
        content_blocks: list[OpenAIPromptContent] = []

        for content in content_list:
            if isinstance(content, PromptTextContent):
                content_blocks.append(await self.convert_text_content(content))
            elif isinstance(content, PromptImageContent):
                content_blocks.append(await self.convert_image_content(content))
            elif isinstance(content, PromptAudioContent):
                content_blocks.append(await self.convert_audio_content(content))
            elif isinstance(content, PromptToolUseContent):
                content_blocks.append(await self.convert_tool_use_content(content))
            elif isinstance(content, PromptToolResultContent):
                content_blocks.append(
                    await self.convert_tool_result_content(content),
                )
            elif isinstance(content, PromptDocumentContent):
                content_blocks.append(await self.convert_document_content(content))

        return content_blocks

    async def _create_openai_message(
        self,
        role: str,
        content_blocks: list[OpenAIPromptContent],
    ) -> OpenAIPromptMessage:
        """Create an OpenAI message from role and content blocks.

        Args:
            role: The role of the message.
            content_blocks: The content blocks of the message.

        Returns:
            The OpenAI message.
        """
        # Extract text content
        text_content = ""
        for block in content_blocks:
            if block.type == "text" and block.text is not None:
                text_content += block.text + "\n"

        # Filter out text blocks (they're combined in the content field)
        filtered_content_blocks = [
            block for block in content_blocks if block.type != "text"
        ]

        return OpenAIPromptMessage(
            role=await self._reverse_role_map(role),
            content=text_content,
            content_list=filtered_content_blocks,
        )

    async def _convert_system_instruction(
        self,
        system_instruction: str | None,
    ) -> list[OpenAIPromptMessage]:
        """Convert system instruction to OpenAI message format.

        Args:
            system_instruction: The system instruction to convert.

        Returns:
            The converted system instruction.
        """
        if system_instruction is None:
            return []

        return [OpenAIPromptMessage(role="system", content=system_instruction)]

    async def _convert_tools(
        self,
        tools: list[ToolDefinition],
    ) -> list[OpenAIPromptToolSpec]:
        """Convert tool definitions to OpenAI tool spec format.

        Args:
            tools: The list of tool definitions to convert.

        Returns:
            The list of OpenAI tool specs.
        """
        converted_tools: list[OpenAIPromptToolSpec] = []
        for tool in tools:
            tool_spec = OpenAIPromptToolSpec(
                type="function",
                name=tool.name,
                description=tool.description,
                input_schema=tool.input_schema,
            )
            converted_tools.append(tool_spec)
        return converted_tools

    async def convert_prompt(self, prompt: Prompt) -> OpenAIPrompt:
        """Convert a prompt to OpenAI format.

        Args:
            prompt: The prompt to convert.

        Returns:
            The converted prompt.
        """
        messages = await self._convert_messages(prompt.finalized_messages)
        system = await self._convert_system_instruction(prompt.system_instruction)
        if system and len(system) > 0:
            messages.insert(0, system[0])
        # Convert tools if present
        tools = None
        if prompt.tools:
            tools = await self._convert_tools(prompt.tools)
        return OpenAIPrompt(
            messages=messages,
            tools=tools,
            temperature=prompt.temperature or 0.0,
            top_p=prompt.top_p or 1.0,
            max_tokens=prompt.max_output_tokens or 4096,
        )
