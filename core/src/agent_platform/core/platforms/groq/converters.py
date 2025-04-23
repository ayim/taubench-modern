import json
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Literal, cast

if TYPE_CHECKING:
    from groq.types.chat import (
        ChatCompletionContentPartTextParam,
        ChatCompletionMessageParam,
        ChatCompletionMessageToolCall,
        ChatCompletionMessageToolCallParam,
        ChatCompletionToolMessageParam,
        ChatCompletionToolParam,
    )

from agent_platform.core.kernel_interfaces.kernel_mixin import UsesKernelMixin
from agent_platform.core.platforms.base import PlatformConverters
from agent_platform.core.platforms.groq.configs import GroqRoleMap
from agent_platform.core.platforms.groq.prompts import GroqPrompt
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


class GroqConverters(PlatformConverters, UsesKernelMixin):
    """Converters that transform agent-server prompt types to Groq types."""

    async def convert_text_content(
        self,
        content: PromptTextContent,
    ) -> "ChatCompletionContentPartTextParam":
        """Converts text content to Groq format."""
        return {
            "type": "text",
            "text": content.text,
        }

    async def convert_image_content(
        self,
        content: PromptImageContent,
    ) -> dict[str, Any]:
        """Converts image content to Groq format."""
        raise NotImplementedError("Image not supported yet")

    async def convert_audio_content(
        self,
        content: PromptAudioContent,
    ) -> dict[str, Any]:
        """Converts audio content to Groq format."""
        raise NotImplementedError("Audio not supported yet")

    async def convert_tool_use_content(
        self,
        content: PromptToolUseContent,
    ) -> "ChatCompletionMessageToolCall":
        """Converts tool use content to Groq format."""
        from groq.types.chat import ChatCompletionMessageToolCall
        from groq.types.chat.chat_completion_message_tool_call import Function

        return ChatCompletionMessageToolCall(
            id=content.tool_call_id,
            type="function",
            function=Function(
                name=content.tool_name,
                arguments=json.dumps(content.tool_input),
            ),
        )

    async def convert_tool_result_content(
        self,
        content: PromptToolResultContent,
    ) -> "ChatCompletionToolMessageParam":
        """Converts tool result content to Groq format.

        Args:
            content: The tool result content to convert.

        Returns:
            A tool message parameter for the Groq API.
        """
        from groq.types.chat import ChatCompletionToolMessageParam

        text_content = ""
        for content_item in content.content:
            if isinstance(content_item, PromptTextContent):
                text_content += content_item.text + "\n"
            elif isinstance(content_item, PromptImageContent):
                raise NotImplementedError("Image not supported yet")
            elif isinstance(content_item, PromptAudioContent):
                raise NotImplementedError("Audio not supported yet")
            elif isinstance(content_item, PromptDocumentContent):
                raise NotImplementedError("Document not supported yet")
            else:
                raise ValueError(f"Unsupported content type: {type(content_item)}")

        # Ensure we return a properly formatted tool message
        # that conforms to Groq's expectations
        return ChatCompletionToolMessageParam(
            role="tool",
            tool_call_id=content.tool_call_id,
            content=text_content.strip(),
        )

    async def convert_document_content(
        self,
        content: PromptDocumentContent,
    ) -> dict[str, Any]:
        """Converts document content to Groq format."""
        raise NotImplementedError("Document not supported yet")

    async def _reverse_role_map(self, role: str) -> Literal["user", "assistant"]:
        """Reverse the role map.

        Args:
            role: The role to reverse.

        Returns:
            The corresponding Groq role name.

        Raises:
            ValueError: If the role is not found in the map.
        """
        for groq_role, our_role in GroqRoleMap.role_map.items():
            if our_role == role:
                return cast(Literal["user", "assistant"], groq_role)
        raise ValueError(f"Role '{role}' not found in Groq RoleMap")

    async def _process_message_content(
        self,
        content_list: Sequence[PromptMessageContent],
    ) -> dict[str, Any]:
        """Process prompt message content and organize into text and tool components.

        Args:
            content_list: The list of content to process.

        Returns:
            A dictionary containing text content and tool calls.
        """
        from groq.types.chat import ChatCompletionMessageToolCall

        text_content = ""
        tool_calls: list[ChatCompletionMessageToolCall] = []

        for content in content_list:
            if isinstance(content, PromptTextContent):
                text_content += content.text + "\n"
            elif isinstance(content, PromptToolUseContent):
                tool_call = await self.convert_tool_use_content(content)
                tool_calls.append(tool_call)
            elif isinstance(content, PromptImageContent):
                raise NotImplementedError("Image content not supported yet")
            elif isinstance(content, PromptAudioContent):
                raise NotImplementedError("Audio content not supported yet")
            elif isinstance(content, PromptDocumentContent):
                raise NotImplementedError("Document content not supported yet")
            elif isinstance(content, PromptToolResultContent):
                # Tool results should be separate messages,
                # not part of an assistant message
                continue

        return {
            "text": text_content.strip(),
            "tool_calls": tool_calls,
        }

    def _create_groq_message_param(
        self,
        role: str,
        content: str,
        tool_calls: list["ChatCompletionMessageToolCallParam"] | None = None,
    ) -> "ChatCompletionMessageParam":
        """Create an Groq message parameter based on role.

        Args:
            role: The role of the message.
            content: The content of the message.
            tool_calls: Optional list of tool calls.

        Returns:
            A message parameter for the Groq API.
        """
        from groq.types.chat import (
            ChatCompletionAssistantMessageParam,
            ChatCompletionSystemMessageParam,
            ChatCompletionUserMessageParam,
        )

        if role == "system":
            # Groq's SDK has not yet adopted the Groq deprecation of
            # SystemMessageParam for DeveloperMessageParam.
            return ChatCompletionSystemMessageParam(
                role="system",
                content=content,
            )
        elif role == "user":
            return ChatCompletionUserMessageParam(role=role, content=content)
        elif role == "assistant":
            if tool_calls and len(tool_calls) > 0:
                return ChatCompletionAssistantMessageParam(
                    role=role,
                    content=content,
                    tool_calls=tool_calls,
                )
            else:
                return ChatCompletionAssistantMessageParam(
                    role=role,
                    content=content,
                )
        else:
            raise ValueError(f"Unsupported role: {role}")

    async def _convert_messages(
        self,
        messages: list[PromptUserMessage | PromptAgentMessage],
    ) -> list["ChatCompletionMessageParam"]:
        """Convert prompt messages to Groq message format.

        Args:
            messages: The list of prompt messages to convert.

        Returns:
            The list of Groq message parameters.
        """
        converted_messages: list[ChatCompletionMessageParam] = []

        for message in messages:
            # Process the message content to get text and tool components
            processed_content = await self._process_message_content(message.content)

            # Get the appropriate Groq role
            groq_role = await self._reverse_role_map(message.role)

            # Convert to the proper message type
            formatted_message = self._create_groq_message_param(
                role=groq_role,
                content=processed_content["text"],
                tool_calls=processed_content["tool_calls"],
            )

            # Can't have an empty user message (especially before tool messages, throws
            # off the API which expects tool messages to follow assistant messages)
            if (
                formatted_message["role"] != "user"
                or formatted_message["content"] != ""
            ):
                converted_messages.append(formatted_message)

            # Add tool result messages that follow a tool use
            for content_item in message.content:
                if isinstance(content_item, PromptToolResultContent):
                    tool_message = await self.convert_tool_result_content(content_item)
                    converted_messages.append(tool_message)

        return converted_messages

    async def _convert_system_instruction_to_groq(
        self,
        system_instruction: str | None,
        model_id: str,
    ) -> list["ChatCompletionMessageParam"]:
        """Convert system instruction to Groq message format.

        Args:
            system_instruction: The system instruction to convert.

        Returns:
            The converted system instruction.
        """
        if system_instruction is None:
            return []

        return [
            self._create_groq_message_param(
                role="system",
                content=system_instruction,
            )
        ]

    async def _convert_tools(
        self,
        tools: list[ToolDefinition],
    ) -> list["ChatCompletionToolParam"]:
        """Convert tool definitions to Groq tool parameters.

        Args:
            tools: The list of tool definitions to convert.

        Returns:
            The list of Groq tool parameters.
        """
        from groq.types import FunctionDefinition

        converted_tools: list[ChatCompletionToolParam] = []
        for tool in tools:
            function_def = FunctionDefinition(
                name=tool.name,
                description=tool.description,
                parameters=tool.input_schema,
            )
            tool_param = cast(
                "ChatCompletionToolParam",
                {
                    "type": "function",
                    "function": {
                        "name": function_def.name,
                        "description": function_def.description or "",
                        "parameters": function_def.parameters or {},
                    },
                },
            )
            converted_tools.append(tool_param)
        return converted_tools

    async def convert_prompt(
        self,
        prompt: Prompt,
        model_id: str | None = None,
    ) -> GroqPrompt:
        """Convert a prompt to Groq format.

        Args:
            prompt: The prompt to convert.

        Returns:
            The converted prompt.
        """
        if model_id is None:
            raise ValueError(
                "Groq requires a model_id to be provided to convert a prompt."
                "\nThere are some model-specific changes such as a lack of "
                "system messages for some models.",
            )

        # Convert messages and system instruction
        messages = await self._convert_messages(prompt.finalized_messages)

        system = await self._convert_system_instruction_to_groq(
            prompt.system_instruction,
            model_id,
        )

        # Add system message at the beginning if present
        all_messages = list(messages)
        if system and len(system) > 0:
            for msg in system:
                all_messages.insert(0, msg)

        # Convert tools if present
        tools = None
        if prompt.tools:
            tools = await self._convert_tools(prompt.tools)

        return GroqPrompt(
            messages=all_messages,
            tools=tools,
            temperature=prompt.temperature or 0.0,
            top_p=prompt.top_p or 1.0,
            max_tokens=prompt.max_output_tokens or 4096,
        )
