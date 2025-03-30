import asyncio
from collections.abc import AsyncGenerator
from typing import cast

from agent_platform.core.delta import GenericDelta
from agent_platform.core.delta.combine_delta import combine_generic_deltas
from agent_platform.core.prompts.prompt import Prompt
from agent_platform.core.responses.content import (
    ResponseAudioContent,
    ResponseDocumentContent,
    ResponseImageContent,
    ResponseMessageContent,
    ResponseTextContent,
    ResponseToolUseContent,
)
from agent_platform.core.responses.response import ResponseMessage
from agent_platform.core.responses.streaming.stream_sink_base import (
    ResponseStreamSinkBase,
)
from agent_platform.core.responses.streaming.stream_sink_noop import (
    NoOpResponseStreamSink,
)
from agent_platform.core.tools.tool_definition import ToolDefinition


class ResponseStreamPipe:
    def __init__(
        self,
        stream: AsyncGenerator[GenericDelta, None],
        prompt: Prompt,
    ):
        self.stream = stream
        self.stream_closed = False
        self.buffer_object: dict = {}
        self.chunk_buffer: list[GenericDelta] = []
        self.source_prompt = prompt

        # Cache for tool definitions lookup
        self._tool_def_cache: dict[str, ToolDefinition] = {
            tool_def.name: tool_def for tool_def in self.source_prompt.tools
        }

        # The most recently assembled ResponseMessage (still might be incomplete)
        self.current_message: ResponseMessage | None = None

        # The last stable ResponseMessage that we've dispatched to sinks
        self.last_message: ResponseMessage | None = None

        # Sinks that we'll call on partial updates
        self.sinks: tuple[ResponseStreamSinkBase, ...] = ()

    async def __aenter__(self) -> "ResponseStreamPipe":
        """Allow this class to be used as an async context manager."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Close the stream when exiting the context manager."""
        await self.aclose()

    async def pipe_to(self, *sinks: ResponseStreamSinkBase):
        """
        Consume deltas from self.stream, buffer them, and whenever
        we can form a valid ResponseMessage, call _compute_response_update().
        """
        if self.stream_closed:
            raise RuntimeError("Stream is already closed")

        # Ignore noop sinks
        self.sinks = tuple(
            sink for sink in sinks
            if type(sink) is not NoOpResponseStreamSink
        )

        async for chunk in self.stream:
            self.chunk_buffer.append(chunk)
            if self._try_reassemble_response():
                await self._compute_response_update()
                # Make sure we yield to the event loop so that we don't
                # starve it of time slices
                await asyncio.sleep(0)

        # Once the stream ends, do a final flush of any leftover chunks
        if self._try_reassemble_response():
            await self._compute_response_update()

        # Dispatch "end" of the message
        if self.last_message:
            await self._dispatch_message_end(self.last_message)

        self.stream_closed = True

    async def aclose(self) -> None:
        """
        Close the stream and make sure we don't try to call any more sinks.
        """
        if hasattr(self.stream, "aclose"):
            await self.stream.aclose()

        # If we're closed, we need to make sure we don't try to call any
        # more sinks
        self.sinks = ()
        self.stream_closed = True

    def _find_matching_tool_def(
        self,
        tool_use_content: ResponseToolUseContent,
    ) -> ToolDefinition | None:
        """
        Find the matching tool def in the prompt (if any)
        """
        return self._tool_def_cache.get(tool_use_content.tool_name)

    def _try_reassemble_response(self) -> bool:
        """
        Try to reassemble the response message from the buffered chunks.
        """
        # Step one is to take the buffered chunks and combine them
        # into a single object
        try:
            self.buffer_object = combine_generic_deltas(
                self.chunk_buffer, self.buffer_object,
            )
            # We managed to combine, so clear the buffer
            self.chunk_buffer.clear()
        except ValueError:
            # Not enough information to combine yet
            # (I don't think this can actually happen)
            return False

        # Step two is to validate the combined object
        # into a ResponseMessage
        try:
            # Try and form the response message
            self.current_message = ResponseMessage.model_validate(
                self.buffer_object,
            )
        except (ValueError, TypeError):
            # Not enough information to form a response message yet
            # (This is maybe more possible?)
            return False

        # If we made it here, we successfully reassembled the response
        # and propagated the update
        return True

    async def _compute_response_update(self) -> None:
        """
        Compare self.current_message to self.last_message to figure out
        what's new or changed. Dispatch partial updates to sinks.
        """
        if not self.current_message:
            # Nothing to do
            return

        new_msg = self.current_message
        old_msg = self.last_message

        if old_msg is None:
            # This is our first message, so we dispatch it
            await self._dispatch_message_begin(new_msg)
        else:
            # We have a previous message, so we need to figure out what's new
            await self._dispatch_message_partial(old_msg, new_msg)

        # Update our last message to reflect what we've just dispatched
        self.last_message = new_msg

    async def _dispatch_message_begin(self, msg: ResponseMessage) -> None:
        """
        Dispatch a fully assembled message to sinks.
        """
        # Dispatch message begin to sinks
        for sink in self.sinks:
            await sink.on_message_begin(msg)

        # Dispatch content to sinks
        for idx, content in enumerate(msg.content):
            await self._dispatch_content_begin(idx, content)

        # Dispatch stop_reason to sinks (if present)
        if msg.stop_reason:
            for sink in self.sinks:
                await sink.on_stop_reason(msg.stop_reason)

        # Dispatch usage to sinks (if present)
        if msg.usage:
            for sink in self.sinks:
                await sink.on_usage(msg.usage)

    async def _dispatch_message_partial(
        self,
        old_msg: ResponseMessage,
        new_msg: ResponseMessage,
    ) -> None:
        """
        Dispatch a partial message to sinks.
        """
        # Check to see if message contents have grown, if so we should end
        # the last message content
        if len(new_msg.content) > len(old_msg.content) and len(old_msg.content) > 0:
            await self._dispatch_content_end(
                len(old_msg.content) - 1, old_msg.content[-1],
            )

        # We assume the stream is append only and content grows monotonically
        for idx, new_content in enumerate(new_msg.content):
            if idx >= len(old_msg.content):
                # This is a new content, so we dispatch the begin and partial
                # for whatever is there already
                await self._dispatch_content_begin(idx, new_content)
                # Next content (likely end of loop)
                continue

            old_content = old_msg.content[idx]
            if old_content.kind != new_content.kind:
                # This can't happen, we're assuming the stream is append only
                raise RuntimeError("Content kind changed during streaming")

            # Dispatch the partial
            await self._dispatch_content_partial(idx, old_content, new_content)

        # TODO: other things we want to incrementally dispatch?

    async def _dispatch_message_end(self, msg: ResponseMessage) -> None:
        """
        Called once we know the message is fully complete (stream ended).
        Dispatches 'end' for each piece of content that began, if not already ended.
        """
        # End the last content (other content gets ended in _dispatch_content_partial)
        await self._dispatch_content_end(
            len(msg.content) - 1, msg.content[-1],
        )

        # TODO: other content only relevant at end?

        if msg.stop_reason:
            for sink in self.sinks:
                await sink.on_stop_reason(msg.stop_reason)

        if msg.usage:
            for sink in self.sinks:
                await sink.on_usage(msg.usage)

        for sink in self.sinks:
            await sink.on_message_end(msg)

    async def _dispatch_content_begin(
        self,
        idx: int,
        content: ResponseMessageContent,
    ) -> None:
        """
        Dispatch a content begin to sinks.
        """
        for sink in self.sinks:
            await sink.on_content_begin(idx, content)
            match content:
                case ResponseTextContent() as text_content:
                    await sink.on_text_content_begin(idx, text_content)
                case ResponseImageContent() as image_content:
                    await sink.on_image_content_begin(idx, image_content)
                case ResponseAudioContent() as audio_content:
                    await sink.on_audio_content_begin(idx, audio_content)
                case ResponseDocumentContent() as document_content:
                    await sink.on_document_content_begin(idx, document_content)
                case ResponseToolUseContent() as tool_use_content:
                    tool_def = self._find_matching_tool_def(tool_use_content)
                    await sink.on_tool_use_content_begin(
                        idx, tool_use_content, tool_def,
                    )

    async def _dispatch_content_partial(
        self,
        idx: int,
        old_content: ResponseMessageContent,
        new_content: ResponseMessageContent,
    ) -> None:
        """
        Dispatch a content partial to sinks.
        """
        for sink in self.sinks:
            # No generic partial dispatch, we have content-specific partial
            # dispatch methods only
            match new_content:
                case ResponseTextContent() as new_text_content:
                    old_text_content = cast(ResponseTextContent, old_content)
                    await sink.on_text_content_partial(
                        idx, old_text_content, new_text_content,
                    )
                case ResponseImageContent() as new_image_content:
                    old_image_content = cast(ResponseImageContent, old_content)
                    await sink.on_image_content_partial(
                        idx, old_image_content, new_image_content,
                    )
                case ResponseAudioContent() as new_audio_content:
                    old_audio_content = cast(ResponseAudioContent, old_content)
                    await sink.on_audio_content_partial(
                        idx, old_audio_content, new_audio_content,
                    )
                case ResponseDocumentContent() as new_document_content:
                    old_document_content = cast(
                        ResponseDocumentContent, old_content,
                    )
                    await sink.on_document_content_partial(
                        idx, old_document_content, new_document_content,
                    )
                case ResponseToolUseContent() as new_tool_use_content:
                    old_tool_use_content = cast(
                        ResponseToolUseContent, old_content,
                    )
                    tool_def = self._find_matching_tool_def(new_tool_use_content)
                    await sink.on_tool_use_content_partial(
                        idx, old_tool_use_content, new_tool_use_content, tool_def,
                    )

    async def _dispatch_content_end(
        self,
        idx: int,
        final_content: ResponseMessageContent,
    ) -> None:
        """
        Dispatch a content end to sinks.
        """
        for sink in self.sinks:
            await sink.on_content_end(idx, final_content, final_content)
            match final_content:
                case ResponseTextContent() as final_text_content:
                    await sink.on_text_content_end(
                        idx, final_text_content,
                    )
                case ResponseImageContent() as final_image_content:
                    await sink.on_image_content_end(
                        idx, final_image_content,
                    )
                case ResponseAudioContent() as final_audio_content:
                    await sink.on_audio_content_end(
                        idx, final_audio_content,
                    )
                case ResponseDocumentContent() as final_document_content:
                    await sink.on_document_content_end(
                        idx, final_document_content,
                    )
                case ResponseToolUseContent() as final_tool_use_content:
                    tool_def = self._find_matching_tool_def(final_tool_use_content)
                    await sink.on_tool_use_content_end(
                        idx, final_tool_use_content, tool_def,
                    )
