from datetime import UTC, datetime

from agent_platform.core.delta import compute_generic_deltas
from agent_platform.core.streaming.delta import StreamingDeltaMessageContent
from agent_platform.core.thread.base import ThreadMessage


def compute_message_delta(
    old: ThreadMessage | None,
    new: ThreadMessage,
    sequence_number: int,
) -> list[StreamingDeltaMessageContent]:
    """Compute the delta between two messages.

    This function will compute the delta between two messages. It will
    return a StreamingDelta object that contains the delta between the
    two messages.

    Arguments:
        old: The old message (or None if we've never seen this message before).
        new: The new message.

    Returns:
        The delta between the two messages.
    """

    old_as_dict = old.model_dump() if old is not None else {}
    new_as_dict = new.model_dump()

    # We will IGNORE updated_at in the delta computation
    if "updated_at" in old_as_dict:
        old_as_dict.pop("updated_at")
    if "updated_at" in new_as_dict:
        new_as_dict.pop("updated_at")

    deltas: list[StreamingDeltaMessageContent] = []
    for i, delta in enumerate(compute_generic_deltas(old_as_dict, new_as_dict)):
        deltas.append(
            StreamingDeltaMessageContent(
                sequence_number=sequence_number + i,
                message_id=new.message_id,
                timestamp=datetime.now(UTC),
                delta=delta,
            ),
        )

    return deltas
