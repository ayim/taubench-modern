from importlib.metadata import version

from agent_platform.architectures.experimental.violet.state import VioletState
from agent_platform.core import Kernel
from agent_platform.core import agent_architectures as aa

__author__ = "Sema4.ai Engineering"
__copyright__ = "Copyright 2025, Sema4.ai"
__license__ = "Proprietary"
__summary__ = "Project Violet experimental agent architecture"
__version__ = version("agent_platform_architectures_experimental")


@aa.entrypoint
async def entrypoint_exp_3(kernel: Kernel, state: VioletState) -> VioletState:
    from agent_platform.architectures.experimental.violet.entrypoint import (
        entrypoint_violet,
    )

    return await entrypoint_violet(kernel, state)


# # ---- Document Cards ----------------------------------------------------------


# async def _initialize_document_cards(
# kernel: Kernel, message: ThreadMessageWithThreadState) -> None:
#     """Detect PDFs without doc-card metadata, seed thread metadata, and stream to UI."""
#     try:
#         # Reuse the documents list the interface already cached
#         documents = await kernel.documents.documents_in_context(None)
#     except Exception:
#         logger.exception("Failed to load documents for doc-card initialization")
#         return

#     if not documents:
#         return

#     pdfs = [doc for doc in documents if doc.mime_type.lower() == "application/pdf"]
#     if not pdfs:
#         return

#     now = datetime.now(UTC).isoformat(timespec="milliseconds")
#     # Use a mapping in metadata for quick lookup by file_ref
#     existing_cards = kernel.thread.metadata.get("doc_cards") or {}
#     # Ensure it's a dict for updates
#     if not isinstance(existing_cards, dict):
#         existing_cards = {}

#     changed = False
#     for doc in pdfs:
#         # Avoid clobbering if we already have a record
#         if doc.file_ref in existing_cards:
#             continue
#         existing_cards[doc.file_ref] = {
#             "id": str(uuid4()),
#             "file_ref": doc.file_ref,
#             "file_id": doc.file_id,
#             "mime_type": doc.mime_type,
#             "size_bytes": doc.file_size_raw,
#             "status": "detected",
#             "sampled_pages": [],
#             "updated_at": now,
#         }
#         changed = True

#     if not changed:
#         # Show cards only once per upload; skip if already shown in a prior message.
#         last_shown = kernel.thread.metadata.get("doc_cards_last_shown_message_id")
#         if existing_cards and not last_shown:
#             message.agent_metadata["doc_cards"] = list(existing_cards.values())
#             kernel.thread.metadata["doc_cards_last_shown_message_id"] = message.message.message_id
#             await message.stream_delta()
#             try:
#                 storage = StorageService.get_instance()
#                 await storage.upsert_thread(kernel.user.user_id, kernel.thread)
#             except Exception:
#                 logger.exception("Failed to persist doc-card metadata to storage")
#         return

#     # Persist to thread metadata
#     kernel.thread.metadata["doc_cards"] = existing_cards
#     kernel.thread.metadata["doc_cards_last_shown_message_id"] = message.message.message_id
#     message.agent_metadata["doc_cards"] = list(existing_cards.values())

#     # Stream immediately so the UI can render cards before the model responds
#     await message.stream_delta()

#     # Persist to storage so subsequent turns reuse the ledger
#     try:
#         storage = StorageService.get_instance()
#         await storage.upsert_thread(kernel.user.user_id, kernel.thread)
#     except Exception:
#         logger.exception("Failed to persist doc-card metadata to storage")


# async def _sample_and_parse_documents(
#     kernel: Kernel,
#     message: ThreadMessageWithThreadState,
# ) -> None:
#     """Sample pages and kick off parse for each PDF; update metadata as results arrive."""
#     last_shown = kernel.thread.metadata.get("doc_cards_last_shown_message_id")
#     allow_stream = not last_shown or last_shown == message.message.message_id

#     doc_cards = kernel.thread.metadata.get("doc_cards")
#     if not isinstance(doc_cards, dict) or not doc_cards:
#         return

