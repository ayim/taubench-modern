"""Helper functions for copying eval-related thread files into scenarios."""

from tempfile import SpooledTemporaryFile
from typing import Any, BinaryIO, cast

from fastapi import UploadFile
from starlette.datastructures import Headers
from structlog import get_logger

from agent_platform.core.evals.types import Scenario
from agent_platform.core.payloads import UploadFilePayload
from agent_platform.core.thread.base import ThreadMessage
from agent_platform.core.thread.content.attachment import ThreadAttachmentContent
from agent_platform.core.thread.thread import Thread
from agent_platform.server.api.dependencies import StorageDependency
from agent_platform.server.file_manager import FileManagerService
from agent_platform.server.file_manager.base import BaseFileManager

logger = get_logger(__name__)


async def copy_thread_files_to_scenario(
    *,
    storage: StorageDependency,
    thread: Thread,
    scenario: Scenario,
    user_id: str,
) -> Scenario:
    """Copy thread files to the scenario and rewrite attachment URIs."""
    if not thread.thread_id:
        return scenario

    thread_files = await _load_thread_files(storage, thread, scenario, user_id)
    if thread_files is None:
        return scenario

    if not thread_files:
        logger.info(
            f"No thread files to copy when creating scenario {scenario.scenario_id}",
        )
        return scenario

    file_manager = FileManagerService.get_instance(storage)
    uploads, source_file_ids = await _prepare_thread_file_uploads(
        file_manager=file_manager,
        thread_files=thread_files,
        thread=thread,
        scenario=scenario,
        user_id=user_id,
    )

    if not uploads:
        logger.info(
            "No readable thread files found for scenario creation",
            thread_id=thread.thread_id,
            scenario_id=scenario.scenario_id,
        )
        return scenario

    try:
        return await _upload_thread_files_to_scenario(
            file_manager=file_manager,
            uploads=uploads,
            source_file_ids=source_file_ids,
            scenario=scenario,
            storage=storage,
            user_id=user_id,
        )
    finally:
        await _cleanup_uploads(uploads)


async def _load_thread_files(
    storage: StorageDependency,
    thread: Thread,
    scenario: Scenario,
    user_id: str,
) -> list[Any] | None:
    try:
        thread_files = await storage.get_thread_files(thread.thread_id, user_id)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning(
            "Unable to list thread files for scenario creation",
            thread_id=thread.thread_id,
            scenario_id=scenario.scenario_id,
            error=str(exc),
        )
        return None
    return thread_files or []


async def _prepare_thread_file_uploads(
    *,
    file_manager: BaseFileManager,
    thread_files: list[Any],
    thread: Thread,
    scenario: Scenario,
    user_id: str,
) -> tuple[list[tuple[UploadFile, BinaryIO]], list[str]]:
    uploads: list[tuple[UploadFile, BinaryIO]] = []
    source_file_ids: list[str] = []

    for uploaded_file in thread_files:
        file_bytes = await _read_thread_file(
            file_manager=file_manager,
            uploaded_file=uploaded_file,
            thread=thread,
            scenario=scenario,
            user_id=user_id,
        )
        if file_bytes is None:
            continue

        temp_file = SpooledTemporaryFile()
        temp_file.write(file_bytes)
        temp_file.seek(0)

        file_obj = cast(BinaryIO, temp_file)
        upload = UploadFile(
            filename=uploaded_file.file_ref,
            file=file_obj,
            headers=Headers(
                {
                    "content-type": uploaded_file.mime_type or "application/octet-stream",
                }
            ),
        )
        uploads.append((upload, file_obj))
        source_file_ids.append(uploaded_file.file_id)

    return uploads, source_file_ids


async def _read_thread_file(
    *,
    file_manager: BaseFileManager,
    uploaded_file: Any,
    thread: Thread,
    scenario: Scenario,
    user_id: str,
) -> bytes | None:
    try:
        return await file_manager.read_file_contents(
            uploaded_file.file_id,
            user_id,
        )
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning(
            "Failed to read thread file during scenario creation",
            thread_id=thread.thread_id,
            scenario_id=scenario.scenario_id,
            file_id=uploaded_file.file_id,
            error=str(exc),
        )
        return None


async def _upload_thread_files_to_scenario(  # noqa: PLR0913
    *,
    file_manager: BaseFileManager,
    uploads: list[tuple[UploadFile, BinaryIO]],
    source_file_ids: list[str],
    scenario: Scenario,
    storage: StorageDependency,
    user_id: str,
) -> Scenario:
    payloads = [UploadFilePayload(file=upload) for upload, _ in uploads]
    uploaded_scenario_files = await file_manager.upload(payloads, scenario, user_id)
    logger.info(
        f"Copied {len(uploads)} thread file(s) to scenario {scenario.scenario_id}",
    )

    id_map = {
        source_id: dest.file_id
        for source_id, dest in zip(source_file_ids, uploaded_scenario_files, strict=False)
    }
    if not id_map:
        return scenario

    if not _update_attachment_uris(scenario.messages, id_map):
        return scenario

    return await storage.update_scenario_messages(
        scenario.scenario_id,
        scenario.messages,
    )


def _update_attachment_uris(
    messages: list[ThreadMessage],
    id_map: dict[str, str],
) -> bool:
    prefix = "agent-server-file://"
    updated = False

    for message in messages:
        for content in message.content:
            if (
                isinstance(content, ThreadAttachmentContent)
                and content.uri
                and content.uri.startswith(prefix)
            ):
                original_id = content.uri[len(prefix) :]
                new_id = id_map.get(original_id)
                if new_id and new_id != original_id:
                    content.uri = f"{prefix}{new_id}"
                    updated = True

    return updated


async def _cleanup_uploads(uploads: list[tuple[UploadFile, BinaryIO]]) -> None:
    for upload, temp_file in uploads:
        try:
            await upload.close()
        except Exception:
            logger.debug(
                "Error closing upload during thread-to-scenario copy",
                exc_info=True,
            )
        try:
            # Closing a SpooledTemporaryFile also removes any disk-backed temp file.
            temp_file.close()
        except Exception:
            logger.debug(
                "Error closing temporary file during thread-to-scenario copy",
                exc_info=True,
            )
