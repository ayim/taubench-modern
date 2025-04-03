import json
from collections.abc import Sequence
from typing import Any, Literal, cast

from openai.types import FunctionDefinition
from openai.types.chat import (
    ChatCompletionAssistantMessageParam,
    ChatCompletionContentPartTextParam,
    ChatCompletionMessageParam,
    ChatCompletionMessageToolCall,
    ChatCompletionSystemMessageParam,
    ChatCompletionToolMessageParam,
    ChatCompletionToolParam,
    ChatCompletionUserMessageParam,
)
from openai.types.chat.chat_completion_message_tool_call import Function

from agent_platform.core.kernel_interfaces.kernel_mixin import UsesKernelMixin
from agent_platform.core.platforms.base import PlatformConverters
from agent_platform.core.platforms.openai.configs import OpenAIRoleMap
from agent_platform.core.platforms.openai.prompts import OpenAIPrompt
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
    ) -> ChatCompletionContentPartTextParam:
        """Converts text content to OpenAI format."""
        return {
            "type": "text",
            "text": content.text,
        }

    async def convert_image_content(
        self,
        content: PromptImageContent,
    ) -> dict[str, Any]:
        """Converts image content to OpenAI format."""
        raise NotImplementedError("Image not supported yet")

    async def convert_audio_content(
        self,
        content: PromptAudioContent,
    ) -> dict[str, Any]:
        """Converts audio content to OpenAI format."""
        raise NotImplementedError("Audio not supported yet")

    async def convert_tool_use_content(
        self,
        content: PromptToolUseContent,
    ) -> ChatCompletionMessageToolCall:
        """Converts tool use content to OpenAI format."""
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
    ) -> ChatCompletionToolMessageParam:
        """Converts tool result content to OpenAI format.

        Args:
            content: The tool result content to convert.

        Returns:
            A tool message parameter for the OpenAI API.
        """
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
        # that conforms to OpenAI's expectations
        return {
            "role": "tool",
            "tool_call_id": content.tool_call_id,
            "content": text_content.strip(),
        }

    async def convert_document_content(
        self,
        content: PromptDocumentContent,
    ) -> dict[str, Any]:
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

    def _create_openai_message_param(
        self,
        role: str,
        content: str,
        tool_calls: list[dict[str, Any]] | None = None,
    ) -> ChatCompletionMessageParam:
        """Create an OpenAI message parameter based on role.

        Args:
            role: The role of the message.
            content: The content of the message.
            tool_calls: Optional list of tool calls.

        Returns:
            A message parameter for the OpenAI API.
        """
        if role == "system":
            return ChatCompletionSystemMessageParam(role=role, content=content)
        elif role == "user":
            return ChatCompletionUserMessageParam(role=role, content=content)
        elif role == "assistant":
            message: dict[str, Any] = {"role": role, "content": content}
            if tool_calls:
                message["tool_calls"] = tool_calls
            return cast(ChatCompletionAssistantMessageParam, message)
        else:
            raise ValueError(f"Unsupported role: {role}")

    async def _convert_messages(
        self,
        messages: list[PromptUserMessage | PromptAgentMessage],
    ) -> list[ChatCompletionMessageParam]:
        """Convert prompt messages to OpenAI message format.

        Args:
            messages: The list of prompt messages to convert.

        Returns:
            The list of OpenAI message parameters.
        """
        converted_messages: list[ChatCompletionMessageParam] = []

        for message in messages:
            # Check for tool results first since they need special handling
            has_tool_results = any(
                isinstance(content_item, PromptToolResultContent)
                for content_item in message.content
            )

            # If this is a user message with only tool results,
            # we want to convert directly to a tool message
            if (
                has_tool_results
                and isinstance(message, PromptUserMessage)
                and len(message.content) == 1
            ):
                tool_result = next(
                    (
                        item
                        for item in message.content
                        if isinstance(item, PromptToolResultContent)
                    ),
                    None,
                )
                if tool_result:
                    tool_message = await self.convert_tool_result_content(tool_result)
                    converted_messages.append(tool_message)
                    continue

            # Process the message content to get text and tool components
            processed_content = await self._process_message_content(message.content)

            # Get the appropriate OpenAI role
            openai_role = await self._reverse_role_map(message.role)

            # Create the message
            message_dict = {
                "role": openai_role,
                "content": processed_content["text"],
            }

            # Add tool calls for assistant messages if needed
            if openai_role == "assistant" and processed_content["tool_calls"]:
                tool_calls = [
                    {
                        "id": tool_call.id,
                        "type": "function",
                        "function": {
                            "name": tool_call.function.name,
                            "arguments": tool_call.function.arguments,
                        },
                    }
                    for tool_call in processed_content["tool_calls"]
                ]
                message_dict["tool_calls"] = tool_calls

                # Set content to empty string when there are tool calls but no text
                if not processed_content["text"]:
                    message_dict["content"] = ""

            # Convert to the proper message type
            formatted_message = self._create_openai_message_param(
                role=openai_role,
                content=message_dict["content"],
                tool_calls=message_dict.get("tool_calls"),
            )

            converted_messages.append(formatted_message)

            # Add tool result messages that follow a tool use
            for content_item in message.content:
                if isinstance(content_item, PromptToolResultContent):
                    tool_message = await self.convert_tool_result_content(content_item)
                    converted_messages.append(tool_message)

        return converted_messages

    async def _convert_system_instruction_to_openai(
        self,
        system_instruction: str | None,
    ) -> list[ChatCompletionMessageParam]:
        """Convert system instruction to OpenAI message format.

        Args:
            system_instruction: The system instruction to convert.

        Returns:
            The converted system instruction.
        """
        if system_instruction is None:
            return []

        system_message = self._create_openai_message_param(
            role="system",
            content=system_instruction,
        )

        return [system_message]

    async def _convert_tools(
        self,
        tools: list[ToolDefinition],
    ) -> list[ChatCompletionToolParam]:
        """Convert tool definitions to OpenAI tool parameters.

        Args:
            tools: The list of tool definitions to convert.

        Returns:
            The list of OpenAI tool parameters.
        """
        converted_tools: list[ChatCompletionToolParam] = []
        for tool in tools:
            function_def = FunctionDefinition(
                name=tool.name,
                description=tool.description,
                parameters=tool.input_schema,
            )
            tool_param = cast(
                ChatCompletionToolParam,
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

    async def convert_prompt(self, prompt: Prompt) -> OpenAIPrompt:
        """Convert a prompt to OpenAI format.

        Args:
            prompt: The prompt to convert.

        Returns:
            The converted prompt.
        """
        # Convert messages and system instruction
        messages = await self._convert_messages(prompt.finalized_messages)
        system = await self._convert_system_instruction_to_openai(
            prompt.system_instruction,
        )

        # Add system message at the beginning if present
        all_messages = list(messages)
        if system and len(system) > 0:
            all_messages.insert(0, system[0])

        # Convert tools if present
        tools = None
        if prompt.tools:
            tools = await self._convert_tools(prompt.tools)

        return OpenAIPrompt(
            messages=all_messages,
            tools=tools,
            temperature=prompt.temperature or 0.0,
            top_p=prompt.top_p or 1.0,
            max_tokens=prompt.max_output_tokens or 4096,
        )
