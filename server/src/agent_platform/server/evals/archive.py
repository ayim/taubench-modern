import io
import re
import zipfile
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml
from fastapi import UploadFile
from structlog import get_logger

from agent_platform.core.evals.replay_executor import ReplayToolExecutor
from agent_platform.core.evals.types import Scenario
from agent_platform.core.files import UploadedFile
from agent_platform.core.payloads.upload_file import UploadFilePayload
from agent_platform.core.thread.base import ThreadMessage
from agent_platform.core.thread.content.attachment import ThreadAttachmentContent
from agent_platform.core.thread.content.tool_usage import ThreadToolUsageContent
from agent_platform.server.api.dependencies import StorageDependency
from agent_platform.server.file_manager.base import BaseFileManager
from agent_platform.server.file_manager.option import FileManagerService

logger = get_logger(__name__)


@dataclass(frozen=True)
class ScenarioAttachmentEntry:
    archive_path: str
    file_ref: str
    mime_type: str | None = None
    size: int | None = None


@dataclass(frozen=True)
class ScenarioArchiveEntry:
    path: str
    tools_path: str | None = None
    attachments: tuple[ScenarioAttachmentEntry, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ScenarioAttachmentImport:
    file_ref: str
    content: bytes
    mime_type: str | None = None


@dataclass(frozen=True)
class ScenarioImportBundle:
    scenario: Scenario
    attachments: tuple[ScenarioAttachmentImport, ...] = field(default_factory=tuple)


class ScenarioImportError(Exception):
    """Raised when a scenario archive cannot be imported."""


def _load_archive_metadata(archive: zipfile.ZipFile) -> dict[str, Any]:
    try:
        metadata_bytes = archive.read("metadata.yaml")
    except KeyError as exc:
        raise ScenarioImportError("Missing metadata.yaml in archive") from exc

    try:
        metadata = yaml.safe_load(metadata_bytes) or {}
    except yaml.YAMLError as exc:
        raise ScenarioImportError("Unable to parse metadata.yaml") from exc

    if not isinstance(metadata, dict):
        raise ScenarioImportError("metadata.yaml must define a mapping")

    return metadata


def _list_scenario_entries(metadata: dict[str, Any]) -> list[ScenarioArchiveEntry]:
    entries: list[ScenarioArchiveEntry] = []
    files_entry = metadata.get("files")

    if isinstance(files_entry, list):
        seen_paths: set[str] = set()
        for entry in files_entry:
            if not isinstance(entry, dict):
                continue
            path = entry.get("path")
            if not isinstance(path, str) or path in seen_paths:
                continue
            tools_path = entry.get("tools_path")
            if not isinstance(tools_path, str):
                tools_path = None
            attachments = _parse_attachment_entries(entry.get("attachments"), path)
            entries.append(
                ScenarioArchiveEntry(path=path, tools_path=tools_path, attachments=attachments)
            )
            seen_paths.add(path)

    if not entries:
        raise ScenarioImportError("No scenario definitions found in archive")

    return entries


def _load_scenario_payload(archive: zipfile.ZipFile, path: str) -> dict[str, Any]:
    try:
        payload_bytes = archive.read(path)
    except KeyError as exc:
        raise ScenarioImportError(f"Scenario file '{path}' is missing from archive") from exc

    try:
        payload = yaml.safe_load(payload_bytes) or {}
    except yaml.YAMLError as exc:
        raise ScenarioImportError(f"Unable to parse scenario file '{path}'") from exc

    if not isinstance(payload, dict):
        raise ScenarioImportError(f"Scenario file '{path}' must define a mapping")

    return payload


def _parse_attachment_entries(  # noqa: C901
    raw_attachments: Any, scenario_path: str
) -> tuple[ScenarioAttachmentEntry, ...]:
    if raw_attachments is None:
        return ()

    if not isinstance(raw_attachments, list):
        raise ScenarioImportError(
            f"Scenario '{scenario_path}' attachments entry must be a list when provided"
        )

    attachments: list[ScenarioAttachmentEntry] = []
    seen_paths: set[str] = set()

    for index, raw_attachment in enumerate(raw_attachments):
        if not isinstance(raw_attachment, dict):
            raise ScenarioImportError(
                f"Scenario '{scenario_path}' attachment at index {index} must be a mapping"
            )

        archive_path = raw_attachment.get("path")
        if not isinstance(archive_path, str) or not archive_path.strip():
            raise ScenarioImportError(
                f"Scenario '{scenario_path}' attachment at index {index} is missing a valid path"
            )
        if archive_path in seen_paths:
            raise ScenarioImportError(
                f"Scenario '{scenario_path}' attachment at index {index} references duplicate path"
            )
        seen_paths.add(archive_path)

        file_ref = raw_attachment.get("file_ref")
        if not isinstance(file_ref, str) or not file_ref.strip():
            raise ScenarioImportError(
                f"Scenario '{scenario_path}' attachment at index {index} "
                f"is missing a valid file ref"
            )

        mime_type = raw_attachment.get("mime_type")
        if mime_type is not None and not isinstance(mime_type, str):
            raise ScenarioImportError(
                f"Scenario '{scenario_path}' attachment at index {index} has an invalid mime type"
            )

        size = raw_attachment.get("size")
        if size is not None:
            if not isinstance(size, int) or size < 0:
                raise ScenarioImportError(
                    f"Scenario '{scenario_path}' attachment at index {index} has an invalid size"
                )

        attachments.append(
            ScenarioAttachmentEntry(
                archive_path=archive_path,
                file_ref=file_ref,
                mime_type=mime_type,
                size=size,
            )
        )

    return tuple(attachments)


def _load_used_tools(
    archive: zipfile.ZipFile, tools_path: str, scenario_path: str
) -> list[dict[str, Any]]:
    try:
        payload_bytes = archive.read(tools_path)
    except KeyError as exc:
        error_message = (
            f"Used tools file '{tools_path}' referenced by {scenario_path}' is missing from archive"
        )
        raise ScenarioImportError(error_message) from exc

    try:
        payload = yaml.safe_load(payload_bytes) or []
    except yaml.YAMLError as exc:
        raise ScenarioImportError(
            f"Unable to parse used tools file '{tools_path}' referenced by '{scenario_path}'"
        ) from exc

    if not isinstance(payload, list):
        raise ScenarioImportError(f"Used tools file '{tools_path}' must define a list of tools")

    tools: list[dict[str, Any]] = []
    for index, entry in enumerate(payload):
        if not isinstance(entry, dict):
            raise ScenarioImportError(
                f"Used tools file '{tools_path}' entry at index {index} must be a mapping"
            )
        tool_name = entry.get("name")
        if not isinstance(tool_name, str) or not tool_name.strip():
            raise ScenarioImportError(
                f"Used tools file '{tools_path}' entry at index {index} is missing a valid name"
            )
        tools.append(entry)

    return tools


def _extract_tool_categories(messages: list[ThreadMessage]) -> dict[str, str]:
    categories: dict[str, str] = {}

    for message in messages:
        for content in message.content:
            if isinstance(content, ThreadToolUsageContent):
                if content.sub_type == "mcp-external":
                    categories.setdefault(content.name, "mcp-tool")
                elif content.sub_type == "action-external":
                    categories.setdefault(content.name, "action-tool")

    return categories


def _apply_used_tools_to_messages(
    messages: list[ThreadMessage], used_tools: list[dict[str, Any]] | None
) -> None:
    if not used_tools:
        return

    categories = _extract_tool_categories(messages)
    normalized_tools: list[dict[str, Any]] = []

    for entry in used_tools:
        tool_copy = deepcopy(entry)
        tool_name = tool_copy.get("name")
        if isinstance(tool_name, str):
            category = tool_copy.get("category")
            if not isinstance(category, str) or not category:
                inferred_category = categories.get(tool_name)
                tool_copy["category"] = inferred_category or "action-tool"
        normalized_tools.append(tool_copy)

    for message in messages:
        if message.role != "agent":
            continue
        message.agent_metadata["tools"] = [deepcopy(tool) for tool in normalized_tools]


def _build_metadata_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    metadata: dict[str, Any] = {}

    evaluations = payload.get("evaluations")
    if isinstance(evaluations, list):
        evaluations_config: dict[str, Any] = {}
        for entry in evaluations:
            if not isinstance(entry, dict):
                continue
            kind = entry.get("kind")
            if not isinstance(kind, str):
                continue
            config = {k: v for k, v in entry.items() if k != "kind"}
            if not config:
                config = {"enabled": True}
            evaluations_config[kind] = config

        if evaluations_config:
            metadata["evaluations"] = evaluations_config

    tool_execution_mode = payload.get("tool_execution_mode")
    if isinstance(tool_execution_mode, str) and tool_execution_mode:
        metadata.setdefault("drift_policy", {})["tool_execution_mode"] = tool_execution_mode

    return metadata


def _scenario_from_payload(
    *,
    payload: dict[str, Any],
    path: str,
    user_id: str,
    agent_id: str,
    used_tools: list[dict[str, Any]] | None = None,
) -> Scenario:
    name = payload.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ScenarioImportError(f"Scenario '{path}' is missing a valid name")

    description = payload.get("description", "")
    if not isinstance(description, str):
        raise ScenarioImportError(f"Scenario '{path}' has an invalid description")

    thread_payload = payload.get("thread")
    if not isinstance(thread_payload, dict):
        raise ScenarioImportError(f"Scenario '{path}' is missing thread data")

    raw_messages = thread_payload.get("messages")
    if not isinstance(raw_messages, list):
        raise ScenarioImportError(f"Scenario '{path}' thread messages must be a list")

    messages: list[ThreadMessage] = []
    for index, raw_message in enumerate(raw_messages):
        if not isinstance(raw_message, dict):
            raise ScenarioImportError(
                f"Scenario '{path}' message at index {index} must be a mapping"
            )
        try:
            message = ThreadMessage.model_validate(raw_message)
        except Exception as exc:
            raise ScenarioImportError(
                f"Scenario '{path}' message at index {index} is invalid: {exc}"
            ) from exc
        message.mark_complete()
        messages.append(message)

    _apply_used_tools_to_messages(messages, used_tools)

    metadata = _build_metadata_from_payload(payload)

    return Scenario(
        scenario_id=str(uuid4()),
        name=name,
        description=description,
        thread_id=None,
        agent_id=agent_id,
        user_id=user_id,
        messages=messages,
        metadata=metadata,
    )


def _load_archive_attachments(
    archive: zipfile.ZipFile, entry: ScenarioArchiveEntry
) -> tuple[ScenarioAttachmentImport, ...]:
    attachments: list[ScenarioAttachmentImport] = []

    for attachment in entry.attachments:
        try:
            file_bytes = archive.read(attachment.archive_path)
        except KeyError as exc:
            raise ScenarioImportError(
                f"Attachment '{attachment.archive_path}' referenced by '{entry.path}' "
                "is missing from archive"
            ) from exc

        if attachment.size is not None and len(file_bytes) != attachment.size:
            raise ScenarioImportError(
                f"Attachment '{attachment.archive_path}' referenced by '{entry.path}' "
                "has unexpected size"
            )

        attachments.append(
            ScenarioAttachmentImport(
                file_ref=attachment.file_ref,
                content=file_bytes,
                mime_type=attachment.mime_type,
            )
        )

    return tuple(attachments)


def _derive_attachment_filename(file_ref: str) -> str:
    filename = Path(file_ref).name
    if filename:
        return filename
    return _safe_filename_fragment(file_ref, default="file")


def _rewrite_imported_attachment_handles(  # noqa: PLR0912, C901
    messages: list[ThreadMessage],
    uploads_by_ref: dict[str, UploadedFile],
) -> bool:
    """Update attachment URIs (and related metadata) to point to newly uploaded files."""
    if not uploads_by_ref:
        return False

    updated = False
    prefix = "agent-server-file://"

    for message in messages:
        message_updated = False
        for content in message.content:
            if not isinstance(content, ThreadAttachmentContent):
                continue
            upload = uploads_by_ref.get(content.name)
            if upload is None:
                continue
            new_uri = f"{prefix}{upload.file_id}"
            if content.uri != new_uri:
                content.uri = new_uri
                message_updated = True

        if message_updated:
            updated = True
            metadata_entries = (
                message.server_metadata.get("files"),
                message.server_metadata.get("attachments"),
            )
            for entries in metadata_entries:
                if not isinstance(entries, list):
                    continue
                for entry in entries:
                    if not isinstance(entry, dict):
                        continue
                    file_ref = entry.get("file_ref")
                    if not isinstance(file_ref, str):
                        continue
                    upload = uploads_by_ref.get(file_ref)
                    if upload is None:
                        continue
                    if entry.get("file_id") != upload.file_id:
                        entry["file_id"] = upload.file_id

    return updated


@dataclass(frozen=True)
class ScenarioFileExport:
    file_id: str
    file_ref: str
    archive_path: str
    mime_type: str | None
    size: int
    content: bytes


async def _collect_scenario_files(
    *,
    scenario: Scenario,
    storage: StorageDependency,
    file_manager: BaseFileManager,
    requester_user_id: str,
    index: int,
) -> list[ScenarioFileExport]:
    try:
        uploaded_files = await storage.get_scenario_files(
            scenario.scenario_id,
            requester_user_id,
        )
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning(
            "Skipping file export for scenario due to scenario files lookup failure"
            f"scenario_id={scenario.scenario_id}"
            f"error={exc!s}",
        )
        return []

    if not uploaded_files:
        return []

    used_names: set[str] = set()
    directory = _scenario_files_dirname(scenario, index)
    exports: list[ScenarioFileExport] = []

    for uploaded in uploaded_files:
        try:
            file_bytes = await file_manager.read_file_contents(uploaded.file_id, requester_user_id)
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning(
                "Unable to read scenario file for export"
                f"scenario_id={scenario.scenario_id}"
                f"file_id={uploaded.file_id}"
                f"error={exc!s}"
            )
            continue

        archive_name = _sanitize_export_file_name(uploaded.file_ref, used_names)
        archive_path = f"{directory}/{archive_name}"
        exports.append(
            ScenarioFileExport(
                file_id=uploaded.file_id,
                file_ref=uploaded.file_ref,
                archive_path=archive_path,
                mime_type=uploaded.mime_type,
                size=len(file_bytes),
                content=file_bytes,
            )
        )

    return exports


def _safe_filename_fragment(value: str, default: str = "agent") -> str:
    """Return a filesystem-safe fragment derived from the provided value."""

    fragment = re.sub(r"[^A-Za-z0-9_.-]", "_", value)
    return fragment or default


def _scenario_entry_filename(scenario: Scenario, index: int) -> str:
    name_fragment = _safe_filename_fragment(scenario.name, default="scenario")
    identifier = scenario.scenario_id[:8]
    return f"evals/{index + 1:03d}_{name_fragment}_{identifier}.yaml"


def _tools_entry_filename(scenario: Scenario, index: int) -> str:
    name_fragment = _safe_filename_fragment(scenario.name, default="scenario")
    identifier = scenario.scenario_id[:8]
    return f"used_tools/{index + 1:03d}_{name_fragment}_{identifier}.yaml"


def _scenarios_export_filename(agent_id: str) -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"agent_{_safe_filename_fragment(agent_id)}_scenarios_{timestamp}.zip"


def _scenario_files_dirname(scenario: Scenario, index: int) -> str:
    name_fragment = _safe_filename_fragment(scenario.name, default="scenario")
    identifier = scenario.scenario_id[:8]
    return f"thread_files/{index + 1:03d}_{name_fragment}_{identifier}"


def _sanitize_export_file_name(file_ref: str, used_names: set[str]) -> str:
    original_name = Path(file_ref).name or "file"
    sanitized = _safe_filename_fragment(original_name, default="file")

    base = Path(sanitized).stem or "file"
    suffix = Path(sanitized).suffix

    candidate = sanitized if sanitized not in {"", "."} else "file"
    counter = 1
    while candidate in used_names:
        candidate = f"{base}_{counter}{suffix}"
        counter += 1

    used_names.add(candidate)
    return candidate


def _extract_evaluations_from_metadata(metadata: Any) -> list[dict[str, Any]]:
    if not isinstance(metadata, dict):
        return []

    raw_evaluations = metadata.get("evaluations")
    if not isinstance(raw_evaluations, dict):
        return []

    evaluations: list[dict[str, Any]] = []

    for key, value in raw_evaluations.items():
        entry: dict[str, Any] = {"kind": key}

        if isinstance(value, dict):
            for prop, prop_value in value.items():
                entry[prop] = prop_value

        evaluations.append(entry)

    return evaluations


async def build_scenarios_archive(
    scenarios: list[Scenario], storage: StorageDependency, requester_user_id: str, agent_id: str
) -> tuple[bytes, str]:
    """Pack all scenarios into an in-memory zip archive ready for download."""

    buffer = io.BytesIO()
    metadata = {
        "exported_at": datetime.now(UTC).isoformat(),
        "files": [],
    }

    def _remove_metadata(data: dict) -> dict:
        return {k: v for k, v in data.items() if k not in {"complete", "content_id", "category"}}

    file_manager = FileManagerService.get_instance(storage)

    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for index, scenario in enumerate(scenarios):
            scenario_path = _scenario_entry_filename(scenario, index)
            tools_path = _tools_entry_filename(scenario, index)
            metadata_dict = scenario.metadata if isinstance(scenario.metadata, dict) else {}
            drift_policy = (
                metadata_dict.get("drift_policy", {}) if isinstance(metadata_dict, dict) else {}
            )
            tool_execution_mode = (
                drift_policy.get("tool_execution_mode") if isinstance(drift_policy, dict) else None
            )

            scenario_payload = {
                "name": scenario.name,
                "description": scenario.description,
                "tool_execution_mode": tool_execution_mode or "replay",
                "evaluations": _extract_evaluations_from_metadata(metadata_dict),
                "thread": {
                    "messages": [
                        {
                            "role": message.role,
                            "content": [
                                _remove_metadata(content.model_dump())
                                for content in message.content
                            ],
                        }
                        for message in scenario.messages
                    ],
                },
            }

            conversation_analysis = ReplayToolExecutor.from_conversation(scenario.messages)
            tool_defs = [
                _remove_metadata(tool.model_dump()) for tool in conversation_analysis.tools
            ]

            archive.writestr(tools_path, yaml.safe_dump(tool_defs, sort_keys=False))
            archive.writestr(scenario_path, yaml.safe_dump(scenario_payload, sort_keys=False))

            scenario_files = await _collect_scenario_files(
                scenario=scenario,
                storage=storage,
                file_manager=file_manager,
                requester_user_id=requester_user_id,
                index=index,
            )

            attachments_metadata: list[dict[str, Any]] = []
            for export in scenario_files:
                archive.writestr(export.archive_path, export.content)
                attachments_metadata.append(
                    {
                        "file_ref": export.file_ref,
                        "path": export.archive_path,
                        "mime_type": export.mime_type,
                        "size": export.size,
                    }
                )

            metadata["files"].append(
                {
                    "scenario_name": scenario.name,
                    "path": scenario_path,
                    "tools_path": tools_path,
                    "attachments": attachments_metadata,
                }
            )

        archive.writestr("metadata.yaml", yaml.dump(metadata))

    return buffer.getvalue(), _scenarios_export_filename(agent_id)


async def load_scenarios_bundles(
    user_id: str, agent_id: str, content: bytes
) -> list[ScenarioImportBundle]:
    scenarios_to_create: list[ScenarioImportBundle] = []

    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        metadata = _load_archive_metadata(archive)

        for entry in _list_scenario_entries(metadata):
            payload = _load_scenario_payload(archive, entry.path)
            used_tools = (
                _load_used_tools(archive, entry.tools_path, entry.path)
                if entry.tools_path is not None
                else None
            )
            scenario_model = _scenario_from_payload(
                payload=payload,
                path=entry.path,
                user_id=user_id,
                agent_id=agent_id,
                used_tools=used_tools,
            )
            attachments = _load_archive_attachments(archive, entry)
            scenarios_to_create.append(
                ScenarioImportBundle(
                    scenario=scenario_model,
                    attachments=attachments,
                )
            )

    return scenarios_to_create


async def create_scenarios_from_bundles(
    user_id: str,
    bundles: list[ScenarioImportBundle],
    storage: StorageDependency,
):
    created: list[Scenario] = []
    file_manager = FileManagerService.get_instance(storage)

    for bundle in bundles:
        created_scenario = await storage.create_scenario(bundle.scenario)

        try:
            uploads_by_ref: dict[str, UploadedFile] = {}
            if bundle.attachments:
                logger.info("Import package has scenario files")
                if file_manager is None:
                    file_manager = FileManagerService.get_instance(storage)
                upload_payloads = [
                    UploadFilePayload(
                        file=UploadFile(
                            filename=_derive_attachment_filename(attachment.file_ref),
                            file=io.BytesIO(attachment.content),
                        )
                    )
                    for attachment in bundle.attachments
                ]
                try:
                    logger.info(
                        f"Uploading {len(upload_payloads)} files "
                        f"for scenario {created_scenario.scenario_id}"
                    )
                    uploaded_files = await file_manager.upload(
                        upload_payloads,
                        created_scenario,
                        user_id,
                    )
                    uploads_by_ref = {
                        attachment.file_ref: uploaded
                        for attachment, uploaded in zip(
                            bundle.attachments, uploaded_files, strict=False
                        )
                        if uploaded is not None
                    }
                finally:
                    for payload in upload_payloads:
                        try:
                            await payload.file.close()
                        except Exception as close_exc:  # pragma: no cover - defensive cleanup
                            logger.warning(
                                "Failed to close attachment file during scenario import"
                                f"file_name={payload.file.filename}"
                                f"error={close_exc!s}"
                            )
            if _rewrite_imported_attachment_handles(created_scenario.messages, uploads_by_ref):
                created_scenario = await storage.update_scenario_messages(
                    created_scenario.scenario_id,
                    created_scenario.messages,
                )
        except Exception:
            logger.error(f"Cannot upload files for scenario {created_scenario.scenario_id}")
            try:
                await storage.delete_scenario_files(created_scenario.scenario_id, user_id)
            except Exception as cleanup_exc:  # pragma: no cover - defensive cleanup
                logger.warning(
                    "Failed to clean up scenario files after import failure"
                    f"scenario_id={created_scenario.scenario_id}"
                    f"error={cleanup_exc!s}"
                )
            await storage.delete_scenario(created_scenario.scenario_id)
            raise

        created.append(created_scenario)

    return created