#     # Limit overall concurrency to avoid hammering Reducto
#     semaphore = asyncio.Semaphore(4)
#     tasks = []
#     for card in doc_cards.values():
#         if not isinstance(card, dict):
#             continue
#         status = (card.get("status") or "").lower()
#         if status in {"sampling", "parsing"}:
#             # In-flight; don't double-run
#             continue
#         tasks.append(
#             _parse_doc_card(
#                 kernel=kernel,
#                 message=message,
#                 card=card,
#                 semaphore=semaphore,
#                 doc_cards=doc_cards,
#                 allow_stream=allow_stream,
#             )
#         )

#     if tasks:
#         await asyncio.gather(*tasks, return_exceptions=True)


# async def _parse_doc_card(
#     kernel: Kernel,
#     message: ThreadMessageWithThreadState,
#     card: dict,
#     semaphore: asyncio.Semaphore,
#     doc_cards: dict,
#     allow_stream: bool,
# ) -> None:
#     """Parse sampled pages for a single doc card."""

#     from agent_platform.core.integrations.settings.reducto import ReductoSettings
#     from agent_platform.core.platforms.reducto.client import ReductoClient
#     from agent_platform.core.platforms.reducto.parameters import ReductoPlatformParameters
#     from agent_platform.core.platforms.reducto.prompts import ReductoPrompt
#     from agent_platform.core.utils import SecretString
#     from agent_platform.server.data_frames.data_reader import (
#         _get_file_contents,
#         get_file_metadata,
#     )
#     from agent_platform.server.storage.errors import IntegrationNotFoundError

#     file_ref = card.get("file_ref")
#     if not file_ref:
#         return

#     try:
#         file_metadata = await get_file_metadata(
#             user_id=kernel.user.user_id,
#             thread_id=kernel.thread.thread_id,
#             storage=StorageService.get_instance(),
#             file_ref=file_ref,
#         )
#         file_bytes = await _get_file_contents(
#             user_id=kernel.user.user_id,
#             thread_id=kernel.thread.thread_id,
#             storage=StorageService.get_instance(),
#             file_metadata=file_metadata,
#         )
#     except Exception:
#         logger.exception(f"Failed to load file bytes for doc card: {file_ref}")
#         card["status"] = "error"
#         card["error"] = "Failed to load file"
#         await _stream_doc_cards(message, doc_cards)
#         return

#     # Determine page count (best-effort). If unknown, we'll sample a few pages anyway.
#     page_count = card.get("page_count")
#     if not isinstance(page_count, int) or page_count <= 0:
#         page_count = _get_pdf_page_count(file_bytes, file_metadata.file_path)
#     card["page_count"] = page_count if isinstance(page_count, int) and page_count > 0 else None

#     pages = _pick_sample_pages(page_count or 0)
#     card["sampled_pages"] = [{"page": p, "status": "queued"} for p in pages]
#     card["status"] = "sampling"
#     if allow_stream:
#         await _stream_doc_cards(message, doc_cards)

#     # Configure Reducto client
#     try:
#         reducto_integration = await StorageService.get_instance().get_integration_by_kind(
#             "reducto"
#         )
#         if not isinstance(reducto_integration.settings, ReductoSettings):
#             raise ValueError("Invalid Reducto settings")
#         settings = reducto_integration.settings
#         api_key = (
#             settings.api_key.get_secret_value()
#             if isinstance(settings.api_key, SecretString)
#             else str(settings.api_key)
#         )
#         reducto_client = ReductoClient(
#             parameters=ReductoPlatformParameters(
#                 reducto_api_url=settings.endpoint,
#                 reducto_api_key=SecretString(api_key),
#             )
#         )
#         reducto_client.attach_kernel(kernel)
#     except IntegrationNotFoundError:
#         card["status"] = "error"
#         card["error"] = "Reducto not configured"
#         await _stream_doc_cards(message, doc_cards)
#         return
#     except Exception:
#         logger.exception("Failed to configure Reducto client")
#         card["status"] = "error"
#         card["error"] = "Reducto client error"
#         await _stream_doc_cards(message, doc_cards)
#         return

