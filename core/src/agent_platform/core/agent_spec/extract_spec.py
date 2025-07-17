import base64
import io
import zipfile
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, Literal

import httpx
import structlog
from fastapi import HTTPException, status
from ruamel.yaml import YAML

from agent_platform.core.agent.question_group import QuestionGroup
from agent_platform.core.agent_spec.config import AgentSpecConfig
from agent_platform.core.agent_spec.knowledge import KnowledgeStreams
from agent_platform.core.agent_spec.package_parsed import AgentPackageParsed

_yaml = YAML(typ="safe")

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


async def extract_and_validate_agent_package(
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
    blob = await _read_package_bytes(path, url, package_base64)

    try:
        with zipfile.ZipFile(io.BytesIO(blob)) as zf:
            spec_raw = _read_file_from_zip(zf, AgentSpecConfig.agent_spec_filename)
            spec: dict[str, Any] = _yaml.load(spec_raw.decode())
            _validate_spec(spec, zf)

            runbook_raw = _read_file_from_zip(zf, AgentSpecConfig.runbook_filename)
            question_groups = _extract_question_groups(spec, zf)

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
            )

    except zipfile.BadZipFile as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provided bytes are not a valid zip archive",
        ) from exc


async def _read_package_bytes(
    path: str | Path | None,
    url: str | None,
    package_base64: str | bytes | None,
) -> bytes:
    """Load the zip file bytes, enforcing a single source."""
    expected_source_count = 1
    chosen = [path, url, package_base64].count(None)
    if chosen != (3 - expected_source_count):  # Should have exactly one source
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Specify exactly one of 'path', 'url', or 'package_base64'",
        )

    if path is not None:
        p = Path(path).expanduser()
        if not p.is_file():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"{p} not found",
            )
        return p.read_bytes()

    if url is not None:
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
                resp = await client.get(url)
                if resp.status_code != status.HTTP_200_OK:
                    raise HTTPException(
                        status_code=resp.status_code,
                        detail=f"Failed to download package: HTTP {resp.status_code}",
                    )
                if len(resp.content) > AgentSpecConfig.max_size_bytes:
                    size_in_mb = len(resp.content) / 1_000_000
                    max_size_mb = AgentSpecConfig.max_size_bytes / 1_000_000
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=(f"Package exceeds {max_size_mb:.1f}MB limit ({size_in_mb:.1f}MB)"),
                    )
                return resp.content
        except httpx.RequestError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Network error while downloading package: {exc}",
            ) from exc

    # base-64 branch
    try:
        if package_base64 is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Base-64 encoded package is required",
            )
        return base64.b64decode(package_base64)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid base-64 encoded package",
        ) from exc


def _read_file_from_zip(zf: zipfile.ZipFile, member: str) -> bytes:
    """Read *member* or raise 400."""
    try:
        return zf.read(member)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"'{member}' not found in agent package",
        ) from exc


def _iter_knowledge_members(zf: zipfile.ZipFile) -> Iterable[str]:
    """Yield every file (not directory) under KNOWLEDGE_DIR/ inside the zip."""
    prefix = AgentSpecConfig.knowledge_dir.rstrip("/") + "/"
    return (fn for fn in zf.namelist() if fn.startswith(prefix) and not fn.endswith("/"))


def _validate_spec(
    spec: dict[str, Any],
    zf: zipfile.ZipFile,
) -> None:
    """Raise HTTPException if any rule is violated."""
    try:
        agent_pkg = spec["agent-package"]
        agents = agent_pkg["agents"]
    except (KeyError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Malformed spec: missing 'agent-package/agents'",
        ) from exc

    if agent_pkg.get("spec-version") != "v2" and agent_pkg.get("spec-version") != "v3":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only spec-version='v2' or spec-version='v3' are supported",
        )

    # ---------------- agent check ---------------- #
    # NOTE: spec allows for multiple agents? We can only handle one.
    if len(agents) != 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only one agent is supported",
        )
    agent0 = agents[0]

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


def _extract_question_groups(spec: dict[str, Any], zf: zipfile.ZipFile) -> list[QuestionGroup]:
    # Exceptions are ignored as the conversation guide is optional
    # ---------------- agent check ---------------- #
    # NOTE: spec allows for multiple agents? We can only handle one.
    agents: list = spec.get("agent-package", {}).get("agents", [])
    if len(agents) != 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only one agent is supported",
        )
    agent0 = agents[0]

    # ---------------- conversation guide file check ---------------- #
    conversation_guide_path = agent0.get("conversation-guide")
    if not conversation_guide_path:
        return []

    try:
        conversation_guide_raw = _read_file_from_zip(zf, conversation_guide_path)
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
