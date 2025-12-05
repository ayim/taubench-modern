import io
import zipfile
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, Literal

import structlog
from fastapi import HTTPException, status
from ruamel.yaml import YAML

from agent_platform.core.agent.question_group import QuestionGroup
from agent_platform.core.agent_package.config import AgentSpecConfig
from agent_platform.core.agent_package.knowledge import KnowledgeStreams
from agent_platform.core.agent_package.package_parsed import ActionPackageParsed, AgentPackageParsed
from agent_platform.core.agent_package.utils import read_file_from_zip, read_package_bytes

_yaml = YAML(typ="safe")

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


async def read_and_validate_agent_package(
    path: str | Path | None = None,
    url: str | None = None,
    package_base64: str | bytes | None = None,
    include_knowledge: bool = False,
    knowledge_return: Literal["bytes", "stream"] = "bytes",
) -> AgentPackageParsed:
    """
    Extract and validate an agent package.

    * Pass **exactly one** of *path*, *url*, *package_base64*.
    * If *include_knowledge* is **False** (default) the 3rd tuple member is ``None``.
      When **True**, you get a mapping ``{filename: <bytes|ZipExtFile>}`` where
      the value type depends on *knowledge_return*:
      * ``"bytes"``  - each file is fully read into RAM (convenient).
      * ``"stream"`` - a seek-able, file-like object straight from ``ZipFile``;
        you decide when/if to read.

    FastAPI detail: any failure raises ``HTTPException`` with descriptive text.

    Arguments:
        path: local path to the agent package
        url: URL to the agent package
        package_base64: base64-encoded agent package
        include_knowledge: whether to include knowledge files in the return value
        knowledge_return: how to return the knowledge files

    Returns:
        An ``AgentPackageParsed`` instance.
    """
    blob = await read_package_bytes(path, url, package_base64)

    try:
        with zipfile.ZipFile(io.BytesIO(blob)) as zf:
            spec_raw = read_file_from_zip(zf, AgentSpecConfig.agent_spec_filename)
            return await read_agent_package(spec_raw, zf, include_knowledge, knowledge_return)

    except zipfile.BadZipFile as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provided bytes are not a valid zip archive",
        ) from exc


async def read_agent_package(
    spec_raw: bytes,
    zf: zipfile.ZipFile,
    include_knowledge: bool = False,
    knowledge_return: Literal["bytes", "stream"] = "bytes",
) -> AgentPackageParsed:
    spec: dict[str, Any] = _yaml.load(spec_raw.decode())
    _validate_spec(spec, zf)

    runbook_raw = read_file_from_zip(zf, AgentSpecConfig.runbook_filename)
    question_groups = _read_question_groups(spec, zf)
    conversation_starter = _read_conversation_starter(spec)
    welcome_message = _read_welcome_message(spec)
    agent_settings = _read_agent_settings(spec)
    action_packages = _read_action_packages(spec)
    semantic_data_models = _read_semantic_data_models(spec, zf)

    knowledge: Mapping[str, bytes] | KnowledgeStreams | None
    if include_knowledge:
        if knowledge_return == "bytes":
            knowledge = {Path(fn).name: zf.read(fn) for fn in _iter_knowledge_members(zf)}
        else:  # "stream"
            streams = {Path(fn).name: zf.open(fn) for fn in _iter_knowledge_members(zf)}
            knowledge = KnowledgeStreams(streams)
    else:
        knowledge = None

    return AgentPackageParsed(
        spec=spec,
        runbook_text=runbook_raw.decode("utf-8", errors="replace"),
        knowledge=knowledge,
        question_groups=question_groups,
        conversation_starter=conversation_starter,
        welcome_message=welcome_message,
        agent_settings=agent_settings,
        action_packages=action_packages,
        semantic_data_models=semantic_data_models,
    )


def _iter_knowledge_members(zf: zipfile.ZipFile) -> Iterable[str]:
    """Yield every file (not directory) under KNOWLEDGE_DIR/ inside the zip."""
    prefix = AgentSpecConfig.knowledge_dir.rstrip("/") + "/"
    return (fn for fn in zf.namelist() if fn.startswith(prefix) and not fn.endswith("/"))


def _get_single_agent(spec: dict[str, Any]) -> dict[str, Any]:
    """Get the single agent from the spec.
    Spec allows for multiple agents, but we can only handle one.
    """
    # ---------------- agent check ---------------- #
    agents: list = spec.get("agent-package", {}).get("agents", [])
    if len(agents) != 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only one agent is supported",
        )
    return agents[0]


def _validate_spec(
    spec: dict[str, Any],
    zf: zipfile.ZipFile,
) -> None:
    """Raise HTTPException if any rule is violated."""
    try:
        agent_pkg = spec["agent-package"]
    except (KeyError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Malformed spec: missing 'agent-package/agents'",
        ) from exc

    if agent_pkg.get("spec-version", "") not in ["v2", "v2.1", "v3"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only spec-version='v2', 'v2.1', or 'v3' are supported",
        )

    # ---------------- agent check ---------------- #
    agent0 = _get_single_agent(spec)

    # ---------------- conversation guide file check ---------------- #
    conversation_guide_path = agent0.get("conversation-guide")
    if conversation_guide_path:
        if conversation_guide_path not in zf.namelist():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"'conversation-guide' specified as '{conversation_guide_path}'"
                "in agent spec, but file not found in package.",
            )

    # ---------------- knowledge file checks ---------------- #
    # Verify that knowledge files declared in the spec match exactly
    # with those found in the archive (no missing or unexpected files)
    spec_files_set = {
        Path(item["name"]).name
        for item in agent0.get("knowledge", [])
        if isinstance(item, dict) and "name" in item
    }

    archive_files_set = {Path(fn).name for fn in _iter_knowledge_members(zf)}

    if spec_files_set != archive_files_set:
        missing = spec_files_set - archive_files_set
        extra = archive_files_set - spec_files_set
        details = []
        if missing:
            details.append(f"missing: {', '.join(sorted(missing))}")
        if extra:
            details.append(f"unexpected: {', '.join(sorted(extra))}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Knowledge files mismatch - " + "; ".join(details),
        )


