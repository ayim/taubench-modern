import logging
from typing import Any

from reducto.types.shared import ParseResponse

from agent_platform.architectures.experimental.violet.docintel.types import (
    DocCard,
    DocComment,
    DocIntState,
    DocSampledPage,
)
from agent_platform.core.thread import ThreadMessage

logger = logging.getLogger(__name__)


class DocIntSerializer:
    """
    Handles converting DocIntState/DocCards to and from raw dictionary formats
    suitable for agent_metadata persistence and UI streaming.
    """

    def extract_from_message(self, message: ThreadMessage) -> DocIntState | None:
        """
        Safely extracts and deserializes DocIntState from a message object.
        Returns None if metadata is missing or malformed.
        """
        meta = message.agent_metadata
        if not meta:
            return None

        return self.deserialize_state(meta.get("doc_int"))

    def extract_from_message_or_create(self, message: ThreadMessage) -> DocIntState:
        """
        Safely extracts and deserializes DocIntState from a message object.
        Returns a default state if metadata is missing or malformed.
        """
        meta = message.agent_metadata
        if not meta:
            return DocIntState()
        return self.deserialize_state(meta.get("doc_int"))

    def apply_to_message(self, message: ThreadMessage, state: DocIntState) -> None:
        """
        Serializes state and patches the message metadata.
        Sets both the compacted 'doc_int' (for persistence) and the
        'doc_cards' list (for UI convenience).
        """
        serialized_state = self.serialize_state(state)
        serialized_cards = serialized_state["cards"]

        # The full state object
        message.agent_metadata["doc_int"] = serialized_state

        # UI-friendly flat lists (redundant but often expected by frontend hooks)
        message.agent_metadata["doc_cards"] = serialized_cards
        message.agent_metadata["doc_int_revision"] = state.revision
        message.agent_metadata["doc_int_input_locked"] = any(c.status != "done" for c in state.cards)

    # --- Serialization (Object -> Dict) ---

    def serialize_state(self, state: DocIntState) -> dict[str, Any]:
        return {
            "revision": state.revision,
            "cards": [self.serialize_card(c) for c in state.cards],
            "prompt_payload": state.prompt_payload,
            "version": 1,
        }

    def serialize_card(self, card: DocCard) -> dict[str, Any]:
        return {
            "file_ref": card.file_ref,
            "file_id": card.file_id,
            "mime_type": card.mime_type,
            "size_bytes": card.size_bytes,
            "status": card.status,
            "sampled_pages": [self._serialize_sampled_page(p) for p in card.sampled_pages],
            "comments": [self._serialize_comment(c) for c in card.comments],
            "json_schema": card.json_schema,
            "error": card.error,
            "updated_at": card.updated_at,
            "revision": card.revision,
        }

    def _serialize_sampled_page(self, page: DocSampledPage) -> dict[str, Any]:
        parse_data_out: Any = {}

        # Handle Reducto Pydantic models vs Dicts vs None
        if page.parse_data:
            try:
                if hasattr(page.parse_data, "model_dump"):
                    parse_data_out = page.parse_data.model_dump()
                elif hasattr(page.parse_data, "dict"):
                    parse_data_out = page.parse_data.dict()  # type: ignore
                else:
                    parse_data_out = page.parse_data
            except Exception:
                logger.warning(f"Failed to serialize parse_data page={page.page} type={type(page.parse_data)}")
                parse_data_out = {}

        return {
            "page": page.page,
            "status": page.status,
            "summary": page.summary,
            "parse_data": parse_data_out,
        }

    def _serialize_comment(self, comment: DocComment) -> dict[str, Any]:
        return {
            "comment": comment.comment,
            "updated_at": comment.updated_at,
            "anchor": comment.anchor,
        }

    # --- Deserialization (Dict -> Object) ---

    def deserialize_state(self, raw: Any) -> DocIntState:
        if not isinstance(raw, dict):
            return DocIntState()

        cards_raw = raw.get("cards")
        cards: list[DocCard] = []
        if isinstance(cards_raw, list):
            for entry in cards_raw:
                parsed = self.deserialize_card(entry)
                if parsed is not None:
                    cards.append(parsed)

        return DocIntState(
            revision=int(raw.get("revision", 0)),
            cards=cards,
            prompt_payload=raw.get("prompt_payload", ""),
        )

    def deserialize_card(self, raw: Any) -> DocCard | None:
        if not isinstance(raw, dict):
            return None

        # Mandatory fields
        file_ref = raw.get("file_ref")
        if not isinstance(file_ref, str):
            return None

        # Optional / Defaulted fields
        file_id = raw.get("file_id", "")
        mime_type = raw.get("mime_type", "")

        # Recursive Lists
        sampled_pages = []
        if raw_pages := raw.get("sampled_pages"):
            if isinstance(raw_pages, list):
                for p in raw_pages:
                    if sp := self._deserialize_sampled_page(p):
                        sampled_pages.append(sp)

        comments = []
        if raw_comments := raw.get("comments"):
            if isinstance(raw_comments, list):
                for c in raw_comments:
                    if cm := self._deserialize_comment(c):
                        comments.append(cm)

        # Schema validation
        schema = raw.get("json_schema")
        if not isinstance(schema, dict):
            schema = None

        return DocCard(
            file_ref=file_ref,
            file_id=str(file_id),
            mime_type=str(mime_type),
            size_bytes=raw.get("size_bytes"),
            status=raw.get("status", "pending_markup"),
            sampled_pages=sampled_pages,
            comments=comments,
            json_schema=schema,
            error=raw.get("error"),
            updated_at=raw.get("updated_at"),
            revision=int(raw.get("revision", 0)),
        )

    def _deserialize_sampled_page(self, raw: Any) -> DocSampledPage | None:
        if not isinstance(raw, dict):
            return None

        page_num = raw.get("page")
        if not isinstance(page_num, int):
            return None

        # Attempt to rehydrate Reducto ParseResponse
        parse_data = None
        raw_parse = raw.get("parse_data")
        if isinstance(raw_parse, dict):
            try:
                parse_data = ParseResponse.model_validate(raw_parse)
            except Exception:
                # If model validation fails, we might have partial data or schema drift.
                # Ideally, we log this but don't crash the whole thread load.
                # For now, we leave it as None or could store raw dict if type allowed.
                parse_data = None

        return DocSampledPage(
            page=page_num,
            status=raw.get("status", "pending"),
            summary=raw.get("summary"),
            parse_data=parse_data,
        )

    def _deserialize_comment(self, raw: Any) -> DocComment | None:
        if not isinstance(raw, dict):
            return None

        text = raw.get("comment")
        if not isinstance(text, str):
            return None

        return DocComment(comment=text, updated_at=raw.get("updated_at"), anchor=raw.get("anchor"))
