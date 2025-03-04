from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Self

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
)


class ThreadMessageWithThreadState:
    """A ThreadMessage that includes thread state functionality for streaming and committing."""

    def __init__(
        self,
        message: ThreadMessage,
        thread_state: "ThreadStateInterface",
    ):
        self._thread_state = thread_state
        self._message = message

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
            content: Either a content object or a string. If a string, it will be treated as text content.
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

    def copy(self) -> Self:
        """Returns a deep copy of the message with thread state."""
        new_message = self._message.copy()
        new_message._thread_state = self._thread_state
        return ThreadMessageWithThreadState(new_message, self._thread_state)


class ThreadStateInterface(ABC):
    """Manages the in-memory representation of the current thread."""

    def __init__(self, thread_id: str, agent_id: str):
        self._thread_id = thread_id
        """The ID of the thread we're managing."""
        self._agent_id = agent_id
        """The ID of the agent attached to this thread."""
        self._previous_message_states: dict[str, ThreadMessage | None] = {}
        """A map of message UIDs to the message state, to aid in computing deltas."""
        self._previous_message_sequence_numbers: dict[str, int] = {}
        """A map of message UIDs to the sequence number of the message, to aid in computing deltas."""

    @property
    def thread_id(self) -> str:
        """The ID of the thread we're managing."""
        return self._thread_id

    async def new_agent_ui_message(self) -> ThreadMessageWithThreadState:
        """Creates a new UI message for the agent.

        Returns:
            A new ThreadMessageWithThreadState object.
        """
        new_message = ThreadAgentMessage(content=[])
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

    async def new_user_ui_message(self) -> ThreadMessageWithThreadState:
        """Creates a new UI message for the user.

        Returns:
            A new ThreadMessageWithThreadState object.
        """
        new_message = ThreadUserMessage(content=[])
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
        """Streams a delta of the message to the UI.

        This method will do the work of finding the delta between
        what was last sent and what we have now, and then sending
        the delta to the UI.

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
                    unwrapped_message.to_json_dict(),
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

    @abstractmethod
    async def _send_delta_event(self, delta_object: StreamingDelta) -> None:
        """Sends a delta event to the UI.

        Arguments:
            delta_object: The computed delta between the previous and current message state.
                        Contains the changes that need to be sent to the UI.

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
