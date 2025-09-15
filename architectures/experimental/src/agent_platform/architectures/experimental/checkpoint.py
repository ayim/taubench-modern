import logging
from copy import deepcopy
from typing import Any, Protocol

import httpx

from agent_platform.core.agent_architectures.state import PendingToolCall
from agent_platform.core.kernel_interfaces.thread_state import (
    ThreadMessageWithThreadState,
)
from agent_platform.core.thread.base import AnyThreadMessageContent

logger = logging.getLogger(__name__)

# Treat these as transient mid-stream failures worth retrying.
RETRYABLE_STREAM_ERRORS = (
    httpx.RemoteProtocolError,
    httpx.ReadError,
    httpx.TransportError,
)


def is_transient_stream_error(exc: Exception) -> bool:
    # You can widen this if your platform raises a different wrapper (e.g., StreamingError)
    return isinstance(exc, RETRYABLE_STREAM_ERRORS)


class _HasPendingToolCalls(Protocol):
    """Protocol for state objects that expose pending tool-calls.

    Only the ability to slice/truncate the sequence is required.
    """

    pending_tool_calls: list[PendingToolCall]


class CheckpointTxn:
    """Checkpoint + rollback around a single streamed LLM step.

    - Streams go out immediately (no buffering).
    - On failure: revert message content + truncate pending_tool_calls, send a revert delta.
    - Idempotent finalize: ``commit()`` and ``rollback()`` are safe to call
      multiple times; after the first finalize, subsequent calls are no-ops.
      This supports streaming try/except blocks that may encounter late errors.
    """

    def __init__(self, message: ThreadMessageWithThreadState, state: _HasPendingToolCalls):
        # message is ThreadMessageWithThreadState
        # state is your Exp1State (has .pending_tool_calls)
        self.message: ThreadMessageWithThreadState = message
        self.state: _HasPendingToolCalls = state
        # Deep snapshot of the message object we're mutating during stream
        # (content includes thoughts, text, tool usages, etc.)
        self._snapshot_content: list[AnyThreadMessageContent] = deepcopy(message._message.content)
        # If you mutate agent_metadata during a turn, snapshot it too:
        self._snapshot_agent_metadata: dict[str, Any] = deepcopy(message._message.agent_metadata)
        # Truncate point for pending tool calls
        self._pending_len: int = len(state.pending_tool_calls)
        self._active: bool = True

    async def rollback(self) -> None:
        """Restore message and pending tool-calls to the checkpoint and send a revert delta."""
        if not self._active:
            return
        # Restore message content/metadata to the exact checkpoint
        msg = self.message._message
        msg.content = deepcopy(self._snapshot_content)
        msg.agent_metadata = deepcopy(self._snapshot_agent_metadata)

        # Truncate newly discovered tool calls
        if self.state.pending_tool_calls:
            del self.state.pending_tool_calls[self._pending_len :]

        # Log the rollback
        # Note: avoid using key 'message' in extra to prevent LogRecord conflicts
        logger.info(
            f"Rolling back to checkpoint: {self.message._message}",
        )

        # Emit one delta that reverts the UI to the checkpointed state
        await self.message.stream_delta()

        self._active = False

    def commit(self) -> None:
        """Mark the checkpoint as done (no state change needed; we already streamed live)."""
        self._active = False
