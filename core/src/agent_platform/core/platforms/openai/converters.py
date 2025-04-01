from typing import Any

from agent_platform.core.kernel_interfaces.kernel_mixin import UsesKernelMixin
from agent_platform.core.platforms.base import PlatformConverters
from agent_platform.core.platforms.openai.prompts import OpenAIPrompt
from agent_platform.core.prompts import Prompt
from agent_platform.core.prompts.content import (
    PromptAudioContent,
    PromptDocumentContent,
    PromptImageContent,
    PromptTextContent,
    PromptToolResultContent,
    PromptToolUseContent,
)


class OpenAIConverters(PlatformConverters, UsesKernelMixin):
    """Converters that transform agent-server prompt types to OpenAI types."""

    async def convert_text_content(
        self,
        content: PromptTextContent,
    ) -> dict[str, Any]:
        """Convert text content to OpenAI format."""
        return {
            "type": "text",
            "text": content.text,
        }

    async def convert_image_content(
        self,
        content: PromptImageContent,
    ) -> dict[str, Any]:
        """Convert image content to OpenAI format."""
        if content.sub_type == "url":
            return {
                "type": "image_url",
                "image_url": {
                    "url": content.value,
                    "detail": content.detail,
                },
            }
        elif content.sub_type == "base64":
            return {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{content.mime_type};base64,{content.value}",
                    "detail": content.detail,
                },
            }
        else:  # raw_bytes
            return {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{content.mime_type};base64,\
                        {content.value_bytes.decode()}",
                    "detail": content.detail,
                },
            }

    async def convert_audio_content(
        self,
        content: PromptAudioContent,
    ) -> dict[str, Any]:
        """Convert audio content to OpenAI format."""
        if content.sub_type == "url":
            return {
                "type": "audio_url",
                "audio_url": {
                    "url": content.value,
                },
            }
        elif content.sub_type == "base64":
            return {
                "type": "audio_url",
                "audio_url": {
                    "url": f"data:{content.mime_type};base64,{content.value}",
                },
            }
        else:
            raise ValueError(f"Unsupported audio sub_type: {content.sub_type}")

    async def convert_tool_use_content(
        self,
        content: PromptToolUseContent,
    ) -> dict[str, Any]:
        """Convert tool use content to OpenAI format."""
        return {
            "type": "function_call",
            "function_call": {
                "name": content.tool_name,
                "arguments": content.tool_input,
            },
        }

    async def convert_tool_result_content(
        self,
        content: PromptToolResultContent,
    ) -> dict[str, Any]:
        """Convert tool result content to OpenAI format."""
        # Find the first text content in the result
        text_content = next(
            (item for item in content.content if isinstance(item, PromptTextContent)),
            None,
        )
        output = text_content.text if text_content else None

        return {
            "type": "function_call_result",
            "function_call_result": {
                "name": content.tool_name,
                "output": output,
            },
        }

    async def convert_document_content(
        self,
        content: PromptDocumentContent,
    ) -> dict[str, Any]:
        """Convert document content to OpenAI format."""
        if content.sub_type == "url":
            return {
                "type": "document_url",
                "document_url": {
                    "url": content.value,
                    "name": content.name,
                },
            }
        elif content.sub_type == "base64":
            return {
                "type": "document_url",
                "document_url": {
                    "url": f"data:{content.mime_type};base64,{content.value}",
                    "name": content.name,
                },
            }
        else:
            raise ValueError(f"Unsupported document sub_type: {content.sub_type}")

    async def convert_prompt(self, prompt: Prompt) -> OpenAIPrompt:
        """Convert a prompt to OpenAI format.

        Args:
            prompt: The prompt to convert.

        Returns:
            An OpenAIPrompt instance.
        """
        return OpenAIPrompt(prompt=prompt)
