import base64
import json
from collections.abc import Sequence
from typing import TYPE_CHECKING

from agent_platform.core.prompts.content.reasoning import PromptReasoningContent

if TYPE_CHECKING:
    from openai.types.responses import (
        ResponseFunctionToolCallParam,
        ResponseInputContentParam,
        ResponseInputImageParam,
        ResponseInputItemParam,
        ResponseInputTextParam,
        ToolParam,
    )
    from openai.types.responses.response_input_param import FunctionCallOutput
    from openai.types.shared_params import ReasoningEffort

from agent_platform.core.kernel_interfaces.kernel_mixin import UsesKernelMixin
from agent_platform.core.platforms.base import PlatformConverters
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
    ) -> "ResponseInputTextParam":
        """Converts text content to OpenAI format."""
        from openai.types.responses import ResponseInputTextParam

        return ResponseInputTextParam(
            type="input_text",
            text=content.text,
        )

    async def convert_image_content(
        self,
        content: PromptImageContent,
    ) -> "ResponseInputImageParam":
        """Converts image content to OpenAI format."""
        from openai.types.responses import ResponseInputImageParam

        detail = "low" if content.detail == "low_res" else "high"

        if content.sub_type == "url" and isinstance(content.value, str):
            return ResponseInputImageParam(
                type="input_image",
                image_url=content.value,
                detail=detail,
            )
        elif content.sub_type == "raw_bytes" and isinstance(content.value, bytes):
            bytes_to_base64 = base64.b64encode(content.value).decode("utf-8")
            as_data_url = f"data:{content.mime_type};base64,{bytes_to_base64}"
            return ResponseInputImageParam(
                type="input_image",
                image_url=as_data_url,
                detail=detail,
            )
        elif content.sub_type == "base64" and isinstance(content.value, str):
            as_data_url = f"data:{content.mime_type};base64,{content.value}"
            return ResponseInputImageParam(
                type="input_image",
                image_url=as_data_url,
                detail=detail,
            )
        else:
            raise ValueError(
                f"Unsupported image content type/value: {content.sub_type} / {type(content.value)}"
            )

    async def convert_audio_content(
        self,
        content: PromptAudioContent,
    ) -> None:
        """Converts audio content to OpenAI format."""
        raise NotImplementedError("Audio not supported in Responses API yet")
        # from openai.types.chat import ChatCompletionContentPartInputAudioParam
        # from openai.types.chat.chat_completion_content_part_input_audio_param import (
        #     InputAudio,
        # )

        # audio_format = "wav" if content.mime_type == "audio/wav" else "mp3"
        # encoded_string = content.value

        # if content.sub_type == "url":
        #     # Now we need to fetch the file and encode it
        #     async with httpx.AsyncClient() as client:
        #         response = await client.get(content.value)
        #         encoded_string = base64.b64encode(response.content).decode("utf-8")

        # return ChatCompletionContentPartInputAudioParam(
        #     type="input_audio",
        #     input_audio=InputAudio(
        #         data=encoded_string,
        #         format=audio_format,
        #     ),
        # )

    async def convert_tool_use_content(
        self,
        content: PromptToolUseContent,
    ) -> "ResponseFunctionToolCallParam":
        """Converts tool use content to OpenAI format."""
        from openai.types.responses import ResponseFunctionToolCallParam

        return ResponseFunctionToolCallParam(
            type="function_call",
            call_id=content.tool_call_id,
            name=content.tool_name,
            arguments=json.dumps(content.tool_input),
        )

    async def convert_tool_result_content(
        self,
        content: PromptToolResultContent,
    ) -> "FunctionCallOutput":
        """Converts tool result content to OpenAI format.

        Args:
            content: The tool result content to convert.

        Returns:
            A tool message parameter for the OpenAI API.
        """
        from openai.types.responses.response_input_param import FunctionCallOutput

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
        return FunctionCallOutput(
            type="function_call_output",
            call_id=content.tool_call_id,
            output=text_content.strip(),
        )

    async def convert_document_content(
        self,
        content: PromptDocumentContent,
    ):
        """Converts document content to OpenAI format."""
        raise NotImplementedError("Document not supported yet")

    async def _process_user_message_content(
        self,
        content_list: Sequence[PromptMessageContent],
    ) -> tuple[list["ResponseInputContentParam"], list["FunctionCallOutput"]]:
        """Process prompt message content and organize into text and tool components.

        Args:
            content_list: The list of content to process.

        Returns:
            A dictionary containing text content and tool calls.
        """
        from openai.types.responses import ResponseInputContentParam, ResponseInputTextParam

        content_parts: list[ResponseInputContentParam] = []
        tool_results: list[FunctionCallOutput] = []

        for content in content_list:
            last_content_part = content_parts[-1] if len(content_parts) > 0 else None

            match content:
                case PromptTextContent() as text_content:
                    if (
                        last_content_part
                        and "type" in last_content_part
                        and last_content_part["type"] == "input_text"
                    ):
                        last_content_part["text"] += text_content.text
                    else:
                        content_parts.append(
                            ResponseInputTextParam(
                                type="input_text",
                                text=text_content.text,
                            )
                        )
                case PromptToolResultContent() as tool_result_content:
                    tool_results.append(await self.convert_tool_result_content(tool_result_content))
                case PromptImageContent() as image_content:
                    content_parts.append(await self.convert_image_content(image_content))
                case PromptAudioContent():
                    raise NotImplementedError("Audio not supported yet")
                case PromptDocumentContent():
                    raise NotImplementedError("Document content not supported yet")

        return content_parts, tool_results

    async def _convert_messages(  # noqa: PLR0912, C901
        self,
        messages: list[PromptUserMessage | PromptAgentMessage],
    ) -> list["ResponseInputItemParam"]:
        """Convert prompt messages to OpenAI message format.

        Args:
            messages: The list of prompt messages to convert.

        Returns:
            The list of OpenAI message parameters.
        """
        from openai.types.responses import (
            EasyInputMessageParam,
            ResponseInputItemParam,
            ResponseOutputTextParam,
            ResponseReasoningItemParam,
        )
        from openai.types.responses.response_reasoning_item_param import Content, Summary

        converted_messages: list[ResponseInputItemParam] = []

        for message in messages:
            match message.role:
                case "user":
                    content_parts, tool_results = await self._process_user_message_content(
                        message.content,
                    )
                    if content_parts:
                        converted_messages.append(
                            EasyInputMessageParam(
                                role="user",
                                content=content_parts,
                            )
                        )
                    # Tool call results must be top-level input items so that the Responses API can
                    # match them by call_id.
                    # We're going to want to look in converted messages (iterating backwards)
                    # finding the matching call for each result and inserting the result right
                    # after the call. If there's no match, that's an exception that we need to
                    # raise.
                    for result in tool_results:
                        call_id = result["call_id"]
                        for i in range(len(converted_messages) - 1, -1, -1):
                            if converted_messages[i].get("type") != "function_call":
                                continue
                            if converted_messages[i].get("call_id") == call_id:
                                converted_messages.insert(i + 1, result)
                                break
                        else:
                            raise ValueError(f"No matching call found for result: {result}")
                case "agent":
                    for content in message.content:
                        match content:
                            case PromptTextContent() as text_content:
                                if text_content.text:
                                    converted_messages.append(
                                        EasyInputMessageParam(
                                            role="assistant",
                                            content=[
                                                # The SDK typing for Azure can be finicky;
                                                ResponseOutputTextParam(
                                                    type="output_text",
                                                    text=text_content.text,
                                                    annotations=[],
                                                )  # type: ignore[arg-type]
                                            ],
                                        )
                                    )
                            case PromptReasoningContent() as reasoning_content:
                                converted_messages.append(
                                    ResponseReasoningItemParam(
                                        id=reasoning_content.response_id or "",
                                        type="reasoning",
                                        summary=[
                                            Summary(type="summary_text", text=s)
                                            for s in reasoning_content.summary or []
                                        ],
                                        content=[
                                            Content(type="reasoning_text", text=c)
                                            for c in reasoning_content.content or []
                                        ],
                                        encrypted_content=reasoning_content.encrypted_content,
                                    )
                                )
                            case PromptToolUseContent() as tool_use_content:
                                tool_call = await self.convert_tool_use_content(tool_use_content)
                                converted_messages.append(tool_call)
                            case _:
                                # Ignore unsupported content types for agent messages here
                                # (audio/document not supported in Responses API yet).
                                pass

                    if (
                        len(converted_messages) > 0
                        and converted_messages[-1].get("type") == "reasoning"
                    ):
                        # This is to patch over a case where we could end up w/ a reasoning
                        # item at the end, but no tool call (perhaps there was text content
                        # we didn't care to include... say, because we're not showing that
                        # content in the thread to the user, so it doesn't round trip)
                        converted_messages.append(
                            EasyInputMessageParam(
                                role="assistant",
                                content=[
                                    ResponseOutputTextParam(
                                        type="output_text",
                                        text="",
                                    )  # type: ignore[arg-type]
                                ],
                            )
                        )
                case _:
                    raise ValueError(f"Unsupported message role: {message.role}")

        return converted_messages

    async def _convert_tools(
        self,
        tools: list[ToolDefinition],
    ) -> list["ToolParam"]:
        """Convert tool definitions to OpenAI tool parameters.

        Args:
            tools: The list of tool definitions to convert.

        Returns:
            The list of OpenAI tool parameters.
        """
        from openai.types.responses import FunctionToolParam, ToolParam

        converted_tools: list[ToolParam] = []
        for tool in tools:
            converted_tools.append(
                FunctionToolParam(
                    type="function",
                    name=tool.name,
                    parameters=tool.input_schema or {},
                    description=tool.description or "",
                    strict=False,
                )
            )
        return converted_tools

    def _model_id_to_reasoning_effort(self, model_id: str | None) -> "ReasoningEffort":
        """Convert a model ID to a reasoning effort."""
        if not model_id:
            # No model ID, default to medium effort
            return "medium"

        if model_id.endswith("-high"):
            return "high"
        elif model_id.endswith("-medium"):
            return "medium"
        elif model_id.endswith("-low"):
            return "low"
        elif model_id.endswith("-minimal"):
            return "minimal"

        # No explicit effort in the model ID, default to medium effort
        return "medium"

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
        from openai.types.shared_params import Reasoning

        # Convert messages and system instruction
        messages = await self._convert_messages(prompt.finalized_messages)

        # Convert tools if present
        tools = []
        if prompt.tools:
            tools = await self._convert_tools(prompt.tools)

        reasoning_effort = self._model_id_to_reasoning_effort(model_id)

        # If we're minimizing reasoning, and on a gpt-5 model, we can set reasoning to "minimal"
        # otherwise, we'll default to medium effort and detailed summary
        reasoning = Reasoning(
            effort=reasoning_effort,
            summary="detailed",
        )
        if prompt.minimize_reasoning:
            if model_id and model_id.startswith("gpt-5"):
                reasoning = Reasoning(
                    effort="minimal",
                    summary="concise",
                )
            else:
                reasoning = Reasoning(
                    effort="low",
                    summary="auto",
                )

        return OpenAIPrompt(
            input=messages,
            instructions=prompt.system_instruction,
            tools=tools,
            temperature=prompt.temperature or 0.0,
            top_p=prompt.top_p or 1.0,
            max_output_tokens=prompt.max_output_tokens or 4096,
            reasoning=reasoning,
        )
