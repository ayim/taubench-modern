import logging
from datetime import UTC, datetime
from typing import Any

from agent_platform.architectures.experimental.violet.docintel.serialization import (
    DocIntSerializer,
)
from agent_platform.architectures.experimental.violet.docintel.types import (
    DocCard,
    DocComment,
    DocIntState,
)

logger = logging.getLogger(__name__)


async def apply_doc_int_ops(
    *,
    storage: Any,
    thread: Any,
    message: Any,
    user_id: str,
    ops: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Applies UI operations (comments, status updates) to a specific agent message.
    """
    serializer = DocIntSerializer()

    # 1. Hydrate state
    state = serializer.extract_from_message_or_create(message)
    any_changes = False
    now_str = datetime.now(UTC).isoformat(timespec="milliseconds")

    # 2. Process Operations
    for op in ops:
        file_ref = op.get("file_ref")
        if not isinstance(file_ref, str):
            continue

        # Find card
        card = next((c for c in state.cards if c.file_ref == file_ref), None)
        if not card:
            continue

        # Dispatch
        op_changed = False
        match op.get("op"):
            case "doc_int/set_status":
                op_changed = _handle_set_status(card, op)
            case "doc_int/add_comment":
                op_changed = _handle_add_comment(card, op, now_str)
            case "doc_int/delete_comment":
                op_changed = _handle_delete_comment(card, op)
            case _:
                logger.warning(f"Unknown doc_int op: {op.get('op')}")

        # Centralized revision management
        if op_changed:
            _touch_card(state, card, now_str)
            any_changes = True

    # 3. Persist if Changed
    if any_changes:
        try:
            serializer.apply_to_message(message, state)
            await storage.upsert_thread(user_id, thread)
        except Exception:
            logger.exception("Failed to persist doc_int ops")

    # 4. Serialize Response
    serialized_full = serializer.serialize_state(state)
    return {
        "doc_int": serialized_full,
        "doc_cards": serialized_full["cards"],
        "doc_int_revision": state.revision,
        "doc_int_input_locked": any(c.status != "done" for c in state.cards),
    }


# --- Handlers ---


def _handle_set_status(card: DocCard, op: dict[str, Any]) -> bool:
    status = op.get("status")
    allowed = {"pending_markup", "in_progress", "done", "error"}

    if status not in allowed:
        return False

    if card.status == status:
        return False

    card.status = status
    return True


def _handle_add_comment(card: DocCard, op: dict[str, Any], now_str: str) -> bool:
    text = op.get("comment")
    if not isinstance(text, str) or not text.strip():
        return False

    new_comment = DocComment(comment=text, updated_at=now_str, anchor=op.get("anchor"))
    card.comments.append(new_comment)
    return True


def _handle_delete_comment(card: DocCard, op: dict[str, Any]) -> bool:
    if not card.comments:
        return False

    field_id = op.get("field_id")
    original_count = len(card.comments)

    if field_id:
        # Filter out the comment with the matching field_id
        card.comments = [
            c
            for c in card.comments
            if not (isinstance(c.anchor, dict) and c.anchor.get("field_id") == field_id)
        ]
    else:
        # Fallback: remove the last comment if no ID provided
        card.comments = card.comments[:-1]

    return len(card.comments) != original_count


def _touch_card(state: DocIntState, card: DocCard, now_str: str) -> None:
    """Updates timestamps and revisions when a change occurs."""
    card.updated_at = now_str
    card.revision += 1
    state.revision += 1
