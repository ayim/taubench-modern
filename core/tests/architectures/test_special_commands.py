import re

import pytest

from agent_platform.architectures.default.state import ArchState
from agent_platform.core.agent_architectures.special_commands import (
    DataCommand,
    DebugCommand,
    HelpCommand,
    SetCommand,
    ToggleCommand,
    UnsetCommand,
    handle_special_command,
    parse_special_command,
)
from agent_platform.core.thread.base import ThreadMessage
from agent_platform.core.thread.content.text import ThreadTextContent

pytest_plugins = ["server.tests.storage_fixtures"]


@pytest.mark.asyncio
async def test_parse_toggle_memory_on():
    cmd = parse_special_command("/toggle memory on")
    assert isinstance(cmd, ToggleCommand)
    assert cmd.target == "memory"
    assert cmd.value is True


@pytest.mark.asyncio
async def test_handle_help_streams_message(file_regression, sqlite_model_creator):
    kernel = await sqlite_model_creator.create_agent_server_kernel()
    ok = await handle_special_command(HelpCommand(), kernel)
    assert ok is True
    msg = kernel.thread.messages[-1]
    file_regression.check(_message_text(msg), extension=".md")


@pytest.mark.asyncio
async def test_handle_set_persists_and_mutates_in_memory(sqlite_storage, sqlite_model_creator):
    kernel = await sqlite_model_creator.create_agent_server_kernel()
    cmd = SetCommand(path="agent_settings.testing", value=0.42)
    ok = await handle_special_command(cmd, kernel)
    assert ok is True
    assert kernel.agent.extra["agent_settings"]["testing"] == 0.42
    stored_agent = await sqlite_storage.get_agent(kernel.user.user_id, kernel.agent.agent_id)
    assert stored_agent.extra["agent_settings"]["testing"] == 0.42


@pytest.mark.asyncio
async def test_parse_help_and_debug():
    assert isinstance(parse_special_command("/help"), HelpCommand)
    assert isinstance(parse_special_command("/debug"), DebugCommand)
    assert isinstance(parse_special_command("/data"), DataCommand)


@pytest.mark.asyncio
async def test_parse_toggle_data_frames_off_whitespace_case():
    cmd = parse_special_command("  /TOGGLE   data-frames   OFF  ")
    assert isinstance(cmd, ToggleCommand)
    assert cmd.target == "data-frames"
    assert cmd.value is False


@pytest.mark.asyncio
async def test_parse_set_json_and_string_values():
    # JSON number parsed to float
    cmd_num = parse_special_command("/set agent_settings.temperature 0.7")
    assert isinstance(cmd_num, SetCommand)
    assert isinstance(cmd_num.value, float)
    assert cmd_num.value == pytest.approx(0.7)

    # Non-JSON string with spaces kept as raw string
    cmd_str = parse_special_command("/set agent_settings.title hello world")
    assert isinstance(cmd_str, SetCommand)
    assert cmd_str.value == "hello world"


@pytest.mark.asyncio
async def test_handle_toggle_memory_on_off_mutates_and_persists(
    sqlite_storage, sqlite_model_creator
):
    kernel = await sqlite_model_creator.create_agent_server_kernel()

    # Turn on
    cmd_on = parse_special_command("/toggle memory on")
    assert isinstance(cmd_on, ToggleCommand)
    ok = await handle_special_command(cmd_on, kernel)
    assert ok is True
    assert kernel.agent.extra["agent_settings"]["enable_memory"] is True
    stored_agent = await sqlite_storage.get_agent(kernel.user.user_id, kernel.agent.agent_id)
    assert stored_agent.extra["agent_settings"]["enable_memory"] is True

    # Turn off
    cmd_off = parse_special_command("/toggle memory off")
    assert isinstance(cmd_off, ToggleCommand)
    ok = await handle_special_command(cmd_off, kernel)
    assert ok is True
    assert kernel.agent.extra["agent_settings"]["enable_memory"] is False
    stored_agent = await sqlite_storage.get_agent(kernel.user.user_id, kernel.agent.agent_id)
    assert stored_agent.extra["agent_settings"]["enable_memory"] is False


