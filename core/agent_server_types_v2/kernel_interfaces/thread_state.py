from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Self

from agent_server_types_v2.kernel_interfaces.kernel_mixin import UsesKernelMixin
from agent_server_types_v2.responses.content.tool_use import ResponseToolUseContent
from agent_server_types_v2.responses.streaming import (
    ToolUseResponseStreamSink,
    XmlTagResponseStreamSink,
)
from agent_server_types_v2.streaming import (
    StreamingDelta,
    StreamingDeltaMessageBegin,
    StreamingDeltaMessageEnd,
    StreamingError,
    compute_message_delta,
)
from agent_server_types_v2.thread import (
    ThreadAgentMessage,
    ThreadMessage,
    ThreadUserMessage,
)
from agent_server_types_v2.thread.base import AnyThreadMessageContent
from agent_server_types_v2.thread.content import (
    ThreadTextContent,
    ThreadThoughtContent,
    ThreadToolUsageContent,
)
from agent_server_types_v2.tools.tool_definition import ToolDefinition
from agent_server_types_v2.tools.tool_execution_result import ToolExecutionResult


class ThreadMessageWithThreadState:
    """A ThreadMessage that includes thread state functionality for
    streaming and committing."""

    class Sinks:
        """A class that contains the sinks for the message."""
        def __init__(
            self,
            message: "ThreadMessageWithThreadState",
            content_tag: str = "response",
            thoughts_tag: str = "thinking",
        ):
            self._message = message
            self._content_tag = content_tag
            self._thoughts_tag = thoughts_tag

        @property
        def content(self) -> XmlTagResponseStreamSink:
            """The sink for the content of the message."""
            async def _append_content(tag: str, content: str) -> None:
                self._message.append_content(content)
                await self._message.stream_delta()

            return XmlTagResponseStreamSink(
                tag=self._content_tag,
                on_tag_partial=_append_content,
            )

        @property
        def thoughts(self) -> XmlTagResponseStreamSink:
            """The sink for the thoughts of the message."""
            async def _append_thought(tag: str, content: str) -> None:
                self._message.append_thought(content)
                await self._message.stream_delta()

            return XmlTagResponseStreamSink(
                tag=self._thoughts_tag,
                on_tag_partial=_append_thought,
            )

        @property
        def tool_calls(self) -> ToolUseResponseStreamSink:
            """The sink for the tool calls of the message."""
            async def _update_tool_use(
                content: ResponseToolUseContent,
                tool_def: ToolDefinition | None,
            ) -> None:
                self._message.update_tool_use(content, tool_def)
                await self._message.stream_delta()

            async def _update_tool_use_final(
                content: ResponseToolUseContent,
                tool_def: ToolDefinition | None,
            ) -> None:
                self._message.update_tool_use(content, tool_def, completed=True)
                await self._message.stream_delta()

            return ToolUseResponseStreamSink(
                on_tool_partial=_update_tool_use,
                on_tool_complete=_update_tool_use_final,
            )

    def __init__(
        self,
        message: ThreadMessage,
        thread_state: "ThreadStateInterface",
    ):
        self._thread_state = thread_state
        self._message = message
        self._sinks = self.Sinks(self)

    @property
    def sinks(self) -> Sinks:
        """The sinks for the message."""
        return self._sinks

    @property
    def message(self) -> ThreadMessage:
        """The message that this object wraps."""
        return self._message

    @property
    def agent_metadata(self) -> dict[str, Any]:
        """The metadata of the message."""
        return self._message.agent_metadata

    async def commit(self) -> None:
        """Commits the message to the thread state."""
        await self._thread_state.commit_message(self._message)
        self._message.commited = True

    async def stream_delta(self) -> None:
        """Streams the delta to the UI."""
        await self._thread_state.stream_message_delta(self._message)

    def new_thought(self, thought: str) -> None:
        """Adds a thought to the message."""
        if self._message.commited:
            raise ValueError("Cannot add content to a committed message")
        self._message.content.append(ThreadThoughtContent(thought=thought))

    def append_content(self, content: AnyThreadMessageContent | str) -> None:
        """Appends content to this message.

        Args:
            content: Either a content object or a string. If a string,
                it will be treated as text content.
        """
        if self._message.commited:
            raise ValueError("Cannot add content to a committed message")

        self.updated_at = datetime.now()

        # If string is passed, treat it as text content
        if isinstance(content, str):
            text_piece = content
            index_of_last_text_content = next(
                (
                    i
                    for i, content in enumerate(self._message.content)
                    if isinstance(content, ThreadTextContent)
                ),
                None,
            )

            if index_of_last_text_content is None:
                self._message.content.append(ThreadTextContent(text=text_piece))
            else:
                # Directly mutate the text content instead of creating a new object
                self._message.content[index_of_last_text_content].text += text_piece
        else:
            # For other content types, just append directly
            self._message.content.append(content)

    def append_thought(self, thought: str) -> None:
        """Appends a text to the most recent thought content."""
        if self._message.commited:
            raise ValueError("Cannot add content to a committed message")

        index_of_last_thought_content = next(
            (
                i
                for i, content in enumerate(self._message.content)
                if isinstance(content, ThreadThoughtContent)
            ),
            None,
        )

        if index_of_last_thought_content is None:
            self._message.content.append(ThreadThoughtContent(thought=thought))
        else:
            # Directly mutate the thought content instead of creating a new object
            self._message.content[index_of_last_thought_content].thought += thought

    def update_tool_use(
        self,
        tool_use: ResponseToolUseContent,
        tool_def: ToolDefinition | None = None,
        completed: bool = False,
    ) -> None:
        """Updates the tool use for the message from a response tool use content."""
        if self._message.commited:
            raise ValueError("Cannot add content to a committed message")

        # Find a matching tool use on ID
        for idx, content in enumerate(self._message.content):
            if not isinstance(content, ThreadToolUsageContent):
                continue
            if content.tool_call_id != tool_use.tool_call_id:
                continue

            # If we're here, we have a matching tool use
            self._message.content[idx].tool_name = tool_use.tool_name
            self._message.content[idx].arguments_raw = tool_use.tool_input_raw
            self._message.content[idx].pending_at = (
                datetime.now() if completed else None
            )
            break  # Only can match one tool use

        else:  # No matching tool use found, so we add a new one
            self._message.content.append(
                ThreadToolUsageContent(
                    name=tool_use.tool_name,
                    arguments_raw=tool_use.tool_input_raw,
                    tool_call_id=tool_use.tool_call_id,
                    status="streaming",
                    discovered_at=datetime.now(),
                    pending_at=datetime.now() if completed else None,
                ),
            )

    def update_tool_result(
        self,
        result: ToolExecutionResult,
    ) -> None:
        """Updates the tool result for the message from a tool execution result."""
        if self._message.commited:
            raise ValueError("Cannot add content to a committed message")

        # There must be a matching tool use on ID
        match_idx = next(
            (
                idx
                for idx, content in enumerate(self._message.content)
                if (
                    isinstance(content, ThreadToolUsageContent) and
                    content.tool_call_id == result.tool_call_id
                )
            ),
            None,
        )

        if match_idx is None:
            # If there isn't a matching tool use, we can't update the result
            raise ValueError(
                f"No matching tool use found for tool call ID {result.execution_id}",
            )

        if self._message.content[match_idx].metadata is None:
            self._message.content[match_idx].metadata = {}

        # Update the tool use with the result
        self._message.content[match_idx].started_at = result.execution_started_at
        self._message.content[match_idx].ended_at = result.execution_ended_at
        # TODO: handle non-string results
        self._message.content[match_idx].result = str(result.output_raw)
        self._message.content[match_idx].error = result.error
        self._message.content[match_idx].metadata["execution"] = (
            result.execution_metadata
        )
        self._message.content[match_idx].status = (
            "failed" if result.error else "finished"
        )

    def copy(self) -> Self:
        """Returns a deep copy of the message with thread state."""
        new_message = self._message.copy()
        new_message._thread_state = self._thread_state
        return ThreadMessageWithThreadState(new_message, self._thread_state)


