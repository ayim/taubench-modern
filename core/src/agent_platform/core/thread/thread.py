from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from agent_platform.core.thread.base import ThreadMessage
from agent_platform.core.utils.dataclass_meta import TolerantDataclass


def _deep_merge_dicts(base: dict | None, incoming: dict | None) -> dict:
    if base is None:
        base = {}
    if incoming is None:
        return dict(base)

    merged = dict(base)
    for key, value in incoming.items():
        existing = merged.get(key)
        if isinstance(existing, dict) and isinstance(value, Mapping):
            merged[key] = _deep_merge_dicts(existing, dict(value))
        else:
            merged[key] = value
    return merged


@dataclass
class Thread(TolerantDataclass):
    """Represents an entire conversation (thread) consisting of multiple messages
    with multiple content types (text, tool usage, vega chart, etc.) nested within
    each message.

    Thread is a key concept and DISTINCT from PromptMessage (even if there is a
    structural similarity). The result of an LLM call may end up as (part) of a message
    in a thread; and, similarly, content in a ThreadMessage (or many messages) may be
    converted and used in PromptMessages to pass to an LLM. But, for the sake of
    clarity, we have kept seperate distinct types for ThreadMessages and
    PromptMessages.
    """

    user_id: str = field(
        metadata={"description": "The user ID of the user who created this thread."},
    )
    """The user ID of the user who created this thread."""

    agent_id: str = field(
        metadata={"description": "The agent ID of the agent that created this thread."},
    )
    """The agent ID of the agent that created this thread."""

    name: str = field(metadata={"description": "The name of this thread."})
    """The name of this thread."""

    thread_id: str = field(
        default_factory=lambda: str(uuid4()),
        metadata={"description": "A unique ID for this thread."},
    )
    """A unique ID for this thread."""

    messages: list[ThreadMessage] = field(
        default_factory=list,
        metadata={"description": "All messages in this thread."},
    )
    """All messages in this thread."""

    created_at: datetime = field(
        default_factory=lambda: datetime.now(UTC),
        metadata={"description": "When this thread was created."},
    )
    """When this thread was created."""

    updated_at: datetime = field(
        default_factory=lambda: datetime.now(UTC),
        metadata={"description": "When this thread was last updated."},
    )
    """When this thread was last updated."""

    metadata: dict = field(
        default_factory=dict,
        metadata={"description": "Arbitrary thread-level metadata."},
    )
    """Arbitrary thread-level metadata."""

    trial_id: str | None = field(
        default=None,
        metadata={"description": "Evaluation trial that originated this thread, if any."},
    )
    """Evaluation trial that originated this thread, if any."""

    work_item_id: str | None = field(
        default=None,
        metadata={"description": "The work item ID associated with this thread."},
    )
    """The work item ID associated with this thread."""

    def add_message(self, message: ThreadMessage) -> None:
        """Adds a new message to the thread.  Updates `updated_at` to reflect
        that the thread has changed.
        """
        self.messages.append(message)
        self.updated_at = datetime.now(UTC)

    def find_message(self, message_id: str) -> ThreadMessage | None:
        """Helper to locate a message by its UID.  Returns None if not found."""
        for msg in self.messages:
            if msg.message_id == message_id:
                return msg
        return None

    def copy(self) -> "Thread":
        """Returns a deep copy of the thread."""
        return Thread(
            user_id=self.user_id,
            agent_id=self.agent_id,
            name=self.name,
            thread_id=self.thread_id,
            messages=[msg.copy() for msg in self.messages],
            created_at=self.created_at,
            updated_at=self.updated_at,
            metadata=self.metadata,
            trial_id=self.trial_id,
            work_item_id=self.work_item_id,
        )

    def model_dump(self) -> dict:
        """Serializes the thread to a dictionary.  Useful for JSON serialization."""
        return {
            "thread_id": self.thread_id,
            "user_id": self.user_id,
            "agent_id": self.agent_id,
            "name": self.name,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
            "trial_id": self.trial_id,
            "work_item_id": self.work_item_id,
            "messages": [msg.model_dump() for msg in self.messages],
        }

    def get_last_n_messages(self, n: int) -> list[ThreadMessage]:
        """Get the last n messages from the thread."""
        return self.messages[-n:]

    def get_last_n_message_turns(self, n: int) -> list[ThreadMessage]:
        """
        Return the most recent ``n`` "turns" from this thread, in a flattened list.

        **Definition of a turn (working backward from the newest message):**
        1) Look at the last (newest) message's role (e.g., "agent").
        2) Gather *all* consecutive messages of that same role from the end.
        3) Then immediately gather *all* consecutive messages of the opposite role
            that appear right before that block, if any.
        4) Combine them into one "turn."

        Keep doing this for the next chunk of messages until you have collected
        ``n`` turns or run out of messages.

        The final return value flattens these turns (oldest turn first, then the
        second-oldest, etc.), and **within each turn** the messages are in ascending
        chronological order. (So, essentially, you get a chronological slice of
        the thread messages, oldest to newest, but chopped into turns, limited to
        the last ``n`` turns, and then recombined into a flat list.)

        **Example:**
        Suppose the full conversation (oldest → newest) has roles:
        [user(1), agent(2), agent(3), user(4), user(5), agent(6), agent(7), agent(8)]

        - Newest message is agent(8). Step 2 collects [agent(8), agent(7), agent(6)].
        - Step 3 collects the user messages right before them: [user(5), user(4)].
        - So the *most recent turn* is [user(4), user(5), agent(6), agent(7), agent(8)]
          when put in ascending chronological order.
        - The remaining older messages are [user(1), agent(2), agent(3)].

        Repeating the process:
          - Last (newest of the leftover) is agent(3) → gather [agent(3), agent(2)]
          - Then gather preceding user(1).
          - So the *second-most-recent turn* is [user(1), agent(2), agent(3)].

        If you request ``n=1``, you get just the latest turn:

        [user(4), user(5), agent(6), agent(7), agent(8)]

        If you request ``n=2``, you get both turns flattened (with the oldest turn
        first, then the second-oldest):

        [
            user(1), agent(2), agent(3),
            user(4), user(5), agent(6), agent(7), agent(8),
        ]

        Args:
            n: The number of turns to retrieve.

        Returns:
            A **flat list** of the last ``n`` turns, with each turn's messages in
            chronological order, and the oldest turn placed first in the returned list.
        """
        # No messages? No turns.
        if not self.messages:
            return []

        turns: list[list[ThreadMessage]] = []
        # We'll copy the list so we can pop from the end
        messages = self.messages[:]
        current_turn: list[ThreadMessage] = []

        # Process from newest to oldest until we have n turns
        while messages and len(turns) < n:
            if not current_turn:
                # Start the turn with the newest message
                current_turn = [messages.pop()]

            # Keep adding messages of the same role
            while messages and messages[-1].role == current_turn[0].role:
                current_turn.append(messages.pop())

            # Then gather opposite-role messages (if any) directly preceding it
            if messages:
                opposite_role = "user" if current_turn[0].role == "agent" else "agent"
                opposite_msgs: list[ThreadMessage] = []

                while messages and messages[-1].role == opposite_role:
                    opposite_msgs.append(messages.pop())

                if opposite_msgs:
                    current_turn.extend(opposite_msgs)

            # We have one complete "turn"
            turns.append(current_turn)
            current_turn = []

        # Now flatten the turns (oldest turn first; restore
        # chronological order within each turn)
        result: list[ThreadMessage] = []
        for turn in reversed(turns):
            # 'turn' was collected newest-first, so reverse
            # it to get oldest→newest in that chunk
            result.extend(reversed(turn))

        # Now we have the turns each in chronological order, and
        # the sequence of turns is oldest→newest.
        return result

    @property
    def latest_user_message_as_text(self) -> str:
        """Get the latest user message as text."""
        latest_user_message = next(
            (msg for msg in reversed(self.messages) if msg.role == "user"),
            None,
        )
        if latest_user_message is None:
            return ""

        as_text = ""
        for content in latest_user_message.content:
            if content.kind == "text":
                as_text += getattr(content, "text", "")

        return as_text

    def is_associated_with_workitem(self) -> bool:
        return self.work_item_id is not None

    def is_user_named(self) -> bool:
        user_named = self.metadata.get("thread_name", {}).get("user_named")
        if user_named is None:
            return False
        return user_named

    def auto_naming_disabled(self) -> bool:
        auto_naming_enabled = self.metadata.get("thread_name", {}).get("enable_auto_naming")
        if auto_naming_enabled is None:
            return False
        return not auto_naming_enabled

    def has_been_auto_named(self) -> bool:
        auto_named_at = self.metadata.get("thread_name", {}).get("auto_named_at")
        return auto_named_at is not None

    def set_user_named(self, is_user_named: bool = True) -> None:
        if "thread_name" not in self.metadata:
            self.metadata["thread_name"] = {}
        self.metadata["thread_name"]["user_named"] = is_user_named

    def update_metadata(self, metadata_to_merge: dict) -> dict:
        self.metadata = _deep_merge_dicts(self.metadata, metadata_to_merge)
        return self.metadata

    @classmethod
    def model_validate(cls, data: dict) -> "Thread":
        """Create a thread from a dictionary."""
        data = data.copy()
        messages = [
            ThreadMessage.model_validate(msg) if isinstance(msg, dict) else msg for msg in data.pop("messages", [])
        ]
        if "thread_id" in data and isinstance(data["thread_id"], UUID):
            data["thread_id"] = str(data["thread_id"])
        if "user_id" in data and isinstance(data["user_id"], UUID):
            data["user_id"] = str(data["user_id"])
        if "agent_id" in data and isinstance(data["agent_id"], UUID):
            data["agent_id"] = str(data["agent_id"])
        if "created_at" in data and isinstance(data["created_at"], str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if "updated_at" in data and isinstance(data["updated_at"], str):
            data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        if "trial_id" in data and isinstance(data["trial_id"], UUID):
            data["trial_id"] = str(data["trial_id"])
        return cls(**data, messages=messages)
