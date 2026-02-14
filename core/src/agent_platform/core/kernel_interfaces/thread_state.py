import json
from abc import ABC, abstractmethod
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal, cast

from agent_platform.core.kernel_interfaces.kernel_mixin import UsesKernelMixin
from agent_platform.core.kernel_interfaces.thread_state_sinks import ThreadStateSinks
from agent_platform.core.responses.content.tool_use import ResponseToolUseContent
from agent_platform.core.streaming import (
    StreamingDeltaMessage,
    StreamingDeltaMessageBegin,
    StreamingDeltaMessageEnd,
    StreamingError,
    compute_message_delta,
)
from agent_platform.core.thread import ThreadAgentMessage, ThreadMessage, ThreadUserMessage
from agent_platform.core.thread.base import AnyThreadMessageContent
from agent_platform.core.thread.content import ThreadTextContent, ThreadThoughtContent, ThreadToolUsageContent
from agent_platform.core.tools.tool_definition import ToolDefinition
from agent_platform.core.tools.tool_execution_result import ToolExecutionResult

if TYPE_CHECKING:
    from agent_platform.core.responses.response import ResponseMessage


def _get_sub_type_from_tool_category(
    tool_def: ToolDefinition | None,
) -> Literal[
    "kernel-internal",
    "aa-internal",
    "action-external",
    "mcp-external",
    "provider-side",
    "client-side",
    "unknown",
]:
    """Map tool definition category to ThreadToolUsageContent sub_type."""
    if tool_def is None:
        return "unknown"

    category_to_sub_type: dict[
        str,
        Literal[
            "kernel-internal",
            "aa-internal",
            "action-external",
            "mcp-external",
            "provider-side",
            "client-side",
            "unknown",
        ],
    ] = {
        "internal-tool": "kernel-internal",
        "action-tool": "action-external",
        "mcp-tool": "mcp-external",
        "client-exec-tool": "client-side",
        "client-info-tool": "client-side",
        "unknown": "unknown",
    }

    return category_to_sub_type.get(tool_def.category, "unknown")