class ThreadStateInterface(ABC, UsesKernelMixin):
    """Manages the in-memory representation of the current thread."""

    def __init__(self, thread_id: str, agent_id: str):
        self._thread_id = thread_id
        """The ID of the thread we're managing."""
        self._agent_id = agent_id
        """The ID of the agent attached to this thread."""
        self._previous_message_states: dict[str, ThreadMessage | None] = {}
        """A map of message UIDs to the message state, to aid in computing deltas."""
        self._previous_message_sequence_numbers: dict[str, int] = {}
        """A map of message UIDs to the sequence number of the message,
        to aid in computing deltas."""
        self._active_message_id: str | None = None
        """The ID of the currently active message in the thread."""

    @property
    def thread_id(self) -> str:
        """The ID of the thread we're managing."""
        return self._thread_id

    @property
    def active_message_id(self) -> str | None:
        """The ID of the currently active message in the thread.

        Returns:
            The ID of the currently active message in the thread, or None if
            there is no active message.
        """
        return self._active_message_id

    async def new_agent_message(self) -> ThreadMessageWithThreadState:
        """Creates a new agent message in the thread (attached to thread state).

        Returns:
            A new ThreadMessageWithThreadState object.
        """
        new_message = ThreadAgentMessage(
            content=[],
            parent_run_id=self.kernel.run.run_id,
        )
        self._active_message_id = new_message.message_id
        await self._send_delta_event(
            StreamingDeltaMessageBegin(
                0,
                new_message.message_id,
                datetime.now(),
                self._thread_id,
                self._agent_id,
            ),
        )
        self._previous_message_states[new_message.message_id] = None
        self._previous_message_sequence_numbers[new_message.message_id] = 1
        return ThreadMessageWithThreadState(new_message, self)

    async def new_user_message(self) -> ThreadMessageWithThreadState:
        """Creates a new user message in the thread (attached to thread state).

        Returns:
            A new ThreadMessageWithThreadState object.
        """
        new_message = ThreadUserMessage(
            content=[],
            parent_run_id=self.kernel.run.run_id,
        )
        self._active_message_id = new_message.message_id
        await self._send_delta_event(
            StreamingDeltaMessageBegin(
                0,
                new_message.message_id,
                datetime.now(),
                self._thread_id,
                self._agent_id,
            ),
        )
        self._previous_message_states[new_message.message_id] = None
        self._previous_message_sequence_numbers[new_message.message_id] = 1
        return ThreadMessageWithThreadState(new_message, self)

    async def stream_message_delta(
        self,
        message: ThreadMessageWithThreadState | ThreadMessage,
    ) -> None:
        """Streams a delta of the message to clients.

        This method will do the work of finding the delta between
        what was last sent and what we have now, and then sending
        the delta to clients.

        Arguments:
            message: The message to stream the delta for.

        Raises:
            StreamingError: If we fail to send the delta to downstream
                consumers.
        """
        unwrapped_message = (
            message._message
            if isinstance(message, ThreadMessageWithThreadState)
            else message
        )

        # First, if we haven't seen this message before, we'll set
        # the previous state to None. (Which our delta computation
        # will treat as an empty message.)
        if unwrapped_message.message_id not in self._previous_message_states:
            self._previous_message_states[unwrapped_message.message_id] = None
            self._previous_message_sequence_numbers[unwrapped_message.message_id] = 0

        # Next, we'll reference what state we last had for this
        # message (possibly None) and what state we have now to
        # compute the delta.
        delta_objects = compute_message_delta(
            old=self._previous_message_states[unwrapped_message.message_id],
            new=unwrapped_message,
            sequence_number=self._previous_message_sequence_numbers[
                unwrapped_message.message_id
            ],
        )

        # Finally, we'll send the delta over to the UI or whatever
        # downstream consumer is listening.
        try:
            for delta_object in delta_objects:
                await self._send_delta_event(delta_object)

            # And, finally, we'll update our state to the current message.
            self._previous_message_states[unwrapped_message.message_id] = (
                unwrapped_message.copy()
            )
            self._previous_message_sequence_numbers[unwrapped_message.message_id] += (
                len(delta_objects)
            )
        except Exception as e:
            # If we failed to send the delta, we'll raise an error.
            raise StreamingError(
                f"Failed to send delta for message {unwrapped_message.message_id}",
            ) from e

    async def commit_message(
        self,
        message: ThreadMessageWithThreadState | ThreadMessage,
    ) -> None:
        """Commits a message to the thread state."""
        unwrapped_message = (
            message._message
            if isinstance(message, ThreadMessageWithThreadState)
            else message
        )

        try:
            sequence_number = 0
            if unwrapped_message.message_id in self._previous_message_sequence_numbers:
                sequence_number = self._previous_message_sequence_numbers[
                    unwrapped_message.message_id
                ]

            await self._send_delta_event(
                StreamingDeltaMessageEnd(
                    sequence_number,
                    unwrapped_message.message_id,
                    datetime.now(),
                    self._thread_id,
                    self._agent_id,
                    # Send full message at end? (TBD)
                    unwrapped_message.model_dump(),
                ),
            )

            await self._commit_message_to_storage(message)

            if unwrapped_message.message_id in self._previous_message_states:
                del self._previous_message_states[unwrapped_message.message_id]
            if unwrapped_message.message_id in self._previous_message_sequence_numbers:
                del self._previous_message_sequence_numbers[
                    unwrapped_message.message_id
                ]
        except Exception as e:
            # TODO: unique error type here?
            raise Exception(
                f"Failed to commit message {unwrapped_message.message_id} to storage",
            ) from e
        finally:
            self._active_message_id = None

    @abstractmethod
    async def _send_delta_event(self, delta_object: StreamingDelta) -> None:
        """Sends a delta event to the UI.

        Arguments:
            delta_object: The computed delta between the previous and current
                message state. Contains the changes that need to be sent to the UI.

        Raises:
            StreamingError: If the delta cannot be sent to the UI.
        """
        pass

    @abstractmethod
    async def _commit_message_to_storage(self, message: ThreadMessage) -> None:
        """Commits a message to the thread state storage.

        Arguments:
            message: The message to commit to storage.

        Raises:
            Exception: If the message cannot be committed to storage.
        """
        pass
