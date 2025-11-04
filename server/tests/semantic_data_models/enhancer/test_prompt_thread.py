"""Unit tests for PromptThread functionality in prompts.py."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from agent_platform.core.prompts.messages import PromptTextContent, PromptUserMessage
from agent_platform.core.responses.content.tool_use import ResponseToolUseContent
from agent_platform.core.responses.response import ResponseMessage


def _create_tool_response_message(tool_input: dict) -> ResponseMessage:
    """Helper to create a ResponseMessage with tool call content."""
    return ResponseMessage(
        role="agent",
        content=[
            ResponseToolUseContent(
                tool_call_id="test_call_id",
                tool_name="enhance_semantic_data_model",
                tool_input_raw=json.dumps(tool_input),
            )
        ],
    )


@pytest.fixture
def prompt_thread():
    """Create a basic PromptThread for testing."""
    from agent_platform.server.semantic_data_models.enhancer.prompts import PromptThread

    return PromptThread(
        system_instruction="Test system instruction",
        messages=[PromptUserMessage(content=[PromptTextContent(text="Initial message")])],
    )


class TestPromptThreadUpdateWithPreviousTry:
    """Tests for update_prompt_with_previous_try method."""

    def test_prompt_thread_update_with_llm_error(self, prompt_thread):
        """Verify prompt is updated with improvement request when LLMResponseError occurs."""
        from agent_platform.server.semantic_data_models.enhancer.errors import (
            LLMResponseError,
        )

        # Create a mock retry state with LLMResponseError
        retry_state = MagicMock()
        retry_state.outcome = MagicMock()
        retry_state.outcome.failed = True

        error = LLMResponseError(
            improvement_request="Please fix the JSON syntax",
            response_message=_create_tool_response_message({"name": "test"}),
        )
        retry_state.outcome.exception.return_value = error

        # Update the prompt
        prompt_thread.update_prompt_with_previous_try(retry_state)

        # Verify messages were appended
        assert len(prompt_thread.messages) == 3  # Initial + agent + user
        # Check that the last message contains the improvement request
        assert "fix the JSON syntax" in prompt_thread.messages[-1].content[0].text

    def test_prompt_thread_update_with_quality_error(self, prompt_thread):
        """Verify prompt is updated with improvement request when QualityCheckError occurs."""
        from agent_platform.server.semantic_data_models.enhancer.errors import (
            QualityCheckError,
        )

        # Create a mock retry state with QualityCheckError
        retry_state = MagicMock()
        retry_state.outcome = MagicMock()
        retry_state.outcome.failed = True

        error = QualityCheckError(
            improvement_request="Please improve the quality",
            response_message=_create_tool_response_message({"name": "test"}),
        )
        retry_state.outcome.exception.return_value = error

        # Update the prompt
        prompt_thread.update_prompt_with_previous_try(retry_state)

        # Verify messages were appended
        assert len(prompt_thread.messages) == 3  # Initial + agent + user
        # Check that the last message contains the improvement request
        assert "improve the quality" in prompt_thread.messages[-1].content[0].text

    def test_prompt_thread_update_without_error(self, prompt_thread):
        """Verify no changes when retry state has no error."""
        initial_message_count = len(prompt_thread.messages)

        # Create a mock retry state without error
        retry_state = MagicMock()
        retry_state.outcome = MagicMock()
        retry_state.outcome.failed = False

        # Update the prompt
        prompt_thread.update_prompt_with_previous_try(retry_state)

        # Verify no messages were added
        assert len(prompt_thread.messages) == initial_message_count

    def test_prompt_thread_update_missing_response_message(self, prompt_thread):
        """Verify ValueError when error has no response_message."""
        from agent_platform.server.semantic_data_models.enhancer.errors import (
            LLMResponseError,
        )

        # Create a mock retry state with LLMResponseError but no response_message
        retry_state = MagicMock()
        retry_state.outcome = MagicMock()
        retry_state.outcome.failed = True

        error = LLMResponseError(
            improvement_request="Please fix the JSON syntax",
            response_message=None,  # Missing response_message
        )
        retry_state.outcome.exception.return_value = error

        # Update should raise ValueError
        with pytest.raises(ValueError, match="No response message available"):
            prompt_thread.update_prompt_with_previous_try(retry_state)


class TestPromptThreadAppendResponseAndError:
    """Tests for append_response_and_error method."""

    def test_prompt_thread_append_response_and_error(self, prompt_thread):
        """Verify agent message with tool call and user message are correctly appended."""
        from agent_platform.core.prompts.messages import PromptToolUseContent

        initial_message_count = len(prompt_thread.messages)

        tool_input = {"name": "Test Model", "tables": []}
        response = _create_tool_response_message(tool_input)
        improvement_request = "Please fix the JSON syntax"

        prompt_thread.append_response_and_error(response, improvement_request)

        # Verify messages were appended
        assert len(prompt_thread.messages) == initial_message_count + 2

        # Check agent message (second to last) contains tool call
        agent_message = prompt_thread.messages[-2]
        assert isinstance(agent_message.content[0], PromptToolUseContent)
        assert agent_message.content[0].tool_name == "enhance_semantic_data_model"
        assert agent_message.content[0].tool_call_id == "test_call_id"

        # Check user message (last)
        user_message = prompt_thread.messages[-1]
        assert user_message.content[0].text == improvement_request

    def test_prompt_thread_append_empty_response(self, prompt_thread):
        """Verify graceful handling when response is empty."""
        from agent_platform.core.responses.response import ResponseMessage

        # Create an empty response (no content)
        empty_response = ResponseMessage(
            role="agent",
            content=[],
        )
        improvement_request = "Please provide content"

        # Should not raise, but should handle gracefully
        initial_message_count = len(prompt_thread.messages)
        prompt_thread.append_response_and_error(empty_response, improvement_request)

        # Should still append messages (with empty text handling)
        assert len(prompt_thread.messages) == initial_message_count + 2

        # The user message should still be appended
        assert prompt_thread.messages[-1].content[0].text == improvement_request