@pytest.mark.asyncio
async def test_handle_unset_removes_and_persists(sqlite_storage, sqlite_model_creator):
    kernel = await sqlite_model_creator.create_agent_server_kernel()
    # Set nested value
    ok = await handle_special_command(SetCommand("agent_settings.a.b", 123), kernel)
    assert ok is True
    assert kernel.agent.extra["agent_settings"]["a"]["b"] == 123

    # Unset nested value
    ok = await handle_special_command(UnsetCommand("agent_settings.a.b"), kernel)
    assert ok is True
    assert "b" not in kernel.agent.extra["agent_settings"]["a"]
    stored_agent = await sqlite_storage.get_agent(kernel.user.user_id, kernel.agent.agent_id)
    assert "a" in stored_agent.extra["agent_settings"]
    assert "b" not in stored_agent.extra["agent_settings"]["a"]


@pytest.mark.asyncio
async def test_handle_set_invalid_path_streams_error_and_no_persist(
    file_regression, sqlite_storage, sqlite_model_creator
):
    kernel = await sqlite_model_creator.create_agent_server_kernel()
    ok = await handle_special_command(SetCommand("foo.bar", 1), kernel)
    assert ok is True
    msg = kernel.thread.messages[-1]
    file_regression.check(_message_text(msg), extension=".md")
    stored_agent = await sqlite_storage.get_agent(kernel.user.user_id, kernel.agent.agent_id)
    assert "agent_settings" not in stored_agent.extra


def test_parse_toggle_invalid_target_returns_none():
    assert parse_special_command("/toggle unknown on") is None


@pytest.mark.asyncio
async def test_handle_data_streams_context_sections(
    sqlite_storage,
    sqlite_model_creator,
    monkeypatch: pytest.MonkeyPatch,
    file_regression,
):
    monkeypatch.delenv("SEMA4AI_AGENT_SERVER_ENABLE_DATA_FRAMES", raising=False)

    kernel = await sqlite_model_creator.create_agent_server_kernel()
    state = ArchState()

    ok = await handle_special_command(DataCommand(), kernel, state=state)
    assert ok is True

    assert kernel.thread.messages, "Expected a committed agent message"
    msg = kernel.thread.messages[-1]
    body = _normalize_dynamic_values(_message_text(msg))
    file_regression.check(body, extension=".md")


@pytest.mark.asyncio
async def test_handle_data_streams_real_kernel_with_sqlite(
    sqlite_storage,
    sqlite_model_creator,  # provided by storage_fixtures
    monkeypatch: pytest.MonkeyPatch,
    file_regression,
):
    # Make sure env flag doesn't disable data frames for this scenario.
    monkeypatch.delenv("SEMA4AI_AGENT_SERVER_ENABLE_DATA_FRAMES", raising=False)

    await sqlite_model_creator.obtain_sample_data_frame()
    semantic_data_model_id = await sqlite_model_creator.obtain_sample_semantic_data_model()

    kernel = await sqlite_model_creator.create_agent_server_kernel()
    # Associate semantic data model to this agent so the collector returns it.
    await sqlite_storage.set_agent_semantic_data_models(
        agent_id=kernel.agent.agent_id, semantic_data_model_ids=[semantic_data_model_id]
    )

    state = ArchState()

    ok = await handle_special_command(DataCommand(), kernel, state=state)
    assert ok is True

    assert kernel.thread.messages, "Expected a committed agent message"
    msg = kernel.thread.messages[-1]
    body = "".join(getattr(c, "text", "") for c in msg.content)

    normalized = _normalize_dynamic_values(body)
    file_regression.check(normalized, extension=".md")


@pytest.mark.asyncio
async def test_handle_data_reports_env_disable_reason(
    sqlite_model_creator, monkeypatch: pytest.MonkeyPatch, file_regression
):
    monkeypatch.setenv("SEMA4AI_AGENT_SERVER_ENABLE_DATA_FRAMES", "0")

    kernel = await sqlite_model_creator.create_agent_server_kernel()
    state = ArchState()

    ok = await handle_special_command(DataCommand(), kernel, state=state)
    assert ok is True

    msg = kernel.thread.messages[-1]
    body = "".join(getattr(c, "text", "") for c in msg.content)

    normalized = _normalize_dynamic_values(body)
    file_regression.check(normalized, extension=".md")


def _normalize_dynamic_values(text: str) -> str:
    """Replace non-deterministic values (UUIDs, timestamps) to stabilize snapshots."""
    text = re.sub(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        "<uuid>",
        text,
    )
    text = re.sub(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?",
        "<timestamp>",
        text,
    )
    return text


def _message_text(msg: ThreadMessage) -> str:
    """Extract concatenated text from a thread message."""
    parts: list[str] = []
    for item in msg.content:
        if isinstance(item, ThreadTextContent):
            parts.append(item.text)
        else:
            parts.append(str(item))
    return "".join(parts)
