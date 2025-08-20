from unittest.mock import MagicMock

import pytest

from agent_platform.core.prompts.special.conversation_history import (
    ConversationHistoryParams,
    ConversationHistorySpecialMessage,
)


@pytest.mark.asyncio
async def test_conversation_history_uses_agent_setting_over_params():
    """When agent setting is present, it should take precedence over params."""
    # Kernel mocks
    thread_spy = MagicMock()
    thread_spy.get_last_n_message_turns = MagicMock(return_value=[])

    class ConvertersMock:
        async def thread_messages_to_prompt_messages(self, messages):
            return ["converted"]

    agent_mock = type(
        "AgentMock",
        (),
        {"extra": {"agent_settings": {"conversation_turns_kept_in_context": 7}}},
    )()

    kernel = type(
        "KernelMock",
        (),
        {"thread": thread_spy, "converters": ConvertersMock(), "agent": agent_mock},
    )()

    # Params specify a different default to ensure precedence is visible
    params = ConversationHistoryParams(maximum_number_of_turns=3)
    special = ConversationHistorySpecialMessage(role="$conversation-history", params=params)

    result = await special.hydrate(kernel)  # type: ignore[arg-type]

    # Verify precedence: agent setting value was used
    thread_spy.get_last_n_message_turns.assert_called_once_with(n=7)
    assert result == ["converted"]


@pytest.mark.asyncio
async def test_conversation_history_uses_params_when_no_setting():
    """When no agent setting is present, params value should be used."""
    thread_spy = MagicMock()
    thread_spy.get_last_n_message_turns = MagicMock(return_value=[])

    class ConvertersMock:
        async def thread_messages_to_prompt_messages(self, messages):
            return ["ok"]

    agent_mock = type("AgentMock", (), {"extra": {"agent_settings": {}}})()

    kernel = type(
        "KernelMock",
        (),
        {"thread": thread_spy, "converters": ConvertersMock(), "agent": agent_mock},
    )()

    params = ConversationHistoryParams(maximum_number_of_turns=11)
    special = ConversationHistorySpecialMessage(role="$conversation-history", params=params)

    result = await special.hydrate(kernel)  # type: ignore[arg-type]

    thread_spy.get_last_n_message_turns.assert_called_once_with(n=11)
    assert result == ["ok"]


@pytest.mark.asyncio
async def test_conversation_history_coerces_string_setting_to_int():
    """String values for the agent setting should be coerced to int and used."""
    thread_spy = MagicMock()
    thread_spy.get_last_n_message_turns = MagicMock(return_value=[])

    class ConvertersMock:
        async def thread_messages_to_prompt_messages(self, messages):
            return ["converted"]

    agent_mock = type(
        "AgentMock",
        (),
        {"extra": {"agent_settings": {"conversation_turns_kept_in_context": "9"}}},
    )()

    kernel = type(
        "KernelMock",
        (),
        {"thread": thread_spy, "converters": ConvertersMock(), "agent": agent_mock},
    )()

    params = ConversationHistoryParams(maximum_number_of_turns=5)
    special = ConversationHistorySpecialMessage(role="$conversation-history", params=params)

    await special.hydrate(kernel)  # type: ignore[arg-type]
    thread_spy.get_last_n_message_turns.assert_called_once_with(n=9)
