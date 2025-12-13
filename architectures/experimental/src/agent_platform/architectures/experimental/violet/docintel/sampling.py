import asyncio
import logging
import math
from datetime import UTC, datetime
from typing import Any, Literal

from agent_platform.architectures.experimental.violet.docintel.serialization import (
    DocIntSerializer,
)
from agent_platform.architectures.experimental.violet.docintel.types import (
    DocCard,
    DocIntState,
    DocSampledPage,
)
from agent_platform.architectures.experimental.violet.reducto import VioletReductoClient
from agent_platform.architectures.experimental.violet.state import VioletState
from agent_platform.core.integrations.settings.reducto import ReductoSettings
from agent_platform.core.kernel import Kernel
from agent_platform.core.kernel_interfaces.thread_state import (
    ThreadMessageWithThreadState,
)
from agent_platform.core.utils import SecretString
from agent_platform.server.data_frames.data_reader import (
    _get_file_contents,
    get_file_metadata,
)
from agent_platform.server.storage.errors import IntegrationNotFoundError
from agent_platform.server.storage.option import StorageService

logger = logging.getLogger(__name__)


class DocSampler:
    """
    Manages the 'Sampling' phase: extracting 3-10 pages from a PDF/PPT
    to generate previews for the UI so the user can verify fields.
    """

    def __init__(self, kernel: Kernel, state: VioletState):
        self.kernel = kernel
        self.state = state
        self.serializer = DocIntSerializer()
        # Limit concurrent Reducto calls to avoid rate limits
        self.semaphore = asyncio.Semaphore(5)

    async def process_sampling(
        self,
        doc_int_state: DocIntState,
        message: ThreadMessageWithThreadState,
    ) -> None:
        """
        Scans all cards. If a card is 'pending_markup' but has no sampled pages,
        it triggers the sampling workflow (upload -> parse specific pages).
        """
        tasks = []
        updated_any = False

        for card in doc_int_state.cards:
            # Skip if already sampled or fully done
            if card.sampled_pages:
                continue
            if card.status not in {"pending_markup", "in_progress"}:
                continue

            # Start sampling for this card
            tasks.append(self._sample_single_card(card, message))
            updated_any = True

        if updated_any:
            await asyncio.gather(*tasks)

    async def _sample_single_card(self, card: DocCard, message: ThreadMessageWithThreadState) -> None:
        """
        Orchestrates sampling for one file:
        1. Fetch content
        2. Pick pages
        3. Stream 'pending' placeholders to UI
        4. Upload & Parse
        5. Stream results
        """
        try:
            # 1. Fetch File Content & Metadata
            storage = StorageService.get_instance()
            file_metadata = await get_file_metadata(
                user_id=self.kernel.user.user_id,
                thread_id=self.kernel.thread_state.thread_id,
                storage=storage,
                file_ref=card.file_ref,
            )
            file_contents = await _get_file_contents(
                user_id=self.kernel.user.user_id,
                thread_id=self.kernel.thread_state.thread_id,
                storage=storage,
                file_metadata=file_metadata,
            )
        except Exception as exc:
            logger.exception(f"Failed to load file for sampling file_ref={card.file_ref} error={exc!s}")
            await self._mark_card_error(card, message)
            return

        # 2. Configure Reducto
        client = await self._get_reducto_client(storage)
        if not client:
            # If no Reducto, we can't sample. Just leave it or mark error.
            logger.warning("Reducto not configured; skipping sampling")
            return

        # 3. Determine Pages to Sample
        page_count = self._get_pdf_page_count(file_contents, getattr(file_metadata, "file_path", None))
        pages_to_sample = self._pick_sample_pages(page_count or 0)

        # 4. Set Placeholders & Stream (User sees "Loading..." bubbles)
        card.sampled_pages = [
            DocSampledPage(page=page_no, status="pending", summary=None, parse_data=None) for page_no in pages_to_sample
        ]
        card.status = "in_progress"
        self._touch_revision(card)
        await self._stream_update(message)

        try:
            # 5. Upload Document
            uploaded_doc = await client.upload((file_metadata.file_ref, file_contents))

            # 6. Parse Pages Concurrently
            parse_tasks = []
            for page_no in pages_to_sample:
                parse_tasks.append(self._parse_page_task(client, uploaded_doc, card, page_no, message))

            results = await asyncio.gather(*parse_tasks)

            # 7. Final Status Update
            success_count = sum(1 for r in results if r)
            card.status = "pending_markup" if success_count > 0 else "error"
            self._touch_revision(card)
            await self._stream_update(message)

        except Exception:
            logger.exception(f"Sampling workflow failed file_ref={card.file_ref}")
            await self._mark_card_error(card, message)

    async def _parse_page_task(
        self,
        client: VioletReductoClient,
        uploaded_doc: Any,
        card: DocCard,
        page_no: int,
        message: ThreadMessageWithThreadState,
    ) -> bool:
        """
        Parses a single page and updates the specific DocSampledPage entry.
        Streams updates (pending -> parsing -> parsed).
        """
        # Set status to 'parsing'
        self._update_page_status(card, page_no, "parsing")
        await self._stream_update(message)

        async with self.semaphore:
            try:
                # Construct Options (Parse just this page)
                # Note: We rely on `reducto` types being available at runtime
                from reducto.types import ParseRunParams

                options = {
                    "document_url": "unset",
                    "advanced_options": {"page_range": {"start": page_no, "end": page_no}},
                }

                # Run Parse
                parse_response = await client.parse(
                    parse_options=ParseRunParams(**options),
                    uploaded_document=uploaded_doc,
                )

                # Update State with Success
                for sp in card.sampled_pages:
                    if sp.page == page_no:
                        sp.status = "parsed"
                        sp.parse_data = parse_response
                        break

                self._touch_revision(card)
                await self._stream_update(message)
                return True

            except Exception as exc:
                logger.exception(f"Page parse failed page={page_no} file_ref={card.file_ref} error={exc!s}")
                self._update_page_status(card, page_no, "error")
                await self._stream_update(message)
                return False

    async def _get_reducto_client(self, storage) -> VioletReductoClient | None:
        try:
            integration = await storage.get_integration_by_kind("reducto")
            settings = integration.settings
            if not isinstance(settings, ReductoSettings):
                return None

            api_key = (
                settings.api_key.get_secret_value()
                if isinstance(settings.api_key, SecretString)
                else str(settings.api_key)
            )
            return VioletReductoClient(api_url=settings.endpoint, api_key=api_key)
        except (IntegrationNotFoundError, Exception) as exc:
            logger.exception(f"Failed to get reducto client error={exc!s}")
            return None

    def _pick_sample_pages(self, page_count: int) -> list[int]:
        """
        Heuristic to pick a spread of pages (start, middle, end)
        to give the user a good overview.
        """
        if page_count <= 0:
            return [1, 2, 3]

        # Target roughly 10% or 3 pages, cap at 12
        num_samples = max(3, math.ceil(page_count * 0.10))
        num_samples = min(num_samples, 12)

        if page_count <= num_samples:
            return list(range(1, page_count + 1))

        step = page_count / (num_samples - 1)
        pages = [1]
        for i in range(1, num_samples - 1):
            pages.append(min(page_count, max(1, round(1 + i * step))))
        pages.append(page_count)

        return sorted(set(pages))

    def _get_pdf_page_count(self, file_bytes: bytes, file_path: str | None) -> int | None:
        """Attempts to read PDF page count from bytes or path."""
        try:
            from io import BytesIO

            from pypdf import PdfReader

            return len(PdfReader(BytesIO(file_bytes)).pages)
        except Exception as exc:
            logger.exception(f"Failed to get PDF page count file_path={file_path} error={exc!s}")
            pass

        if file_path:
            try:
                from pypdf import PdfReader

                return len(PdfReader(file_path).pages)
            except Exception:
                pass
        return None

    def _update_page_status(
        self, card: DocCard, page_no: int, status: Literal["pending", "parsing", "parsed", "error"]
    ):
        for sp in card.sampled_pages:
            if sp.page == page_no:
                sp.status = status
                break
        self._touch_revision(card)

    async def _mark_card_error(self, card: DocCard, message: ThreadMessageWithThreadState):
        card.status = "error"
        self._touch_revision(card)
        await self._stream_update(message)

    def _touch_revision(self, card: DocCard):
        now_str = datetime.now(UTC).isoformat(timespec="milliseconds")
        card.updated_at = now_str
        card.revision += 1
        self.state.doc_int.revision += 1

    async def _stream_update(self, message: ThreadMessageWithThreadState):
        """
        Pushes a delta update to the UI.
        We use the serializer here to ensure the format matches what the frontend expects.
        """
        payload = self.serializer.serialize_state(self.state.doc_int)

        message.agent_metadata["doc_cards"] = payload["cards"]
        message.agent_metadata["doc_int_revision"] = payload["revision"]
        # If any card is not done, input is locked
        message.agent_metadata["doc_int_input_locked"] = any(c.status != "done" for c in self.state.doc_int.cards)
        await message.stream_delta()