class ThreadMessageWithThreadState:
    """A ThreadMessage that includes thread state functionality for
    streaming and committing."""

    def __init__(
        self,
        message: ThreadMessage,
        thread_state: "ThreadStateInterface",
        tag_expected_past_response: str | None = "step",
        tag_expected_pre_response: str | None = "thinking",
    ):
        self._thread_state = thread_state
        self._message = message
        self._prompt_index = 0
        self._tag_expected_past_response = tag_expected_past_response
        self._tag_expected_pre_response = tag_expected_pre_response
        self._sinks = ThreadStateSinks(
            self,
            tag_expected_past_response=self._tag_expected_past_response,
            tag_expected_pre_response=self._tag_expected_pre_response,
        )

    @property
    def sinks(self) -> ThreadStateSinks:
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

    def update_tools_metadata(self, tools: Sequence[ToolDefinition]) -> None:
        """Update the tools metadata for the message."""
        self.agent_metadata["tools"] = [tool.model_dump() for tool in tools]

    def update_usage_metadata(
        self,
        *,
        platform: str,
        model: str,
        call_type: str,
        response: "ResponseMessage | None" = None,
        usage: dict[str, Any] | None = None,
    ) -> None:
        """Record the platform/model usage info for this message."""
        usage_payload = usage
        if usage_payload is None and response is not None:
            usage_payload = response.usage.model_dump()

        self.agent_metadata.setdefault("models", [])
        self.agent_metadata["models"].append(
            {
                "platform": platform,
                "model": model,
                "call_type": call_type,
                "usage": usage_payload,
            }
        )

    def get_text_content(self) -> str:
        """Gets the text content of the message."""
        text_content = ""
        for content in self._message.content:
            if isinstance(content, ThreadTextContent):
                text_content += content.text
        return text_content

    def mark_prompt_start(self) -> None:
        """Marks the prompt as started."""
        if "content_idx_to_prompt_idx" not in self._message.agent_metadata:
            self._message.agent_metadata["content_idx_to_prompt_idx"] = {}

    def mark_prompt_end(self) -> None:
        """Marks the prompt as ended."""
        for idx in range(len(self._message.content)):
            if idx not in self._message.agent_metadata["content_idx_to_prompt_idx"]:
                self._message.agent_metadata["content_idx_to_prompt_idx"][idx] = self._prompt_index
        self._prompt_index += 1

    def mark_last_content_complete(self) -> None:
        """Marks the last content as complete (finished streaming)."""
        if self._message.content:
            self._message.content[-1].mark_complete()

    async def commit(self, ignore_websocket_errors: bool = False) -> None:
        """Commits the message to the thread state.

        Args:
            ignore_websocket_errors: If True, websocket errors will be ignored during commit.
                Useful for long-running tools where websocket connections might be lost.
        """
        self._message.commited = True
        self._message.mark_complete()

        if ignore_websocket_errors:
            # Try to send websocket delta but ignore errors
            try:
                await self.stream_delta()
            except Exception:
                # Ignore websocket errors when flag is set
                pass
        else:
            # Normal behavior - websocket errors will propagate
            await self.stream_delta()

        await self._thread_state.commit_message(self._message, ignore_websocket_errors=ignore_websocket_errors)

        kernel = self._thread_state.kernel
        kernel.ctx.increment_counter(
            "sema4ai.agent_server.messages",
            1,
            {
                "agent_id": kernel.agent.agent_id,
                "thread_id": kernel.thread.thread_id,
            },
        )

    async def soft_commit(self) -> None:
        """Commits the message to storage but keeps it editable for long-running tools.

        This method saves the message to the database but keeps self._message.commited = False
        so that the message can still be updated (e.g., for long-running tool results).
        Use this when you want to persist the message but continue tool execution.
        """
        # We used to mark complete in soft commit... but that's not
        # correct, as it's not complete until we've streamed the final
        # delta for the content

        # Send the current state to websocket (but don't fail if websocket is down)
        try:
            await self.stream_delta()
        except Exception:
            # Ignore websocket errors during soft commit
            pass

        # Commit to storage but ignore websocket errors
        await self._thread_state.commit_message(self._message, ignore_websocket_errors=True)

        # Increment counter
        kernel = self._thread_state.kernel
        kernel.ctx.increment_counter(
            "sema4ai.agent_server.messages",
            1,
            {
                "agent_id": kernel.agent.agent_id,
                "thread_id": kernel.thread.thread_id,
            },
        )

    async def stream_delta(self) -> None:
        """Streams the delta to the UI."""
        await self._thread_state.stream_message_delta(self._message)

    def new_thought(self, thought: str, complete: bool = False) -> None:
        """Adds a thought to the message."""
        if self._message.commited:
            raise ValueError("Cannot add content to a committed message")
        as_thought_content = ThreadThoughtContent(thought=thought)
        if complete:
            as_thought_content.mark_complete()
        self._message.content.append(as_thought_content)

    def clear_thoughts(self) -> None:
        """Clears the thoughts from the message."""
        if self._message.commited:
            raise ValueError("Cannot add content to a committed message")
        for content in self._message.content:
            if isinstance(content, ThreadThoughtContent):
                content.thought = ""

    def clear_content(self) -> None:
        """Clears the content from the message."""
        if self._message.commited:
            raise ValueError("Cannot add content to a committed message")
        for content in self._message.content:
            if isinstance(content, ThreadTextContent):
                content.text = ""

    def append_content(
        self,
        content: AnyThreadMessageContent | str,
        complete: bool = False,
        incremental: bool = False,
        overwrite: bool = False,
    ) -> None:
        """Appends content to this message.

        Args:
            content: Either a content object or a string. If a string,
                it will be treated as text content.
        """
        if self._message.commited:
            raise ValueError("Cannot add content to a committed message")

        self._message.updated_at = datetime.now(UTC)

        # If string is passed, treat it as text content
        if isinstance(content, str):
            text_piece = content

            # In older versions of this index computation, we had wrongly
            # picked the _first_ index instead of the _last_ index. Somehow,
            # this didn't bite us as we only had one text/thought content.
            # Now we may have more, and need to make sure we iterate
            # backwards to find the last text content.
            index_of_last_text_content = None
            for i in range(len(self._message.content) - 1, -1, -1):
                if isinstance(self._message.content[i], ThreadTextContent):
                    index_of_last_text_content = i
                    break

            if index_of_last_text_content is None or self._message.content[index_of_last_text_content].complete:
                self._message.content.append(ThreadTextContent(text=text_piece))
                self._message.content[-1].complete = complete
            else:
                # Directly mutate the text content instead of creating a new object
                as_text_content = cast(
                    ThreadTextContent,
                    self._message.content[index_of_last_text_content],
                )
                if overwrite:
                    as_text_content.text = text_piece
                    as_text_content.complete = complete
                    return

                current_text_length = len(as_text_content.text)
                if incremental and current_text_length > 0:
                    as_text_content.text += text_piece[current_text_length:]
                else:
                    as_text_content.text += text_piece
                as_text_content.complete = complete
        else:
            # For other content types, just append directly
            self._message.content.append(content)

    def append_thought(
        self,
        thought: str,
        complete: bool = False,
        extras: dict[str, Any] | None = None,
    ) -> None:
        """Appends a text to the most recent thought content."""
        if self._message.commited:
            raise ValueError("Cannot add content to a committed message")

        # Same thing, we were getting _first_ not last previouslly
        index_of_last_thought_content = None
        for i in range(len(self._message.content) - 1, -1, -1):
            if isinstance(self._message.content[i], ThreadThoughtContent):
                index_of_last_thought_content = i
                break

        if index_of_last_thought_content is None or self._message.content[index_of_last_thought_content].complete:
            self._message.content.append(ThreadThoughtContent(thought=thought))
        else:
            # Directly mutate the thought content instead of creating a new object
            as_thought_content = cast(
                ThreadThoughtContent,
                self._message.content[index_of_last_thought_content],
            )
            as_thought_content.thought += thought
            if complete:
                # Merge extras before marking complete to preserve timing data
                if extras:
                    as_thought_content.extras.update(extras)
                as_thought_content.mark_complete()

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
            match_as_tool_use = cast(
                ThreadToolUsageContent,
                self._message.content[idx],
            )
            match_as_tool_use.name = tool_use.tool_name
            match_as_tool_use.arguments_raw = tool_use.tool_input_raw
            match_as_tool_use.sub_type = _get_sub_type_from_tool_category(tool_def)
            # Complete means "we have got all the content from the LLM"
            if completed:
                # If we are complete, the tool is no _pending execution_
                match_as_tool_use.pending_at = datetime.now(UTC)
            # Once we are complete, we shouldn't flop back to incomplete
            # (The LLM can't take the tokens back from us)
            match_as_tool_use.complete = match_as_tool_use.complete or completed
            break  # Only can match one tool use

        else:  # No matching tool use found, so we add a new one
            new_tool_usage = ThreadToolUsageContent(
                name=tool_use.tool_name,
                arguments_raw=tool_use.tool_input_raw,
                tool_call_id=tool_use.tool_call_id,
                sub_type=_get_sub_type_from_tool_category(tool_def),
                status="streaming",
                discovered_at=datetime.now(UTC),
                pending_at=datetime.now(UTC) if completed else None,
            )
            new_tool_usage.complete = completed
            self._message.content.append(new_tool_usage)

    def update_tool_running(self, tool_call_id: str) -> None:
        """Updates the tool to "running" for the message from a tool call ID."""
        if self._message.commited:
            raise ValueError("Cannot add content to a committed message")

        # Find a matching tool use on ID
        for idx, content in enumerate(self._message.content):
            if not isinstance(content, ThreadToolUsageContent):
                continue
            if content.tool_call_id != tool_call_id:
                continue

            # If we're here, we have a matching tool use
            match_as_tool_use = cast(
                ThreadToolUsageContent,
                self._message.content[idx],
            )
            match_as_tool_use.status = "running"
            match_as_tool_use.started_at = datetime.now(UTC)
            break

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
                if (isinstance(content, ThreadToolUsageContent) and content.tool_call_id == result.tool_call_id)
            ),
            None,
        )

        if match_idx is None:
            # If there isn't a matching tool use, we can't update the result
            raise ValueError(
                f"No matching tool use found for tool call ID {result.execution_id}",
            )

        match_as_tool_use = cast(
            ThreadToolUsageContent,
            self._message.content[match_idx],
        )

        if match_as_tool_use.metadata is None:
            match_as_tool_use.metadata = {}

        # Update the tool use with the result
        match_as_tool_use.started_at = result.execution_started_at
        match_as_tool_use.ended_at = result.execution_ended_at

        # Process the tool result based on its type and structure
        if result.output_raw is None:
            match_as_tool_use.result = None
        elif isinstance(result.output_raw, str):
            # MCP responses are JSON strings - use as-is
            match_as_tool_use.result = result.output_raw
        elif isinstance(result.output_raw, dict) and "result" in result.output_raw:
            # Action responses have a 'result' field that may be a JSON string
            try:
                result.output_raw["result"] = json.loads(result.output_raw["result"])
            except (json.JSONDecodeError, TypeError):
                # Keeping the original value
                pass
            match_as_tool_use.result = json.dumps(result.output_raw)
        elif isinstance(result.output_raw, dict | list):
            # Other structured data - serialize as JSON
            match_as_tool_use.result = json.dumps(result.output_raw)
        else:
            # Fallback for other types
            match_as_tool_use.result = str(result.output_raw)

        match_as_tool_use.error = result.error
        match_as_tool_use.metadata["execution"] = result.execution_metadata
        match_as_tool_use.action_server_run_id = result.action_server_run_id
        match_as_tool_use.status = "failed" if result.error else "finished"

    def copy(self) -> "ThreadMessageWithThreadState":
        """Returns a deep copy of the message with thread state."""
        new_message = self._message.copy()
        return ThreadMessageWithThreadState(
            new_message,
            self._thread_state,
            tag_expected_past_response=self._tag_expected_past_response,
            tag_expected_pre_response=self._tag_expected_pre_response,
        )


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
        self._active_message_content: list[AnyThreadMessageContent] = []
        """The content of the currently active message in the thread."""

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

    @property
    def active_message_content(self) -> list[AnyThreadMessageContent]:
        """The content of the currently active message in the thread."""
        return self._active_message_content

    async def new_agent_message(
        self,
        # TODO: there's some amount of "configuration" here that an agent
        # arch may want to do... there's been a small number of coupling points
        # w/ default arch I'm noticing (as I venture into experimental arch territory)
        tag_expected_past_response: str | None = "step",
        tag_expected_pre_response: str | None = "thinking",
    ) -> ThreadMessageWithThreadState:
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
                datetime.now(UTC),
                0,
                new_message.message_id,
                self._thread_id,
                self._agent_id,
            ),
        )
        self._previous_message_states[new_message.message_id] = None
        self._previous_message_sequence_numbers[new_message.message_id] = 1
        return ThreadMessageWithThreadState(
            new_message,
            self,
            tag_expected_past_response=tag_expected_past_response,
            tag_expected_pre_response=tag_expected_pre_response,
        )

    async def new_user_message(
        self,
        tag_expected_past_response: str | None = "step",
        tag_expected_pre_response: str | None = "thinking",
    ) -> ThreadMessageWithThreadState:
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
                datetime.now(UTC),
                0,
                new_message.message_id,
                self._thread_id,
                self._agent_id,
            ),
        )
        self._previous_message_states[new_message.message_id] = None
        self._previous_message_sequence_numbers[new_message.message_id] = 1
        return ThreadMessageWithThreadState(
            new_message,
            self,
            tag_expected_past_response=tag_expected_past_response,
            tag_expected_pre_response=tag_expected_pre_response,
        )

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
        unwrapped_message = message._message if isinstance(message, ThreadMessageWithThreadState) else message

        # Update the active message content
        self._active_message_content = unwrapped_message.content.copy()

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
            # By normalizing timestamps, we cut down on a ton of noise
            # over-the-wire we get from just timestamp updates
            new=unwrapped_message.with_normalized_timestamps(),
            sequence_number=self._previous_message_sequence_numbers[unwrapped_message.message_id],
        )

        # Finally, we'll send the delta over to the UI or whatever
        # downstream consumer is listening.
        try:
            for delta_object in delta_objects:
                await self._send_delta_event(delta_object)

            # And, finally, we'll update our state to the current message.
            self._previous_message_states[unwrapped_message.message_id] = (
                # By normalizing timestamps, we cut down on a ton of noise
                # over-the-wire we get from just timestamp updates
                unwrapped_message.with_normalized_timestamps()
            )
            self._previous_message_sequence_numbers[unwrapped_message.message_id] += len(delta_objects)
        except Exception as e:
            # If we failed to send the delta, we'll raise an error.
            raise StreamingError(
                f"Failed to send delta for message {unwrapped_message.message_id}",
            ) from e

    async def commit_message(
        self,
        message: ThreadMessageWithThreadState | ThreadMessage,
        ignore_websocket_errors: bool = False,
    ) -> None:
        """Commits a message to the thread state."""
        unwrapped_message = message._message if isinstance(message, ThreadMessageWithThreadState) else message

        websocket_error = None
        storage_error = None

        try:
            sequence_number = 0
            if unwrapped_message.message_id in self._previous_message_sequence_numbers:
                sequence_number = self._previous_message_sequence_numbers[unwrapped_message.message_id]

            try:
                await self._send_delta_event(
                    StreamingDeltaMessageEnd(
                        datetime.now(UTC),
                        sequence_number,
                        unwrapped_message.message_id,
                        self._thread_id,
                        self._agent_id,
                        # Send full message at end? (TBD)
                        unwrapped_message.model_dump(),
                    ),
                )
            except Exception as e:
                websocket_error = e
                # Continue to commit to storage even if websocket fails

            try:
                await self._commit_message_to_storage(unwrapped_message)
            except Exception as e:
                storage_error = e

            if unwrapped_message.message_id in self._previous_message_states:
                del self._previous_message_states[unwrapped_message.message_id]
            if unwrapped_message.message_id in self._previous_message_sequence_numbers:
                del self._previous_message_sequence_numbers[unwrapped_message.message_id]

        finally:
            self._active_message_id = None

        # Handle errors after cleanup
        if storage_error:
            raise Exception(
                f"Failed to commit message {unwrapped_message.message_id} to storage",
            ) from storage_error
        elif websocket_error and not ignore_websocket_errors:
            raise Exception(
                f"Failed to send websocket delta for message {unwrapped_message.message_id}",
            ) from websocket_error

    @abstractmethod
    async def _send_delta_event(self, delta_object: StreamingDeltaMessage) -> None:
        """Sends a delta event to the UI.

        Arguments:
            delta_object: The computed delta between the previous and current
                message state. Contains the changes that need to be sent to the UI.

        Raises:
            StreamingError: If the delta cannot be sent to the UI.
        """

    @abstractmethod
    async def _commit_message_to_storage(self, message: ThreadMessage) -> None:
        """Commits a message to the thread state storage.

        Arguments:
            message: The message to commit to storage.

        Raises:
            Exception: If the message cannot be committed to storage.
        """
