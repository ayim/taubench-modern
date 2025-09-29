import pytest

from agent_platform.core.agent_architectures.special_commands import (
    HelpCommand,
    SetCommand,
    ToggleCommand,
    UnsetCommand,
    handle_special_command,
    parse_special_command,
)
from core.tests.helpers.kernel_stubs import MinimalKernelStub


@pytest.mark.asyncio
async def test_parse_toggle_memory_on():
    cmd = parse_special_command("/toggle memory on")
    assert isinstance(cmd, ToggleCommand)
    assert cmd.target == "memory"
    assert cmd.value is True


@pytest.mark.asyncio
async def test_handle_help_streams_message():
    kernel = MinimalKernelStub()
    ok = await handle_special_command(HelpCommand(), kernel)
    assert ok is True
    msg = kernel._thread_state._last_msg
    assert msg is not None
    assert msg._committed is True
    assert any("Special Commands" in c for c in msg.contents)


@pytest.mark.asyncio
async def test_handle_set_persists_and_mutates_in_memory():
    kernel = MinimalKernelStub()
    cmd = SetCommand(path="agent_settings.testing", value=0.42)
    ok = await handle_special_command(cmd, kernel)
    assert ok is True
    assert kernel.agent.extra["agent_settings"]["testing"] == 0.42
    assert kernel.storage._last_upsert is not None
    user_id, agent = kernel.storage._last_upsert
    assert user_id == kernel.user.user_id
    assert agent.extra["agent_settings"]["testing"] == 0.42


@pytest.mark.asyncio
async def test_parse_help_and_debug():
    assert isinstance(parse_special_command("/help"), HelpCommand)
    from agent_platform.core.agent_architectures.special_commands import DebugCommand

    assert isinstance(parse_special_command("/debug"), DebugCommand)


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
async def test_handle_toggle_memory_on_off_mutates_and_persists():
    kernel = MinimalKernelStub()

    # Turn on
    cmd_on = parse_special_command("/toggle memory on")
    assert isinstance(cmd_on, ToggleCommand)
    ok = await handle_special_command(cmd_on, kernel)
    assert ok is True
    assert kernel.agent.extra["agent_settings"]["enable_memory"] is True
    assert kernel.storage._last_upsert is not None

    # Turn off
    cmd_off = parse_special_command("/toggle memory off")
    assert isinstance(cmd_off, ToggleCommand)
    ok = await handle_special_command(cmd_off, kernel)
    assert ok is True
    assert kernel.agent.extra["agent_settings"]["enable_memory"] is False


@pytest.mark.asyncio
async def test_handle_unset_removes_and_persists():
    kernel = MinimalKernelStub()
    # Set nested value
    ok = await handle_special_command(SetCommand("agent_settings.a.b", 123), kernel)
    assert ok is True
    assert kernel.agent.extra["agent_settings"]["a"]["b"] == 123

    # Unset nested value
    ok = await handle_special_command(UnsetCommand("agent_settings.a.b"), kernel)
    assert ok is True
    assert "b" not in kernel.agent.extra["agent_settings"]["a"]
    # Persisted at least once
    assert kernel.storage._last_upsert is not None


@pytest.mark.asyncio
async def test_handle_set_invalid_path_streams_error_and_no_persist():
    kernel = MinimalKernelStub()
    ok = await handle_special_command(SetCommand("foo.bar", 1), kernel)
    assert ok is True
    msg = kernel._thread_state._last_msg
    assert msg is not None
    assert msg._committed is True
    assert any("path must start with `agent_settings.`" in c for c in msg.contents)
    # No upsert called
    assert kernel.storage._last_upsert is None


def test_parse_toggle_invalid_target_returns_none():
    assert parse_special_command("/toggle unknown on") is None
