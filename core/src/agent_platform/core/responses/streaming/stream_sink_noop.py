from agent_platform.core.responses.content import (
    ResponseAudioContent,
    ResponseDocumentContent,
    ResponseImageContent,
    ResponseMessageContent,
    ResponseTextContent,
    ResponseToolUseContent,
)
from agent_platform.core.responses.response import ResponseMessage, TokenUsage
from agent_platform.core.responses.streaming.stream_sink_base import (
    ResponseStreamSinkBase,
)
from agent_platform.core.tools.tool_definition import ToolDefinition


class NoOpResponseStreamSink(ResponseStreamSinkBase):
    async def on_message_begin(
        self,
        message: ResponseMessage,
    ) -> None:
        pass

    async def on_stop_reason(
        self,
        stop_reason: str | None,
    ) -> None:
        pass

    async def on_usage(
        self,
        usage: TokenUsage,
    ) -> None:
        pass

    async def on_message_end(
        self,
        message: ResponseMessage,
    ) -> None:
        pass

    async def on_content_begin(
        self,
        idx: int,
        content: ResponseMessageContent,
    ) -> None:
        pass

    async def on_content_end(
        self,
        idx: int,
        final_content: ResponseMessageContent,
    ) -> None:
        pass

    async def on_text_content_begin(
        self,
        idx: int,
        content: ResponseTextContent,
    ) -> None:
        pass

    async def on_text_content_partial(
        self,
        idx: int,
        old_content: ResponseTextContent,
        new_content: ResponseTextContent,
    ) -> None:
        pass

    async def on_text_content_end(
        self,
        idx: int,
        final_content: ResponseTextContent,
    ) -> None:
        pass

    async def on_image_content_begin(
        self,
        idx: int,
        content: ResponseImageContent,
    ) -> None:
        pass

    async def on_image_content_partial(
        self,
        idx: int,
        old_content: ResponseImageContent,
        new_content: ResponseImageContent,
    ) -> None:
        pass

    async def on_image_content_end(
        self,
        idx: int,
        final_content: ResponseImageContent,
    ) -> None:
        pass

    async def on_audio_content_begin(
        self,
        idx: int,
        content: ResponseAudioContent,
    ) -> None:
        pass

    async def on_audio_content_partial(
        self,
        idx: int,
        old_content: ResponseAudioContent,
        new_content: ResponseAudioContent,
    ) -> None:
        pass

    async def on_audio_content_end(
        self,
        idx: int,
        final_content: ResponseAudioContent,
    ) -> None:
        pass

    async def on_document_content_begin(
        self,
        idx: int,
        content: ResponseDocumentContent,
    ) -> None:
        pass

    async def on_document_content_partial(
        self,
        idx: int,
        old_content: ResponseDocumentContent,
        new_content: ResponseDocumentContent,
    ) -> None:
        pass

    async def on_document_content_end(
        self,
        idx: int,
        final_content: ResponseDocumentContent,
    ) -> None:
        pass

    async def on_tool_use_content_begin(
        self,
        idx: int,
        content: ResponseToolUseContent,
        tool_def: ToolDefinition | None,
    ) -> None:
        pass

    async def on_tool_use_content_partial(
        self,
        idx: int,
        old_content: ResponseToolUseContent,
        new_content: ResponseToolUseContent,
        tool_def: ToolDefinition | None,
    ) -> None:
        pass

    async def on_tool_use_content_end(
        self,
        idx: int,
        final_content: ResponseToolUseContent,
        tool_def: ToolDefinition | None,
    ) -> None:
        pass
