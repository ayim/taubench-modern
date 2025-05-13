import base64
import json
from collections.abc import Sequence
from typing import TYPE_CHECKING, Literal, cast

import httpx

if TYPE_CHECKING:
    from openai.types.chat import (
        ChatCompletionContentPartImageParam,
        ChatCompletionContentPartInputAudioParam,
        ChatCompletionContentPartParam,
        ChatCompletionContentPartTextParam,
        ChatCompletionMessageParam,
        ChatCompletionMessageToolCallParam,
        ChatCompletionToolMessageParam,
        ChatCompletionToolParam,
    )

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
    ) -> "ChatCompletionContentPartTextParam":
        """Converts text content to OpenAI format."""
        from openai.types.chat import ChatCompletionContentPartTextParam

        return ChatCompletionContentPartTextParam(
            type="text",
            text=content.text,
        )

    async def convert_image_content(
        self,
        content: PromptImageContent,
    ) -> "ChatCompletionContentPartImageParam":
        """Converts image content to OpenAI format."""
        from openai.types.chat import ChatCompletionContentPartImageParam
        from openai.types.chat.chat_completion_content_part_image_param import ImageURL

        detail = "low" if content.detail == "low_res" else "high"

        if content.sub_type == "url" and isinstance(content.value, str):
            return ChatCompletionContentPartImageParam(
                type="image_url",
                image_url=ImageURL(
                    url=content.value,
                    detail=detail,
                ),
            )
        elif content.sub_type == "raw_bytes" and isinstance(content.value, bytes):
            bytes_to_base64 = base64.b64encode(content.value).decode("utf-8")
            as_data_url = f"data:{content.mime_type};base64,{bytes_to_base64}"
            return ChatCompletionContentPartImageParam(
                type="image_url",
                image_url=ImageURL(
                    url=as_data_url,
                    detail=detail,
                ),
            )
        elif content.sub_type == "base64" and isinstance(content.value, str):
            as_data_url = f"data:{content.mime_type};base64,{content.value}"
            return ChatCompletionContentPartImageParam(
                type="image_url",
                image_url=ImageURL(
                    url=as_data_url,
                    detail=detail,
                ),
            )
        else:
            raise ValueError(
                f"Unsupported image content type/value: {content.sub_type} "
                f"/ {type(content.value)}"
            )

    async def convert_audio_content(
        self,
        content: PromptAudioContent,
    ) -> "ChatCompletionContentPartInputAudioParam":
        """Converts audio content to OpenAI format."""
        from openai.types.chat import ChatCompletionContentPartInputAudioParam
        from openai.types.chat.chat_completion_content_part_input_audio_param import (
            InputAudio,
        )

        audio_format = "wav" if content.mime_type == "audio/wav" else "mp3"
        encoded_string = content.value

        if content.sub_type == "url":
            # Now we need to fetch the file and encode it
            async with httpx.AsyncClient() as client:
                response = await client.get(content.value)
                encoded_string = base64.b64encode(response.content).decode("utf-8")

        return ChatCompletionContentPartInputAudioParam(
            type="input_audio",
            input_audio=InputAudio(
                data=encoded_string,
                format=audio_format,
            ),
        )

    async def convert_tool_use_content(
        self,
        content: PromptToolUseContent,
    ) -> "ChatCompletionMessageToolCallParam":
        """Converts tool use content to OpenAI format."""
        from openai.types.chat import ChatCompletionMessageToolCallParam
        from openai.types.chat.chat_completion_message_tool_call_param import (
            Function,
        )

        return ChatCompletionMessageToolCallParam(
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
        """Converts tool result content to OpenAI format.

        Args:
            content: The tool result content to convert.

        Returns:
            A tool message parameter for the OpenAI API.
        """
        from openai.types.chat import ChatCompletionToolMessageParam

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
        return ChatCompletionToolMessageParam(
            role="tool",
            tool_call_id=content.tool_call_id,
            content=text_content.strip(),
        )

    async def convert_document_content(
        self,
        content: PromptDocumentContent,
    ):
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
        for openai_role, our_role in OpenAIRoleMap.role_map.items():
            if our_role == role:
                return cast(Literal["user", "assistant"], openai_role)
        raise ValueError(f"Role '{role}' not found in OpenAIRoleMap")

    async def _process_message_content(
        self,
        content_list: Sequence[PromptMessageContent],
    ) -> tuple[
        list["ChatCompletionContentPartParam"],
        list["ChatCompletionMessageToolCallParam"],
    ]:
        """Process prompt message content and organize into text and tool components.

        Args:
            content_list: The list of content to process.

        Returns:
            A dictionary containing text content and tool calls.
        """
        from openai.types.chat import (
            ChatCompletionContentPartTextParam,
            ChatCompletionMessageToolCallParam,
        )

        content_parts: list[ChatCompletionContentPartParam] = []
        tool_calls: list[ChatCompletionMessageToolCallParam] = []

        for content in content_list:
            last_content_part = content_parts[-1] if len(content_parts) > 0 else None

            match content:
                case PromptTextContent() as text_content:
                    if last_content_part and last_content_part["type"] == "text":
                        last_content_part["text"] += "\n" + text_content.text
                    else:
                        content_parts.append(
                            ChatCompletionContentPartTextParam(
                                type="text",
                                text=text_content.text,
                            )
                        )
                case PromptToolUseContent() as tool_use_content:
                    tool_call = await self.convert_tool_use_content(tool_use_content)
                    tool_calls.append(tool_call)
                case PromptImageContent() as image_content:
                    content_parts.append(
                        await self.convert_image_content(image_content)
                    )
                case PromptAudioContent() as audio_content:
                    content_parts.append(
                        await self.convert_audio_content(audio_content)
                    )
                case PromptDocumentContent():
                    raise NotImplementedError("Document content not supported yet")
                case PromptToolResultContent():
                    # Tool results should be separate messages,
                    # not part of an assistant message
                    continue

        return content_parts, tool_calls

    def _create_openai_message_param(
        self,
        role: str,
        content: list["ChatCompletionContentPartParam"],
        tool_calls: list["ChatCompletionMessageToolCallParam"] | None = None,
    ) -> "ChatCompletionMessageParam":
        """Create an OpenAI message parameter based on role.

        Args:
            role: The role of the message.
            content: The content of the message.
            tool_calls: Optional list of tool calls.

        Returns:
            A message parameter for the OpenAI API.
        """
        from openai.types.chat import (
            ChatCompletionAssistantMessageParam,
            ChatCompletionDeveloperMessageParam,
            ChatCompletionUserMessageParam,
        )

        if role == "system":
            # OpenAI is deprecating "system" in favor of "developer"
            # prompts --- some reasoning models fail in the presence of
            # "system" messages now (04/05/2025)
            return ChatCompletionDeveloperMessageParam(
                role="developer",
                content=[
                    part  # Dev prompt only takes text instructions
                    for part in content
                    if part["type"] == "text"
                ],
            )
        elif role == "user":
            return ChatCompletionUserMessageParam(role=role, content=content)
        elif role == "assistant":
            result = ChatCompletionAssistantMessageParam(
                role=role,
                content=[
                    part  # Assitant only takes text (and refusals it looks like?)
                    for part in content
                    if part["type"] == "text"
                ],
            )
            # If we have tools, add them to the TypedDict
            if tool_calls and len(tool_calls) > 0:
                result["tool_calls"] = tool_calls
            return result
        else:
            raise ValueError(f"Unsupported role: {role}")

    async def _convert_messages(
        self,
        messages: list[PromptUserMessage | PromptAgentMessage],
    ) -> list["ChatCompletionMessageParam"]:
        """Convert prompt messages to OpenAI message format.

        Args:
            messages: The list of prompt messages to convert.

        Returns:
            The list of OpenAI message parameters.
        """
        converted_messages: list[ChatCompletionMessageParam] = []

        for message in messages:
            # Process the message content to get text and tool components
            processed_contents, tool_calls = await self._process_message_content(
                message.content
            )

            # Get the appropriate OpenAI role
            openai_role = await self._reverse_role_map(message.role)

            # Convert to the proper message type
            formatted_message = self._create_openai_message_param(
                role=openai_role,
                content=processed_contents,
                tool_calls=tool_calls,
            )

            # Can't have an empty user message (especially before tool messages, throws
            # off the API which expects tool messages to follow assistant messages)
            not_user_message = formatted_message["role"] != "user"
            user_message_with_content = formatted_message["role"] == "user" and (
                # We only convert to content lists, not plain str
                isinstance(formatted_message["content"], list)
                and len(formatted_message["content"]) > 0
            )
            if not_user_message or user_message_with_content:
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
        model_id: str,
    ) -> list["ChatCompletionMessageParam"]:
        """Convert system instruction to OpenAI message format.

        Args:
            system_instruction: The system instruction to convert.

        Returns:
            The converted system instruction.
        """
        from openai.types.chat import ChatCompletionContentPartTextParam

        if system_instruction is None:
            return []

        if model_id.startswith("o1-mini-"):
            # For o1-mini, the system message is always a user message
            system_message = self._create_openai_message_param(
                role="user",
                content=[
                    ChatCompletionContentPartTextParam(
                        type="text",
                        text=system_instruction,
                    )
                ],
            )
        else:
            system_message = self._create_openai_message_param(
                role="system",
                content=[
                    ChatCompletionContentPartTextParam(
                        type="text",
                        text=system_instruction,
                    )
                ],
            )

        return [system_message]

    async def _convert_tools(
        self,
        tools: list[ToolDefinition],
    ) -> list["ChatCompletionToolParam"]:
        """Convert tool definitions to OpenAI tool parameters.

        Args:
            tools: The list of tool definitions to convert.

        Returns:
            The list of OpenAI tool parameters.
        """
        from openai.types.chat import ChatCompletionToolParam
        from openai.types.shared_params.function_definition import FunctionDefinition

        converted_tools: list[ChatCompletionToolParam] = []
        for tool in tools:
            converted_tools.append(
                ChatCompletionToolParam(
                    type="function",
                    function=FunctionDefinition(
                        name=tool.name,
                        description=tool.description or "",
                        parameters=tool.input_schema or {},
                    ),
                )
            )
        return converted_tools

    async def convert_prompt(
        self,
        prompt: Prompt,
        model_id: str | None = None,
    ) -> OpenAIPrompt:
        """Convert a prompt to OpenAI format.

        Args:
            prompt: The prompt to convert.

        Returns:
            The converted prompt.
        """
        if model_id is None:
            raise ValueError(
                "OpenAI requires a model_id to be provided to convert a prompt."
                "\nThere are some model-specific changes such as a lack of "
                "system messages for some models.",
            )

        # Convert messages and system instruction
        messages = await self._convert_messages(prompt.finalized_messages)

        system = await self._convert_system_instruction_to_openai(
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

        return OpenAIPrompt(
            messages=all_messages,
            tools=tools,
            temperature=prompt.temperature or 0.0,
            top_p=prompt.top_p or 1.0,
            max_tokens=prompt.max_output_tokens or 4096,
        )
