from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from structlog import get_logger

from agent_platform.architectures.experimental.violet.docintel.sampling import (
    DocSampler,
)
from agent_platform.architectures.experimental.violet.docintel.schema import (
    SchemaGenerator,
)
from agent_platform.architectures.experimental.violet.docintel.serialization import (
    DocIntSerializer,
)
from agent_platform.architectures.experimental.violet.docintel.types import (
    DocCard,
    DocIntState,
)
from agent_platform.core.files.mime_types import (
    MIME_TYPE_PDF,
    MIME_TYPE_PPT,
    MIME_TYPE_PPTX,
)

if TYPE_CHECKING:
    from agent_platform.architectures.experimental.violet.state import VioletState
    from agent_platform.core.kernel import Kernel
    from agent_platform.core.kernel_interfaces.thread_state import (
        ThreadMessageWithThreadState,
    )
    from agent_platform.core.thread import ThreadMessage

logger = get_logger(__name__)


class DocIntelManager:
    """
    Central controller for Document Intelligence.
    Manages state hydration, file scanning, sampling, and schema inference.
    """

    def __init__(self, kernel: Kernel, state: VioletState):
        self.kernel = kernel
        self.state = state
        self.serializer = DocIntSerializer()
        self.sampler = DocSampler(kernel, state)
        self.schema_gen = SchemaGenerator(kernel, state)
        self._start_revision = 0

    async def ensure_active_state(self, message: ThreadMessageWithThreadState) -> bool:
        """
        Main entrypoint.
        Returns True if processing should halt (waiting for markup).
        """
        self.hydrate_from_thread()
        added_new = await self._scan_thread_files()

        # Sampling updates state and streams UI placeholders immediately
        await self.sampler.process_sampling(self.state.doc_int, message)

        awaiting_markup = any(c.status != "done" for c in self.state.doc_int.cards)

        # 1. Blocking State: Must persist to CURRENT message so user can interact.
        if awaiting_markup:
            self._set_ui_waiting_state(message)
            await self.persist(message, force_current_message=True)
            return True

        # 2. New Files Detected: Must persist to CURRENT message to announce them.
        if added_new:
            await self.persist(message, force_current_message=True)
            return False

        # 3. Quiet State: Try to update history. If nothing changed, this does nothing.
        await self.persist(message, force_current_message=False)
        return False

    async def process_missing_schemas(self, message: ThreadMessageWithThreadState):
        """
        Identifies cards that are 'done' but missing schemas, and runs inference.
        """
        targets = [c for c in self.state.doc_int.cards if c.status == "done" and not isinstance(c.json_schema, dict)]

        if not targets:
            return

        logger.info("doc_int.processing_schemas", count=len(targets))

        for card in targets:
            usage = await self.schema_gen.emit_tool_start(message, card.file_ref, "")
            result = await self.schema_gen.infer_and_apply(card, message)
            await self.schema_gen.emit_tool_finish(message, usage, card.file_ref, result=result, is_error=False)

            # Update the original message (so "Schema Ready" appears there),
            # keeping the current "Thinking..." message clean.
            await self.persist(message, force_current_message=False)

    def hydrate_from_thread(self) -> None:
        """Reconstructs the DocIntState by reducing all agent messages."""
        thread = self.kernel.thread
        if not thread.messages:
            self.state.doc_int = DocIntState()
            self._start_revision = 0
            return

        card_snapshots: dict[str, list[DocCard]] = defaultdict(list)
        highest_revision = 0

        for msg in thread.messages:
            if getattr(msg, "role", None) != "agent":
                continue

            doc_int = self.serializer.extract_from_message(msg)
            if not doc_int:
                continue

            highest_revision = max(highest_revision, doc_int.revision)
            for card in doc_int.cards:
                card_snapshots[card.file_ref].append(card)

        final_cards = []
        for file_ref, snapshots in card_snapshots.items():
            final_cards.append(self._reconstruct_card_state(file_ref, snapshots))

        self.state.doc_int = DocIntState(revision=highest_revision, cards=final_cards, prompt_payload="")
        self._start_revision = highest_revision

    def _reconstruct_card_state(self, file_ref: str, snapshots: list[DocCard]) -> DocCard:
        base = DocCard(file_ref=file_ref, file_id="", mime_type="")

        for snap in snapshots:
            base.file_id = snap.file_id or base.file_id
            base.mime_type = snap.mime_type or base.mime_type
            base.size_bytes = snap.size_bytes or base.size_bytes

            if snap.status:
                base.status = snap.status
            if snap.json_schema:
                base.json_schema = snap.json_schema
            if len(snap.sampled_pages) >= len(base.sampled_pages):
                base.sampled_pages = snap.sampled_pages

            base.revision = max(base.revision, snap.revision)
            base.updated_at = snap.updated_at or base.updated_at
            base.comments = self._merge_comments(base.comments, snap.comments)

        return base

    async def persist(self, message: ThreadMessageWithThreadState, force_current_message: bool = False):
        """
        Persists state to storage.

        Logic:
        1. If `force_current_message` is True, writes to the current message.
        2. If changes occurred (`revision > start_revision`), tries to write to the
           LATEST PREVIOUS message that has doc_int.
        3. If no previous message is found, falls back to the current message.
        4. If no changes and no force, DOES NOTHING (keeps metadata clean).
        """
        from agent_platform.server.storage.option import StorageService

        storage = StorageService.get_instance()

        has_changes = self.state.doc_int.revision > self._start_revision
        target_message: ThreadMessage | None = None
        is_current = False

        if force_current_message:
            target_message = message.message
            is_current = True
        elif has_changes:
            # Try to find a history anchor
            history_anchor = self._find_history_anchor()
            if history_anchor:
                target_message = history_anchor
                is_current = False
            else:
                # Fallback to current if we can't find where to put it
                logger.warning("doc_int.persist.history_gap: No anchor found, defaulting to current.")
                target_message = message.message
                is_current = True
        else:
            # No changes, no force -> Do nothing.
            return

        if target_message:
            # Stamp the data
            self.serializer.apply_to_message(target_message, self.state.doc_int)

            # If we are writing to the current message in-flight, stream the delta
            if is_current:
                await message.stream_delta()

            # Commit to DB (saves the update to history OR the current message)
            try:
                await storage.upsert_thread(self.kernel.user.user_id, self.kernel.thread)
            except Exception:
                logger.exception("Failed to persist doc_int")

    def _find_history_anchor(self) -> ThreadMessage | None:
        """
        Finds the most recent Agent message in history that already contains doc_int data.
        """
        thread = self.kernel.thread
        if not thread.messages:
            return None

        current_msg_id = getattr(self.kernel.thread_state, "message_id", None)

        for msg in reversed(thread.messages):
            if getattr(msg, "role", None) != "agent":
                continue
            # Skip the current in-flight message
            if getattr(msg, "message_id", "") == current_msg_id:
                continue

            # Check if this message hosts doc data
            meta = getattr(msg, "agent_metadata", {}) or {}
            if "doc_int" in meta:
                return msg

        return None

    # --- Internals ---

    async def _scan_thread_files(self) -> bool:
        from agent_platform.server.storage.option import StorageService

        storage = StorageService.get_instance()
        try:
            files = await storage.get_thread_files(self.kernel.thread_state.thread_id, self.kernel.user.user_id)
        except Exception:
            return False

        existing_refs = {c.file_ref for c in self.state.doc_int.cards}
        added = False
        allowed = {MIME_TYPE_PDF, MIME_TYPE_PPT, MIME_TYPE_PPTX}

        for f in files:
            if f.mime_type not in allowed or f.file_ref in existing_refs:
                continue
            new_card = DocCard(
                file_ref=f.file_ref,
                file_id=f.file_id,
                mime_type=f.mime_type,
                size_bytes=f.file_size_raw,
                status="pending_markup",
            )
            self.state.doc_int.cards.append(new_card)
            self.state.doc_int.revision += 1
            added = True

        return added

    def _set_ui_waiting_state(self, message: ThreadMessageWithThreadState):
        from agent_platform.core.thread.content import ThreadTextContent

        message.message.content.append(
            ThreadTextContent(text="Waiting for PDF markup. Open the document cards and mark each as done.")
        )
        self.state.step = "gathering-pdf-context"

    def _merge_comments(self, base, incoming):
        merged = list(base)
        existing_keys = {(c.comment, c.updated_at) for c in base}
        for c in incoming:
            if (c.comment, c.updated_at) not in existing_keys:
                merged.append(c)
                existing_keys.add((c.comment, c.updated_at))
        return merged
