"""
Special command handling for the agent platform.

This module parses small "slash" commands (e.g., /debug, /help, /set …),
dispatches them, and renders human-readable debug/diagnostic output into
the current thread via the Kernel APIs.

The implementation aims to be:
- Explicit and readable
- Cautious around failures (never let a single section break the whole /debug)
- Consistent in formatting and streaming partial output
"""

from __future__ import annotations

import json
import logging
import re
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final, Literal, cast

if TYPE_CHECKING:
    from agent_platform.architectures.default.state import ArchState
    from agent_platform.core import Kernel
    from agent_platform.core.kernel_interfaces.data_frames import DataFrameArchState
    from agent_platform.core.tools.tool_definition import ToolDefinition

# ---- Constants ----------------------------------------------------------------

TOGGLE_TARGETS: Final[frozenset[str]] = frozenset({"memory", "data-frames"})

# Precompiled regexes for command parsing (whitespace tolerant)
_RE_TOGGLE: Final[re.Pattern[str]] = re.compile(
    r"^/toggle\s+(?P<target>\S+)\s+(?P<switch>on|off)\s*$", re.IGNORECASE
)
_RE_SET: Final[re.Pattern[str]] = re.compile(r"^/set\s+(?P<path>\S+)\s+(?P<value>.+)$")
_RE_UNSET: Final[re.Pattern[str]] = re.compile(r"^/unset\s+(?P<path>\S+)\s*$", re.IGNORECASE)

logger = logging.getLogger(__name__)

# ---- Commands -----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DebugCommand:
    """Emit a detailed diagnostic dump into the thread (no model call)."""

    pass


@dataclass(frozen=True, slots=True)
class HelpCommand:
    """Render short help for available special commands."""

    pass


@dataclass(frozen=True, slots=True)
class ToggleCommand:
    """Quick toggle for common agent settings."""

    target: Literal["memory", "data-frames"]
    value: bool


@dataclass(frozen=True, slots=True)
class SetCommand:
    """Set a value at agent_settings.<path> (value parsed as JSON if possible)."""

    path: str  # must begin with agent_settings.
    value: Any


@dataclass(frozen=True, slots=True)
class UnsetCommand:
    """Unset the value at agent_settings.<path>."""

    path: str  # must begin with agent_settings.


SpecialCommand = DebugCommand | HelpCommand | ToggleCommand | SetCommand | UnsetCommand

__all__ = [
    "DebugCommand",
    "HelpCommand",
    "SetCommand",
    "SpecialCommand",
    "ToggleCommand",
    "UnsetCommand",
    "handle_special_command",
    "parse_special_command",
]

# ---- Parsing ------------------------------------------------------------------


def parse_special_command(  # noqa: PLR0911
    text: str,
) -> SpecialCommand | None:
    """
    Parse a user-entered special command.

    Grammar (whitespace around tokens is tolerated):
      /debug
      /help
      /toggle <memory|data-frames> <on|off>
      /set agent_settings.<path> <value>
      /unset agent_settings.<path>

    For `/set`, <value> is parsed as JSON if possible; otherwise it's kept as str.

    Returns:
        A SpecialCommand instance if the input matched; otherwise None.
    """
    if not isinstance(text, str):
        return None

    s = text.strip()
    if s == "/debug":
        return DebugCommand()
    if s == "/help":
        return HelpCommand()

    if m := _RE_TOGGLE.fullmatch(s):
        key = m.group("target").lower()
        if key in TOGGLE_TARGETS:
            val = m.group("switch").lower() == "on"
            return ToggleCommand(
                target=cast(Literal["memory", "data-frames"], key),
                value=val,
            )
        return None

    if m := _RE_SET.fullmatch(s):
        path, raw = m.group("path"), m.group("value")
        if path.startswith("agent_settings."):
            return SetCommand(path=path, value=_parse_value_token(raw))
        return None

    if m := _RE_UNSET.fullmatch(s):
        path = m.group("path")
        if path.startswith("agent_settings."):
            return UnsetCommand(path=path)

    return None


# ---- Dispatcher ---------------------------------------------------------------