#     async def _parse_page(page_no: int) -> None:
#         async with semaphore:
#             _mark_page_status(card, page_no, "parsing")
#             if allow_stream:
#                 await _stream_doc_cards(message, doc_cards)
#             try:
#                 prompt = ReductoPrompt(
#                     operation="parse",
#                     document_name=file_ref,
#                     document_bytes=file_bytes,
#                     system_prompt=None,
#                     parse_options=_build_parse_params(page_no),
#                 )
#                 response = await reducto_client.generate_response(prompt=prompt, model="default")
#                 parsed = response.model_dump()
#                 _store_page_result(card, page_no, parsed)
#                 if allow_stream:
#                     await _stream_doc_cards(message, doc_cards)
#             except Exception as exc:
#                 logger.exception(
#                     f"Page parse failed: page_no={page_no}, file_ref={file_ref}, error={exc!s}"
#                 )
#                 _mark_page_status(card, page_no, "error", error=str(exc))
#                 if allow_stream:
#                     await _stream_doc_cards(message, doc_cards)

#     await asyncio.gather(*[_parse_page(p) for p in pages], return_exceptions=True)
#     card["status"] = _derive_card_status(card)
#     card["updated_at"] = datetime.now(UTC).isoformat(timespec="milliseconds")
#     await _persist_doc_cards(kernel, doc_cards)
#     if allow_stream:
#         await _stream_doc_cards(message, doc_cards)


# def _build_parse_params(page_no: int) -> "ParseRunParams":
#     """Build parse params with a scoped page range and conservative defaults."""
#     from reducto.types import ParseRunParams
#     from reducto.types.shared_params import (
#         AdvancedProcessingOptions,
#         BaseProcessingOptions,
#         PageRange,
#     )
#     from reducto.types.shared_params.advanced_processing_options import LargeTableChunking
#     from reducto.types.shared_params.base_processing_options import (
#         Chunking,
#         FigureSummary,
#         TableSummary,
#     )

#     return ParseRunParams(
#         document_url="unset",
#         options=BaseProcessingOptions(
#             extraction_mode="ocr",
#             ocr_mode="standard",
#             chunking=Chunking(chunk_mode="disabled"),
#             table_summary=TableSummary(enabled=False),
#             figure_summary=FigureSummary(enabled=False),
#             filter_blocks=[
#                 "Comment",
#                 "Footer",
#                 "Header",
#                 "Page Number",
#             ],
#             force_url_result=False,
#         ),
#         advanced_options=AdvancedProcessingOptions(
#             page_range=PageRange(start=page_no, end=page_no),
#             ocr_system="highres",
#             table_output_format="html",
#             merge_tables=False,
#             continue_hierarchy=True,
#             keep_line_breaks=False,
#             large_table_chunking=LargeTableChunking(
#                 enabled=True,
#                 size=50,
#             ),
#             spreadsheet_table_clustering="default",
#             remove_text_formatting=False,
#             filter_line_numbers=False,
#         ),
#         experimental_options={
#             "enrich": {"enabled": False, "mode": "standard"},
#             "native_office_conversion": False,
#             "enable_checkboxes": False,
#             "rotate_pages": False,
#             "enable_underlines": False,
#             "enable_equations": False,
#             "return_figure_images": False,
#             # Enable layout enrichment to ensure bounding boxes are returned
#             "layout_enrichment": True,
#             "layout_model": "default",
#         },
#     )


# def _store_page_result(card: dict, page: int, parsed: dict) -> None:
#     sampled_pages = card.get("sampled_pages") or []
#     parse_payload = _extract_parse_payload(parsed)
#     for entry in sampled_pages:
#         if entry.get("page") == page:
#             entry["status"] = "ready"
#             entry["parse_data"] = parse_payload
#             # Add lightweight summary
#             entry["summary"] = _summarize_parse(parse_payload or parsed)
#             break
#     card["sampled_pages"] = sampled_pages


