"""Tests for ValidateSemanticDataModelPayload validation logic."""

import pytest

from agent_platform.core.errors import ErrorCode, PlatformHTTPError
from agent_platform.core.payloads.semantic_data_model_payloads import (
    ValidateSemanticDataModelPayload,
)


def test_requires_at_least_one_parameter():
    """Test that at least one parameter must be provided."""
    with pytest.raises(PlatformHTTPError) as exc_info:
        ValidateSemanticDataModelPayload()

    assert exc_info.value.response.error_code == ErrorCode.BAD_REQUEST
    assert "At least one of" in str(exc_info.value)


def test_only_one_selector_allowed():
    """Test that only one selector can be provided (thread_id can be added for context)."""
    with pytest.raises(PlatformHTTPError) as exc_info:
        ValidateSemanticDataModelPayload(
            semantic_data_model={"name": "test"},
            agent_id="agent_123",
        )

    assert exc_info.value.response.error_code == ErrorCode.BAD_REQUEST
    assert "Only one of" in str(exc_info.value)


def test_error_message_includes_provided_options():
    """Test that error message lists the provided options when multiple selectors are given."""
    with pytest.raises(PlatformHTTPError) as exc_info:
        ValidateSemanticDataModelPayload(
            semantic_data_model_id="sdm_123",
            agent_id="agent_123",
        )

    error_msg = str(exc_info.value)
    assert "got:" in error_msg
    assert "semantic_data_model_id" in error_msg


def test_valid_payload_with_single_parameter():
    """Test that valid payload with one parameter works."""
    payload = ValidateSemanticDataModelPayload(agent_id="agent_123")
    assert payload.agent_id == "agent_123"
    assert payload.semantic_data_model is None
    assert payload.semantic_data_model_id is None
    assert payload.thread_id is None


def test_error_message_truncates_long_values():
    """Test that error messages truncate long semantic_data_model values."""
    very_long_sdm = {"name": "test", "data": "x" * 100}
    with pytest.raises(PlatformHTTPError) as exc_info:
        ValidateSemanticDataModelPayload(
            semantic_data_model=very_long_sdm,
            agent_id="agent_123",
        )

    error_msg = str(exc_info.value)
    # Should truncate to 50 chars per the implementation
    assert "x" * 100 not in error_msg


def test_thread_id_can_be_combined_with_selectors():
    """Test that thread_id can be provided alongside other selectors for file resolution."""
    # thread_id + semantic_data_model
    payload1 = ValidateSemanticDataModelPayload(
        semantic_data_model={"name": "test"},
        thread_id="thread_123",
    )
    assert payload1.semantic_data_model is not None
    assert payload1.thread_id == "thread_123"

    # thread_id + semantic_data_model_id
    payload2 = ValidateSemanticDataModelPayload(
        semantic_data_model_id="sdm_123",
        thread_id="thread_123",
    )
    assert payload2.semantic_data_model_id == "sdm_123"
    assert payload2.thread_id == "thread_123"

    # thread_id + agent_id
    payload3 = ValidateSemanticDataModelPayload(
        agent_id="agent_123",
        thread_id="thread_123",
    )
    assert payload3.agent_id == "agent_123"
    assert payload3.thread_id == "thread_123"

    # thread_id alone
    payload4 = ValidateSemanticDataModelPayload(thread_id="thread_123")
    assert payload4.thread_id == "thread_123"
    assert payload4.agent_id is None