async def handle_special_command(
    command: SpecialCommand,
    kernel: Kernel,
    *,
    state: ArchState | None = None,
    internal_tools_provider: Callable[[], Sequence[ToolDefinition]] | None = None,
) -> bool:
    """
    Dispatch a parsed SpecialCommand to its handler.

    Returns:
        True if a handler was executed; False if the command was not recognized.
    """
    match command:
        case DebugCommand():
            await _handle_debug(kernel, state, internal_tools_provider)
            return True
        case HelpCommand():
            await _handle_help(kernel)
            return True
        case ToggleCommand() as cmd:
            await _handle_toggle(kernel, state, cmd)
            return True
        case SetCommand() as cmd:
            await _handle_set(kernel, state, cmd)
            return True
        case UnsetCommand() as cmd:
            await _handle_unset(kernel, state, cmd)
            return True
        case _:
            return False


# ---- Debug --------------------------------------------------------------------


async def _handle_debug(  # noqa: C901, PLR0912, PLR0915  (complex by design but structured)
    kernel: Kernel,
    state: ArchState | None,
    internal_tools_provider: Callable[[], Sequence[ToolDefinition]] | None,
) -> None:
    """
    Stream a structured diagnostic report covering:
      - Agent identity + settings
      - Selected model/platform
      - Tool availability across sources
      - Thread and run stats
      - Environment summary
    """
    message = await kernel.thread_state.new_agent_message(
        tag_expected_past_response=None,
        tag_expected_pre_response=None,
    )

    # --- Agent -----------------------------------------------------------------
    try:
        agent = kernel.agent
        lines = [
            "\n### Agent",
            f"- id: `{agent.agent_id}`",
            f"- name: `{agent.name}`",
            f"- version: `{agent.version}`",
            f"- mode: `{agent.mode}`",
            f"- architecture: `{agent.agent_architecture.name}` {agent.agent_architecture.version}",
        ]
        if agent.action_packages:
            pkg_names = ", ".join(f"`{ap.name}`" for ap in agent.action_packages)
            lines.append(f"- action_packages: {len(agent.action_packages)}")
            lines.append(f"  - {pkg_names}")
        else:
            lines.append("- action_packages: 0")
        if agent.mcp_servers:
            mcp_names = ", ".join(f"`{m.name}`" for m in agent.mcp_servers)
            lines.append(f"- mcp_servers: {len(agent.mcp_servers)}")
            lines.append(f"  - {mcp_names}")
        else:
            lines.append("- mcp_servers: 0")

        await _append(message, "\n".join(lines) + "\n")

        # Agent settings (best-effort)
        settings = agent.extra.get("agent_settings", {})
        if not isinstance(settings, dict):
            settings = {}
        await _append(message, "\n#### Agent Settings\n")
        await _append_json_block(message, settings)
    except Exception:
        logger.exception("/debug: agent section failed")
        await _append(message, "\n### Agent\n- <failed to render agent section>\n")

    # --- Model -----------------------------------------------------------------
    platform_name = "<unresolved>"
    model_id = "<unresolved>"
    model_family = "unknown"
    try:
        platform, model = await kernel.get_platform_and_model(model_type="llm")
        platform_name = platform.name
        model_id = model
        try:
            model_family = platform.client.model_map.model_families.get(model) or "unknown"
        except Exception:
            model_family = "unknown"
    except Exception:
        logger.exception("/debug: model selection failed")
    finally:
        selector_name = type(kernel.model_selector).__name__
        lines = [
            "\n### Model",
            f"- platform: `{platform_name}`",
            f"- model: `{model_id}`",
            f"- family: `{model_family}`",
            f"- selector: `{selector_name}`",
        ]
        await _append(message, "\n".join(lines) + "\n")

    # --- Tools -----------------------------------------------------------------
    await _append(message, "\n### Tools\n")
    all_tools_dump: list[dict[str, Any]] = []
    issues: list[str] = []

    if state is not None:
        # Data frames (optional)
        try:
            await kernel.data_frames.step_initialize(state=state)
            df_tools = list(kernel.data_frames.get_data_frame_tools())
            df_names = [f"`{t.name}`" for t in df_tools]
            _append_tool_group(message, "data_frames", df_names, len(df_tools))

            all_tools_dump.extend([t.model_dump() for t in df_tools])
        except Exception as e:
            logger.exception("/debug: data frames tools failed")
            _append_tool_group(message, "data_frames", [], 0)
            await _append(message, f"  - <error: {e}>\n")

        # Work item (optional)
        try:
            await kernel.work_item.step_initialize(state=state)
            wi_tools = list(kernel.work_item.get_work_item_tools())
            wi_names = [f"`{t.name}`" for t in wi_tools]
            _append_tool_group(message, "work_item", wi_names, len(wi_tools))
            await message.stream_delta()

            all_tools_dump.extend([t.model_dump() for t in wi_tools])
        except Exception as e:
            logger.exception("/debug: work item tools failed")
            _append_tool_group(message, "work_item", [], 0)
            await _append(message, f"  - <error: {e}>\n")

        # Documents (optional)
        try:
            await kernel.documents.step_initialize(state=state)
            doc_tools = list(kernel.documents.get_document_tools())
            doc_names = [f"`{t.name}`" for t in doc_tools]
            _append_tool_group(message, "documents", doc_names, len(doc_tools))
            await message.stream_delta()

            all_tools_dump.extend([t.model_dump() for t in doc_tools])
        except Exception as e:
            logger.exception("/debug: document tools failed")
            _append_tool_group(message, "documents", [], 0)
            await _append(message, f"  - <error: {e}>\n")

    # Action tool defs
    try:
        action_tools, action_issues = await kernel.tools.from_action_packages(
            kernel.agent.action_packages
        )
        names = [f"`{t.name}`" for t in action_tools]
        _append_tool_group(message, "action", names, len(action_tools))
        await message.stream_delta()
        all_tools_dump.extend([t.model_dump() for t in action_tools])
        issues.extend(action_issues)
    except Exception as e:
        logger.exception("/debug: action tools failed")
        _append_tool_group(message, "action", [], 0)
        await _append(message, f"  - <error: {e}>\n")

    # MCP tool defs
    try:
        mcp_tools, mcp_issues = await kernel.tools.from_mcp_servers(kernel.agent.mcp_servers)
        names = [f"`{t.name}`" for t in mcp_tools]
        _append_tool_group(message, "mcp", names, len(mcp_tools))
        await message.stream_delta()
        all_tools_dump.extend([t.model_dump() for t in mcp_tools])
        issues.extend(mcp_issues)
    except Exception as e:
        logger.exception("/debug: mcp tools failed")
        _append_tool_group(message, "mcp", [], 0)
        await _append(message, f"  - <error: {e}>\n")

    # Internal tools (optional provider)
    if internal_tools_provider is not None:
        try:
            internal_tools = list(internal_tools_provider())
            df_names = [f"`{t.name}`" for t in internal_tools]
            _append_tool_group(message, "internal", df_names, len(internal_tools))
            await message.stream_delta()
            all_tools_dump.extend([t.model_dump() for t in internal_tools])
        except Exception as e:
            logger.exception("/debug: internal tools failed")
            _append_tool_group(message, "internal", [], 0)
            await _append(message, f"  - <error: {e}>\n")

    # Client tools
    try:
        client_tools = list(kernel.client_tools)
        names = [f"`{t.name}`" for t in client_tools]
        _append_tool_group(message, "client", names, len(client_tools))
        await message.stream_delta()
        all_tools_dump.extend([t.model_dump() for t in client_tools])
    except Exception as e:
        logger.exception("/debug: client tools failed")
        _append_tool_group(message, "client", [], 0)
        await _append(message, f"  - <error: {e}>\n")

    if issues:
        await _append(message, "- issues:\n")
        for issue in issues:
            await _append(message, f"  - {issue}\n")

    # --- Thread/Run ------------------------------------------------------------
    try:
        thread = kernel.thread
        run = kernel.run

        content_counts_by_kind: Counter[str] = Counter()
        total_content_items = 0
        for thread_message in thread.messages:
            for content in thread_message.content:
                content_counts_by_kind[content.kind] += 1
                total_content_items += 1

        lines = [
            "\n### Thread/Run",
            f"- run_id: `{run.run_id}`",
            f"- thread_id: `{thread.thread_id}`",
            f"- messages: {len(thread.messages)}",
            f"- content counts by kind (total content items: {total_content_items}):",
            *[f"  - {kind}: {count}" for kind, count in content_counts_by_kind.items()],
        ]
        await _append(message, "\n".join(lines) + "\n")
    except Exception:
        logger.exception("/debug: thread/run section failed")
        await _append(message, "\n### Thread/Run\n")
        await _append(message, "- <failed to render thread/run>\n")

    # --- Environment ------------------------------------------------------------
    try:
        arch_name = kernel.agent.agent_architecture.name
        arch_ver = kernel.agent.agent_architecture.version
        lines = [
            "\n### Environment",
            f"- architecture: `{arch_name}` {arch_ver}",
            f"- now: `{kernel.current_datetime_str}`",
        ]
        await _append(message, "\n".join(lines) + "\n")
    except Exception:
        logger.exception("/debug: environment section failed")
        await _append(message, "\n### Environment\n- <failed to render environment>\n")

    # --- Metadata & finalize ----------------------------------------------------
    try:
        message.agent_metadata["models"] = []
        message.agent_metadata["platform"] = platform_name
        message.agent_metadata["model"] = model_id
        message.agent_metadata["tools"] = all_tools_dump
    except Exception:
        # Best-effort; do not fail the command because of metadata issues.
        pass

    await _append(message, "\n", complete=True)
    await message.commit()


