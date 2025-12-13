import base64
import logging
from typing import Any

import httpx

from agent_platform.core.kernel_interfaces.kernel_mixin import UsesKernelMixin
from agent_platform.core.platforms.base import PlatformConverters
from agent_platform.core.platforms.reducto.prompts import ReductoPrompt
from agent_platform.core.prompts import (
    Prompt,
    PromptAudioContent,
    PromptImageContent,
    PromptTextContent,
    PromptToolResultContent,
    PromptToolUseContent,
)
from agent_platform.core.prompts.content.document import PromptDocumentContent

logger = logging.getLogger(__name__)


class ReductoConverters(PlatformConverters, UsesKernelMixin):
    """Converters that transform agent-server prompt types to Reducto types."""

    async def convert_text_content(
        self,
        content: PromptTextContent,
    ) -> dict[str, Any]:
        raise ValueError("Reducto does not support text")

    async def convert_image_content(
        self,
        content: PromptImageContent,
    ) -> dict[str, Any]:
        raise ValueError("Reducto does not support images")

    async def convert_audio_content(
        self,
        content: PromptAudioContent,
    ) -> dict[str, Any]:
        raise ValueError("Reducto does not support audio")

    async def convert_tool_use_content(
        self,
        content: PromptToolUseContent,
    ) -> dict[str, Any]:
        raise ValueError("Reducto does not support tool use")

    async def convert_tool_result_content(
        self,
        content: PromptToolResultContent,
    ) -> dict[str, Any]:
        raise ValueError("Reducto does not support tool results")

    async def convert_document_content(
        self,
        content: PromptDocumentContent,
    ) -> tuple[str, bytes]:
        # Need to get (filename, bytes)
        if content.sub_type == "UploadedFile":
            raise NotImplementedError("UploadedFile sub-type not supported yet")
        elif content.sub_type == "base64" and isinstance(content.value, str):
            return (content.name, base64.b64decode(content.value))
        elif content.sub_type == "raw_bytes" and isinstance(content.value, bytes):
            return (content.name, content.value)
        elif content.sub_type == "url" and isinstance(content.value, str):
            # Fetch the file and get the bytes
            async with httpx.AsyncClient() as client:
                response = await client.get(content.value)
                return (content.name, response.content)
        else:
            raise ValueError(
                f"Unsupported document content sub-type / value: {content.sub_type} / {type(content.value)}",
            )

    async def convert_prompt(
        self,
        prompt: Prompt,
        model_id: str | None = None,
    ) -> ReductoPrompt:
        """Convert a prompt to Reducto's format.

        Args:
            prompt: The prompt to convert.
            model_id: Optional model ID.

        Returns:
            The converted prompt.
        """
        # We expect a single message with a single content item
        # which is a document content item
        if len(prompt.finalized_messages) != 1:
            raise ValueError("Expected a single message with a single content item")
        if len(prompt.finalized_messages[0].content) != 1:
            raise ValueError(
                "Expected a single content item in the message",
            )
        if not isinstance(
            prompt.finalized_messages[0].content[0],
            PromptDocumentContent,
        ):
            raise ValueError(
                "Expected a document content item in the message",
            )

        file_name, _document_bytes = await self.convert_document_content(
            prompt.finalized_messages[0].content[0],
        )

        if prompt.tools:
            raise ValueError("Tools cannot be used with Reducto")

        op = "extract"
        if (model_id or "").endswith("-parse"):
            op = "parse"
        elif (model_id or "").endswith("-classify"):
            op = "classify"

        return ReductoPrompt(
            operation=op,
            system_prompt=prompt.system_instruction,
            file_name=file_name,
        )
