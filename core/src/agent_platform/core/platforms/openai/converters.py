import json
from typing import Any, Literal, cast

from openai.types import FunctionDefinition
from openai.types.chat import ChatCompletionMessageToolCall
from openai.types.chat.chat_completion_message_tool_call import Function

from agent_platform.core.kernel_interfaces.kernel_mixin import UsesKernelMixin
from agent_platform.core.platforms.base import PlatformConverters
from agent_platform.core.platforms.openai.adapters import (
    format_message_for_api,
)
from agent_platform.core.platforms.openai.configs import OpenAIRoleMap
from agent_platform.core.platforms.openai.prompts import OpenAIPrompt
from agent_platform.core.platforms.openai.types import (
    OpenAIPromptContent,
    OpenAIPromptToolResults,
)
from agent_platform.core.prompts import (
    Prompt,
    PromptAgentMessage,
    PromptAudioContent,
    PromptImageContent,
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
        tool_call = ChatCompletionMessageToolCall(
            id=content.tool_call_id,
            type="function",
            function=Function(
                name=content.tool_name,
                arguments=json.dumps(content.tool_input),
            ),
        )

        return OpenAIPromptContent(
            type="tool_use",
            tool_use=tool_call,
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

    async def _convert_messages_to_openai(
        self,
        messages: list[PromptUserMessage | PromptAgentMessage],
    ) -> list[dict[str, Any]]:
        """Convert prompt messages to OpenAI message format.

        Args:
            messages: The list of prompt messages to convert.

        Returns:
            The list of OpenAI message dictionaries.
        """
        converted_messages: list[dict[str, Any]] = []

        for message in messages:
            # Get content as a string
            content = ""
            for content_item in message.content:
                if isinstance(content_item, PromptTextContent):
                    content += content_item.text + "\n"

            # Get role
            openai_role = await self._reverse_role_map(message.role)

            # Create formatted message
            formatted_message = format_message_for_api(
                role=openai_role,
                content=content.strip(),
            )

            converted_messages.append(formatted_message)

        return converted_messages

    async def _convert_system_instruction_to_openai(
        self,
        system_instruction: str | None,
    ) -> list[dict[str, Any]]:
        """Convert system instruction to OpenAI message format.

        Args:
            system_instruction: The system instruction to convert.

        Returns:
            The converted system instruction.
        """
        if system_instruction is None:
            return []

        system_message = format_message_for_api(
            role="system",
            content=system_instruction,
        )

        return [system_message]

    async def _convert_tools(
        self,
        tools: list[ToolDefinition],
    ) -> list[FunctionDefinition]:
        """Convert tool definitions to OpenAI function definitions.

        Args:
            tools: The list of tool definitions to convert.

        Returns:
            The list of OpenAI function definitions.
        """
        converted_tools: list[FunctionDefinition] = []
        for tool in tools:
            function_def = FunctionDefinition(
                name=tool.name,
                description=tool.description,
                parameters=tool.input_schema,
            )
            converted_tools.append(function_def)
        return converted_tools

    async def convert_prompt(self, prompt: Prompt) -> OpenAIPrompt:
        """Convert a prompt to OpenAI format.

        Args:
            prompt: The prompt to convert.

        Returns:
            The converted prompt.
        """
        # Use the new message conversion method
        messages = await self._convert_messages_to_openai(prompt.finalized_messages)
        system = await self._convert_system_instruction_to_openai(
            prompt.system_instruction,
        )
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