def _append_tool_group(message, label: str, names: list[str], count: int) -> None:
    """Append a bullet group for a tool source."""
    message.append_content(f"- {label}: {count}\n", complete=False)
    if names:
        for n in sorted(names):
            message.append_content(f"  - {n}\n", complete=False)


# ---- Help ---------------------------------------------------------------------


async def _handle_help(kernel: Kernel) -> None:
    """Render short help text for supported special commands."""
    message = await kernel.thread_state.new_agent_message(
        tag_expected_past_response=None,
        tag_expected_pre_response=None,
    )
    lines = [
        "Special Commands",
        "",
        "### /debug",
        "Dump internal info (no model call).",
        "",
        "### /help",
        "Show this help.",
        "",
        "### /toggle <memory|data-frames> <on|off>",
        "Quick toggle for common agent settings.",
        "",
        "### /set agent_settings.<path> <value>",
        "Set arbitrary agent_settings value. Value parsed as JSON if possible,",
        "else used as string.",
        "",
        "### /unset agent_settings.<path>",
        "Remove a setting at the given path.",
        "",
        "Examples:",
        "- /toggle memory on",
        "- /toggle data-frames off",
        "- /set agent_settings.temperature 0.4",
        "- /set agent_settings.execution.max_iterations 12",
        "- /unset agent_settings.integrations.enable_web_search",
    ]
    message.append_content("\n".join(lines), complete=True)
    await message.stream_delta()
    await message.commit()