def _read_question_groups(spec: dict[str, Any], zf: zipfile.ZipFile) -> list[QuestionGroup]:
    # Exceptions are ignored as the conversation guide is optional
    # ---------------- agent check ---------------- #
    agent0 = _get_single_agent(spec)

    # ---------------- conversation guide file check ---------------- #
    conversation_guide_path = agent0.get("conversation-guide")
    if not conversation_guide_path:
        return []

    try:
        conversation_guide_raw = read_file_from_zip(zf, conversation_guide_path)
    except Exception as e:
        logger.error(
            "Conversation guide file '%s' not found or could not be read",
            AgentSpecConfig.conversation_guide_filename,
            exc_info=True,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Conversation guide file not found or could not be read",
        ) from e

    # ---------------- question groups check ---------------- #
    question_groups: list[QuestionGroup] = []
    if conversation_guide_raw:
        try:
            guide_yaml = _yaml.load(conversation_guide_raw.decode())
            qg_list = guide_yaml.get("question-groups", []) if isinstance(guide_yaml, dict) else []

            question_groups = [
                QuestionGroup.model_validate(qg) for qg in qg_list if isinstance(qg, dict)
            ]
        except Exception as e:
            logger.error(
                "Failed to parse or validate conversation guide",
                exc_info=True,
                error=str(e),
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to parse or validate conversation guide",
            ) from e
    return question_groups


def _read_conversation_starter(spec: dict[str, Any]) -> str | None:
    agent0 = _get_single_agent(spec)
    return agent0.get("conversation-starter", None)


def _read_welcome_message(spec: dict[str, Any]) -> str | None:
    agent0 = _get_single_agent(spec)
    return agent0.get("welcome-message", None)


def _read_agent_settings(spec: dict[str, Any]) -> dict[str, Any] | None:
    agent0 = _get_single_agent(spec)
    return agent0.get("agent-settings", None)


def _read_action_packages(spec: dict[str, Any]) -> list[ActionPackageParsed]:
    agent0 = _get_single_agent(spec)
    action_packages = agent0.get("action-packages", [])
    return [ActionPackageParsed.model_validate(ap) for ap in action_packages]


def _read_semantic_data_models(
    spec: dict[str, Any], zf: zipfile.ZipFile
) -> dict[str, dict[str, Any]] | None:
    """
    Extract semantic data models from the semantic-data-models/ folder.

    Returns:
        Dictionary mapping filename to SDM content (parsed YAML), or None if no SDMs
    """
    logger.info("[_extract_semantic_data_models] Starting SDM extraction")
    agent0 = _get_single_agent(spec)
    sdm_refs = agent0.get("semantic-data-models", [])

    logger.info(
        f"[_extract_semantic_data_models] Found {len(sdm_refs)} SDM references in spec: {sdm_refs}"
    )

    if not sdm_refs:
        logger.info("[_extract_semantic_data_models] No SDM references found, returning None")
        return None

    sdms: dict[str, dict[str, Any]] = {}

    for sdm_ref in sdm_refs:
        sdm_filename = sdm_ref.get("name")
        if not sdm_filename:
            logger.warning("SDM reference missing 'name' field, skipping")
            continue

        # SDMs are stored in semantic-data-models/ folder
        sdm_path = f"semantic-data-models/{sdm_filename}"

        try:
            sdm_bytes = read_file_from_zip(zf, sdm_path)
            # Parse YAML (Snowflake Cortex Analyst semantic model format)
            sdm_content = _yaml.load(sdm_bytes.decode("utf-8"))

            if not isinstance(sdm_content, dict):
                logger.warning(
                    "SDM file '%s' does not contain valid YAML dict, skipping",
                    sdm_path,
                )
                continue

            sdms[sdm_filename] = sdm_content
            logger.info(
                f"[_extract_semantic_data_models] Successfully extracted SDM: {sdm_filename}"
            )

        except KeyError:
            logger.warning(
                f"[_extract_semantic_data_models] SDM file not found in package: {sdm_path}"
            )
        except Exception as e:
            logger.error(
                f"[_extract_semantic_data_models] Failed to parse SDM file {sdm_path}: {e}",
                exc_info=True,
                error=str(e),
            )
            # Continue with other SDMs even if one fails
            continue

    result = sdms if sdms else None
    sdm_count = len(sdms) if sdms else 0
    sdm_keys = list(sdms.keys()) if sdms else []
    logger.info(
        f"[_extract_semantic_data_models] Extraction complete. "
        f"Returning {sdm_count} SDMs: {sdm_keys}"
    )
    return result
