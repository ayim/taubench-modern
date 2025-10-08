from typing import Literal

from agent_platform.core.kernel_interfaces.kernel_mixin import UsesKernelMixin
from agent_platform.core.platforms.base import PlatformConverters
from agent_platform.core.platforms.cortex.prompts import CortexPrompt
from agent_platform.core.platforms.cortex.types import (
    CortexPromptContent,
    CortexPromptMessage,
    CortexPromptToolResults,
    CortexPromptToolSpec,
    CortexPromptToolUse,
)
from agent_platform.core.prompts import Prompt
from agent_platform.core.prompts.content import (
    PromptAudioContent,
    PromptDocumentContent,
    PromptImageContent,
    PromptTextContent,
    PromptToolResultContent,
    PromptToolUseContent,
)
from agent_platform.core.prompts.messages import PromptAgentMessage, PromptUserMessage
from agent_platform.core.tools.tool_definition import ToolDefinition


class CortexConverters(PlatformConverters, UsesKernelMixin):
    """Converters that transform agent-server prompt types to Cortex types."""

    async def convert_text_content(
        self,
        content: PromptTextContent,
    ) -> CortexPromptContent:
        """Converts text content to Cortex format."""
        return CortexPromptContent(
            type="text",
            text=content.text,
        )

    async def convert_image_content(
        self,
        content: PromptImageContent,
    ) -> CortexPromptContent:
        """Converts image content to Cortex format.

        Raises:
            NotImplementedError: Image content is not supported in Cortex.
        """
        raise NotImplementedError("Image content is not supported in Cortex")

    async def convert_audio_content(
        self,
        content: PromptAudioContent,
    ) -> CortexPromptContent:
        """Converts audio content to Cortex format.

        Raises:
            NotImplementedError: Audio content is not supported in Cortex.
        """
        raise NotImplementedError("Audio content is not supported in Cortex")

    async def convert_tool_use_content(
        self,
        content: PromptToolUseContent,
    ) -> CortexPromptContent:
        """Converts tool use content to Cortex format."""
        return CortexPromptContent(
            type="tool_use",
            tool_use=CortexPromptToolUse(
                tool_use_id=content.tool_call_id,
                name=content.tool_name,
                input=content.tool_input,
            ),
        )

    async def convert_tool_result_content(
        self,
        content: PromptToolResultContent,
    ) -> CortexPromptContent:
        """Converts tool result content to Cortex format.

        Handles text, image, audio, and document content types, converting each to the
        appropriate Cortex format (or raising NotImplementedError if not supported).
        """
        result_content: list[CortexPromptContent] = []

        for content_item in content.content:
            if isinstance(content_item, PromptTextContent):
                result_content.append(
                    CortexPromptContent(type="text", text=content_item.text),
                )
            elif isinstance(content_item, PromptImageContent):
                raise NotImplementedError("Image content is not supported in Cortex")
            elif isinstance(content_item, PromptAudioContent):
                raise NotImplementedError("Audio content is not supported in Cortex")
            elif isinstance(content_item, PromptDocumentContent):
                raise NotImplementedError("Document content is not supported in Cortex")
            else:
                raise ValueError(f"Unsupported content type: {type(content_item)}")

        return CortexPromptContent(
            type="tool_results",
            tool_results=CortexPromptToolResults(
                tool_use_id=content.tool_call_id,
                name=content.tool_name,
                content=result_content,
            ),
        )

    async def convert_document_content(
        self,
        content: PromptDocumentContent,
    ) -> CortexPromptContent:
        """Converts document content to Cortex format.

        Raises:
            NotImplementedError: Document content is not supported in Cortex.
        """
        raise NotImplementedError("Document content is not supported in Cortex")

    async def _reverse_role_map(self, role: str) -> Literal["user", "assistant"]:
        """Reverse the role map.

        Args:
            role: The role to reverse.

        Returns:
            The corresponding Cortex role name.

        Raises:
            ValueError: If the role is not found in the map.
        """
        match role:
            case "user":
                return "user"
            case "agent":
                return "assistant"
            case _:
                raise ValueError(f"Unsupported role: {role}")

    async def _convert_messages(  # noqa: C901, PLR0912
        self,
        messages: list[PromptUserMessage | PromptAgentMessage],
    ) -> list[CortexPromptMessage]:
        """Convert prompt messages to Cortex message format.

        Args:
            messages: List of prompt messages to convert.

        Returns:
            List of converted Cortex messages.
        """
        converted_messages: list[CortexPromptMessage] = []

        for message in messages:
            content_blocks: list[CortexPromptContent] = []
            for content in message.content:
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

            # CHOICE: Collect all text content, concat (newline delimited)
            # and then put that into content; the rest remain in content_list
            text_contents = []
            for block in content_blocks:
                if block.type == "text" and block.text is not None:
                    text_contents.append(block.text)

            filtered_content_blocks = [block for block in content_blocks if block.type != "text"]

            converted_messages.append(
                CortexPromptMessage(
                    role=await self._reverse_role_map(message.role),
                    content="\n".join(text_contents),
                    content_list=filtered_content_blocks,
                ),
            )

        # NOTE: cortex does NOT like repeated messages of the same role, so
        # we'll need to go through and "collapse" repeated messages.
        collapsed_messages: list[CortexPromptMessage] = []
        for message in converted_messages:
            if not collapsed_messages or collapsed_messages[-1].role != message.role:
                collapsed_messages.append(message)
            else:
                # NOTE: we'll need to merge the content lists
                collapsed_messages[-1] = CortexPromptMessage(
                    role=message.role,
                    content=(
                        "\n\n".join(
                            [
                                collapsed_messages[-1].content,
                                message.content,
                            ],
                        )
                    ).strip(),
                    content_list=(
                        (collapsed_messages[-1].content_list or []) + (message.content_list or [])
                    ),
                )

        # NOTE: cortex does NOT like messages with empty content
        # This is mostly an issue for tool results, which may be empty
        for i, message in enumerate(collapsed_messages):
            if message.content == "":
                if not message.content_list or len(message.content_list) == 0:
                    raise ValueError("Message has empty content and no content_list")
                elif message.content_list[0].type == "tool_results":
                    collapsed_messages[i] = CortexPromptMessage(
                        role=message.role,
                        content="Tool results:",
                        content_list=message.content_list,
                    )
                else:
                    # This is a bit of a hack, but we really shouldn't hit this
                    collapsed_messages[i] = CortexPromptMessage(
                        role=message.role,
                        content=".",
                        content_list=message.content_list,
                    )

        return collapsed_messages

    async def _convert_system_instruction(
        self,
        system_instruction: str | None,
    ) -> list[CortexPromptMessage]:
        """Convert system instruction to Bedrock system format.

        Args:
            system_instruction: System instruction to convert.

        Returns:
            List containing single system content block with the instruction.
        """
        if system_instruction is None:
            return []

        return [CortexPromptMessage(role="system", content=system_instruction)]

    async def _convert_tools(
        self,
        tools: list[ToolDefinition],
    ) -> list[CortexPromptToolSpec]:
        """Convert tool definitions to Cortex tool format.

        Args:
            tools: List of tool definitions to convert.

        Returns:
            List of converted Cortex tools.
        """
        converted_tools: list[CortexPromptToolSpec] = []
        for tool in tools:
            tool_spec = CortexPromptToolSpec(
                type="generic",
                name=tool.name,
                description=tool.description,
                input_schema=tool.input_schema,
            )
            converted_tools.append(tool_spec)
        return converted_tools

    async def convert_prompt(
        self,
        prompt: Prompt,
        model_id: str | None = None,
    ) -> CortexPrompt:
        """Converts a prompt to Cortex format.

        Args:
            prompt: The prompt to convert.

        Returns:
            A CortexPrompt instance with all converted fields.

        Raises:
            ValueError: If any content in the prompt exceeds Cortex's limits.
        """
        messages = await self._convert_messages(prompt.finalized_messages)
        system = await self._convert_system_instruction(prompt.system_instruction)
        if system and len(system) > 0:
            messages.insert(0, system[0])

        # Convert tools if present
        tools = None
        if prompt.tools:
            tools = await self._convert_tools(prompt.tools)

        return CortexPrompt(
            messages=messages,
            tools=tools,
            temperature=prompt.temperature or 0.0,
            top_p=prompt.top_p or 1.0,
            max_tokens=prompt.max_output_tokens or 4096,
        )