# ---- Settings -----------------------------------------------------------------


async def _handle_toggle(
    kernel: Kernel, state: DataFrameArchState | None, cmd: ToggleCommand
) -> None:
    """Handle /toggle by mapping the logical key to its settings path."""
    mapping: dict[Literal["memory", "data-frames"], str] = {
        "memory": "agent_settings.enable_memory",
        "data-frames": "agent_settings.enable_data_frames",
    }
    path = mapping[cmd.target]
    await _apply_setting_update(kernel, op="set", path=path, value=cmd.value)


async def _handle_set(kernel: Kernel, state: DataFrameArchState | None, cmd: SetCommand) -> None:
    """Handle /set by updating the requested path with the provided value."""
    await _apply_setting_update(kernel, op="set", path=cmd.path, value=cmd.value)


async def _handle_unset(
    kernel: Kernel, state: DataFrameArchState | None, cmd: UnsetCommand
) -> None:
    """Handle /unset by removing the requested path."""
    await _apply_setting_update(kernel, op="unset", path=cmd.path)


async def _apply_setting_update(
    kernel: Kernel,
    *,
    op: Literal["set", "unset"],
    path: str,
    value: Any | None = None,
) -> None:
    """
    Apply a settings mutation, stream a small report, and persist.

    Behavior:
      - Only paths under `agent_settings.` are allowed.
      - Update both the persisted copy (via storage) and the in-memory copy on the agent.
      - Print a compact JSON view of the resulting agent_settings.
    """
    message = await kernel.thread_state.new_agent_message(
        tag_expected_past_response=None,
        tag_expected_pre_response=None,
    )
    await _append(message, "Settings Update\n")

    if not path.startswith("agent_settings."):
        await _append(message, "- Error: path must start with `agent_settings.`\n", complete=True)
        await message.commit()
        return

    inner_path = path[len("agent_settings.") :]
    agent = kernel.agent

    # Deep-copy agent.extra via JSON for safety; if it fails, fall back to a Python copy.
    try:
        new_extra = json.loads(json.dumps(agent.extra)) if agent.extra else {}
    except Exception:
        new_extra = dict(agent.extra or {})

    settings = new_extra.setdefault("agent_settings", {})
    if not isinstance(settings, dict):
        new_extra["agent_settings"] = settings = {}

    prev = _get_by_path(settings, inner_path)
    if op == "set":
        _set_by_path(settings, inner_path, value)
    else:
        _unset_by_path(settings, inner_path)
    new_val = _get_by_path(settings, inner_path)

    # Immediate in-memory effect
    live_settings = agent.extra.setdefault("agent_settings", {})
    if not isinstance(live_settings, dict):
        agent.extra["agent_settings"] = live_settings = {}
    if op == "set":
        _set_by_path(live_settings, inner_path, value)
    else:
        _unset_by_path(live_settings, inner_path)

    await _append(message, f"- Path: `{path}`\n")
    await _append(message, f"- Previous: `{prev}`\n")
    await _append(message, f"- New: `{new_val}`\n" if op == "set" else "- New: <unset>\n")

    # Persist
    try:
        updated_agent = kernel.agent.copy(extra=new_extra)
        await kernel.storage.upsert_agent(kernel.user.user_id, updated_agent)
        await _append(message, "- Persisted: yes\n")
    except Exception as e:
        logger.exception("Failed to persist agent settings")
        await _append(message, "- Persisted: no\n")
        await _append(message, f"  - error: {e}\n")

    await _append(message, "\n#### agent_settings\n")
    await _append_json_block(message, settings)

    await _append(message, "\n", complete=True)
    await message.commit()