# def _summarize_parse(parsed: dict | Any) -> dict:
#     try:
#         chunks = parsed.get("result", {}).get("chunks", []) if isinstance(parsed, dict) else []
#         num_blocks = sum(len(c.get("blocks") or []) for c in chunks)
#         num_tables = sum(
#             1
#             for c in chunks
#             for b in c.get("blocks") or []
#             if isinstance(b, dict) and str(b.get("type", "")).lower() == "table"
#         )
#         return {"blocks": num_blocks, "tables": num_tables}
#     except Exception:
#         return {}


# def _mark_page_status(card: dict, page: int, status: str, error: str | None = None) -> None:
#     sampled_pages = card.get("sampled_pages") or []
#     updated = False
#     for entry in sampled_pages:
#         if entry.get("page") == page:
#             entry["status"] = status
#             if error:
#                 entry["error"] = error
#             updated = True
#             break
#     if not updated:
#         sampled_pages.append({"page": page, "status": status, "error": error})
#     card["sampled_pages"] = sampled_pages


# def _derive_card_status(card: dict) -> str:
#     pages = card.get("sampled_pages") or []
#     if any((p.get("status") or "").lower() == "error" for p in pages):
#         return "error"
#     if any((p.get("status") or "").lower() in {"queued", "parsing"} for p in pages):
#         return "parsing"
#     if pages:
#         return "ready"
#     return card.get("status", "detected")


# def _extract_parse_payload(parsed: dict | Any) -> dict | None:
#     """Prefer the raw_response.result (Reducto payload) for UI overlays."""
#     try:
#         if not isinstance(parsed, dict):
#             return None
#         raw = parsed.get("metadata", {}).get("raw_response")
#         if raw:
#             if isinstance(raw, str):
#                 import json

#                 raw = json.loads(raw)
#             if isinstance(raw, dict):
#                 # Prefer the Reducto result object; if absent, fall back to raw
#                 if "result" in raw and isinstance(raw["result"], dict):
#                     return raw["result"]
#                 return raw
#         # If no raw_response, but parsed already has result, return that
#         if "result" in parsed and isinstance(parsed["result"], dict):
#             return parsed["result"]
#     except Exception:
#         return None
#     return None


# def _pick_sample_pages(page_count: int) -> list[int]:
#     if page_count <= 0:
#         return [1, 2, 3]
#     num_samples = max(3, math.ceil(page_count * 0.10))
#     # Cap to avoid huge payloads
#     num_samples = min(num_samples, 12)
#     if page_count <= num_samples:
#         return list(range(1, page_count + 1))
#     step = page_count / (num_samples - 1)
#     pages = [1]
#     for i in range(1, num_samples - 1):
#         pages.append(min(page_count, max(1, round(1 + i * step))))
#     pages.append(page_count)
#     # Ensure unique and sorted
#     pages = sorted(set(pages))
#     return pages


# def _get_pdf_page_count(file_bytes: bytes, file_path: str | None = None) -> int | None:
#     try:
#         from io import BytesIO

#         from pypdf import PdfReader

#         reader = PdfReader(BytesIO(file_bytes))
#         return len(reader.pages)
#     except Exception as e:
#         logger.warning(f"Failed to detect PDF page count: {e!s}")
#     # Fallback: try file path if available
#     if file_path:
#         try:
#             from pypdf import PdfReader

#             reader = PdfReader(file_path)
#             return len(reader.pages)
#         except Exception as e:  # pragma: no cover - best-effort fallback
#             logger.warning(f"PDF page count via file_path failed: {e!s}")
#     return None


# async def _stream_doc_cards(message: ThreadMessageWithThreadState, doc_cards: dict) -> None:
#     message.agent_metadata["doc_cards"] = list(doc_cards.values())
#     await message.stream_delta()


# async def _persist_doc_cards(kernel: Kernel, doc_cards: dict) -> None:
#     kernel.thread.metadata["doc_cards"] = doc_cards
#     try:
#         await StorageService.get_instance().upsert_thread(kernel.user.user_id, kernel.thread)
#     except Exception:
#         logger.exception("Failed to persist doc-card metadata after sampling")
