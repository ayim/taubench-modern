from abc import ABC, abstractmethod

from agent_platform.core.responses.content import (
    ResponseAudioContent,
    ResponseDocumentContent,
    ResponseImageContent,
    ResponseMessageContent,
    ResponseTextContent,
    ResponseToolUseContent,
)
from agent_platform.core.responses.response import ResponseMessage, TokenUsage
from agent_platform.core.tools.tool_definition import ToolDefinition


class ResponseStreamSinkBase(ABC):
    """
    Base interface for sinks that receive partial or complete response updates
    from a ResponseStreamPipe.
    """

    @abstractmethod
    async def on_message_begin(
        self,
        message: ResponseMessage,
    ) -> None:
        """
        Called when a new ResponseMessage is recognized or begins streaming.
        """
        pass

    @abstractmethod
    async def on_stop_reason(
        self,
        stop_reason: str | None,
    ) -> None:
        """
        Called when a ResponseMessage's stop reason becomes known.
        """
        pass

    @abstractmethod
    async def on_usage(
        self,
        usage: TokenUsage,
    ) -> None:
        """
        Called when usage info is available or updated.
        """
        pass

    @abstractmethod
    async def on_message_end(
        self,
        message: ResponseMessage,
    ) -> None:
        """
        Called when a ResponseMessage is fully completed.
        """
        pass

    @abstractmethod
    async def on_content_begin(
        self,
        idx: int,
        content: ResponseMessageContent,
    ) -> None:
        """
        Called before partial content updates for a specific content item.
        """
        pass

    @abstractmethod
    async def on_content_end(
        self,
        idx: int,
        old_content: ResponseMessageContent,
        new_content: ResponseMessageContent,
    ) -> None:
        """
        Called when the content item at `idx` is considered final/completed.
        """
        pass

    @abstractmethod
    async def on_text_content_begin(
        self,
        idx: int,
        content: ResponseTextContent,
    ) -> None:
        """
        Called before partial updates of text content.
        """
        pass

    @abstractmethod
    async def on_text_content_partial(
        self,
        idx: int,
        old_content: ResponseTextContent,
        new_content: ResponseTextContent,
    ) -> None:
        """
        Called to update the partial text content at `idx`.
        """
        pass

    @abstractmethod
    async def on_text_content_end(
        self,
        idx: int,
        final_content: ResponseTextContent,
    ) -> None:
        """
        Called when the text content at `idx` is final.
        """
        pass

    @abstractmethod
    async def on_image_content_begin(
        self,
        idx: int,
        content: ResponseImageContent,
    ) -> None:
        """
        Called before partial updates of image content.
        """
        pass

    @abstractmethod
    async def on_image_content_partial(
        self,
        idx: int,
        old_content: ResponseImageContent,
        new_content: ResponseImageContent,
    ) -> None:
        """
        Called to update the partial image content at `idx`.
        """
        pass

    @abstractmethod
    async def on_image_content_end(
        self,
        idx: int,
        final_content: ResponseImageContent,
    ) -> None:
        """
        Called when the image content at `idx` is final.
        """
        pass

    @abstractmethod
    async def on_audio_content_begin(
        self,
        idx: int,
        content: ResponseAudioContent,
    ) -> None:
        """
        Called before partial updates of audio content.
        """
        pass

    @abstractmethod
    async def on_audio_content_partial(
        self,
        idx: int,
        old_content: ResponseAudioContent,
        new_content: ResponseAudioContent,
    ) -> None:
        """
        Called to update the partial audio content at `idx`.
        """
        pass

    @abstractmethod
    async def on_audio_content_end(
        self,
        idx: int,
        final_content: ResponseAudioContent,
    ) -> None:
        """
        Called when the audio content at `idx` is final.
        """
        pass

    @abstractmethod
    async def on_document_content_begin(
        self,
        idx: int,
        content: ResponseDocumentContent,
    ) -> None:
        """
        Called before partial updates of document content.
        """
        pass

    @abstractmethod
    async def on_document_content_partial(
        self,
        idx: int,
        old_content: ResponseDocumentContent,
        new_content: ResponseDocumentContent,
    ) -> None:
        """
        Called to update the partial document content at `idx`.
        """
        pass

    @abstractmethod
    async def on_document_content_end(
        self,
        idx: int,
        final_content: ResponseDocumentContent,
    ) -> None:
        """
        Called when the document content at `idx` is final.
        """
        pass

    @abstractmethod
    async def on_tool_use_content_begin(
        self,
        idx: int,
        content: ResponseToolUseContent,
        tool_def: ToolDefinition | None,
    ) -> None:
        """
        Called before partial updates of tool use content.
        """
        pass

    @abstractmethod
    async def on_tool_use_content_partial(
        self,
        idx: int,
        old_content: ResponseToolUseContent,
        new_content: ResponseToolUseContent,
        tool_def: ToolDefinition | None,
    ) -> None:
        """
        Called to update the partial tool use content at `idx`.
        """
        pass

    @abstractmethod
    async def on_tool_use_content_end(
        self,
        idx: int,
        final_content: ResponseToolUseContent,
        tool_def: ToolDefinition | None,
    ) -> None:
        """
        Called when the tool use content at `idx` is final.
        """
        pass