# ---- Small helpers ------------------------------------------------------------


def _parse_value_token(raw: str) -> Any:
    """Try to decode a token as JSON; fall back to string on failure."""
    try:
        return json.loads(raw)
    except Exception:
        return raw


def _get_by_path(obj: dict, dotted_path: str) -> Any:
    """Get a nested value by dot-separated path; return None if not present."""
    cur: Any = obj
    for part in dotted_path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _set_by_path(obj: dict, dotted_path: str, value: Any) -> None:
    """Set a nested value by dot-separated path, creating intermediate dicts as needed."""
    parts = dotted_path.split(".")
    cur = obj
    for part in parts[:-1]:
        nxt = cur.get(part)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[part] = nxt
        cur = nxt
    cur[parts[-1]] = value


def _unset_by_path(obj: dict, dotted_path: str) -> None:
    """Unset a nested value by dot-separated path; no-op if any link is missing."""
    parts = dotted_path.split(".")
    cur = obj
    for part in parts[:-1]:
        nxt = cur.get(part)
        if not isinstance(nxt, dict):
            return
        cur = nxt
    cur.pop(parts[-1], None)


async def _append(message, text: str, *, complete: bool = False) -> None:
    """
    Append text to the message and stream the delta right away.

    Using this tiny helper keeps the streaming style consistent and avoids
    repetitive boilerplate.
    """
    message.append_content(text, complete=complete)
    await message.stream_delta()


async def _append_json_block(message, data: Any) -> None:
    """Append a pretty-printed JSON code block for the given data."""
    try:
        dumped = json.dumps(data, indent=2, sort_keys=True)
    except Exception:
        # Best-effort fallback if the payload is not JSON-serializable
        try:
            dumped = json.dumps(str(data))
        except Exception:
            dumped = '"<unserializable>"'
    await _append(message, "```json\n" + dumped + "\n```\n")
