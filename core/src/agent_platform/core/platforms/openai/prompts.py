from dataclasses import dataclass
from typing import Any

from agent_platform.core.platforms.base import PlatformPrompt
from agent_platform.core.prompts import (
    Prompt,
    PromptAudioContent,
    PromptImageContent,
    PromptMessage,
    PromptMessageContent,
    PromptTextContent,
    PromptToolResultContent,
    PromptToolUseContent,
)


@dataclass(frozen=True)
class OpenAIPrompt(PlatformPrompt):
    """OpenAI platform prompt."""

    prompt: Prompt
    """The prompt to format."""

    def _convert_text_content(self, msg_content: PromptTextContent) -> dict[str, Any]:
        """Convert text content to OpenAI format.

        Args:
            msg_content: Text content to convert.

        Returns:
            OpenAI formatted text content.
        """
        return {
            "type": "text",
            "text": msg_content.text,
        }

    def _convert_image_content(self, msg_content: PromptImageContent) -> dict[str, Any]:
        """Convert image content to OpenAI format.

        Args:
            msg_content: Image content to convert.

        Returns:
            OpenAI formatted image content.
        """
        image_url = {}
        if msg_content.sub_type == "url":
            image_url["url"] = msg_content.value
        elif msg_content.sub_type == "base64":
            image_url["url"] = (
                f"data:{msg_content.mime_type};base64,{msg_content.value}"
            )
        else:  # raw_bytes
            image_url["url"] = (
                f"data:{msg_content.mime_type};base64,{msg_content.value_bytes.decode()}"
            )

        if msg_content.detail:
            image_url["detail"] = msg_content.detail

        return {
            "type": "image_url",
            "image_url": image_url,
        }

    def _convert_audio_content(self, msg_content: PromptAudioContent) -> dict[str, Any]:
        """Convert audio content to OpenAI format.

        Args:
            msg_content: Audio content to convert.

        Returns:
            OpenAI formatted audio content.
        """
        url = (
            msg_content.value
            if msg_content.sub_type == "url"
            else f"data:{msg_content.mime_type};base64,{msg_content.value}"
        )
        return {
            "type": "audio_url",
            "audio_url": {"url": url},
        }

    def _convert_message_content(
        self,
        msg_content: PromptMessageContent,
    ) -> dict[str, Any] | None:
        """Convert message content to OpenAI format.

        Args:
            msg_content: Message content to convert.

        Returns:
            OpenAI formatted content or None if content type is not supported.
        """
        if isinstance(msg_content, PromptTextContent):
            return self._convert_text_content(msg_content)
        elif isinstance(msg_content, PromptImageContent):
            return self._convert_image_content(msg_content)
        elif isinstance(msg_content, PromptAudioContent):
            return self._convert_audio_content(msg_content)
        elif isinstance(msg_content, PromptToolUseContent | PromptToolResultContent):
            # Tool-related content is handled separately
            return None
        return None

    def _convert_message(self, message: PromptMessage) -> dict[str, Any]:
        """Convert a message to OpenAI format.

        Args:
            message: Message to convert.

        Returns:
            OpenAI formatted message.
        """
        content = []
        for msg_content in message.content:
            converted_content = self._convert_message_content(msg_content)
            if converted_content:
                content.append(converted_content)

        if not content:
            return {}

        # Map our internal roles to OpenAI roles
        role_map = {
            "user": "user",
            "agent": "assistant",
        }
        openai_role = role_map.get(message.role, message.role)

        return {
            "role": openai_role,
            "content": content,
        }

    def _build_messages(self) -> list[dict[str, Any]]:
        """Build OpenAI messages from the prompt.

        Returns:
            List of OpenAI formatted messages.
        """
        messages = []
        if self.prompt.system_instruction:
            messages.append(
                {
                    "role": "system",
                    "content": self.prompt.system_instruction,
                },
            )

        for message in self.prompt.finalized_messages:
            converted_message = self._convert_message(message)
            if converted_message:
                messages.append(converted_message)

        return messages

    def _build_tools(self) -> list[dict[str, Any]] | None:
        """Build OpenAI tools configuration.

        Returns:
            OpenAI tools configuration or None if no tools are present.
        """
        if not self.prompt.tools:
            return None

        tools = [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.input_schema,
                },
            }
            for tool in self.prompt.tools
        ]

        return tools

    def _build_tool_choice(self) -> dict[str, Any] | None:
        """Build OpenAI tool choice configuration.

        Returns:
            OpenAI tool choice configuration or None if no tool choice is specified.
        """
        if self.prompt.tool_choice not in ["auto", "any"]:
            return {
                "type": "function",
                "function": {"name": self.prompt.tool_choice},
            }
        return None

    def _build_additional_fields(self) -> dict[str, Any]:
        """Build additional OpenAI request fields.

        Returns:
            Dictionary of additional fields.
        """
        fields = {}
        if self.prompt.temperature is not None:
            fields["temperature"] = self.prompt.temperature
        if self.prompt.max_output_tokens is not None:
            fields["max_tokens"] = self.prompt.max_output_tokens
        if self.prompt.top_p is not None:
            fields["top_p"] = self.prompt.top_p
        if self.prompt.stop_sequences:
            fields["stop"] = self.prompt.stop_sequences
        return fields

    def as_platform_request(self, model: str, stream: bool = False) -> dict[str, Any]:
        """Convert the prompt to an OpenAI request.

        Args:
            model: The OpenAI model ID to use.
            stream: Whether to generate a stream request.

        Returns:
            An OpenAI request.
        """
        request = {
            "model": model,
            "messages": self._build_messages(),
            "stream": stream,
        }

        # Add tools if present
        tools = self._build_tools()
        if tools:
            request["tools"] = tools

        # Add tool choice if specified
        tool_choice = self._build_tool_choice()
        if tool_choice:
            request["tool_choice"] = tool_choice

        # Add additional fields
        request.update(self._build_additional_fields())

        return request
