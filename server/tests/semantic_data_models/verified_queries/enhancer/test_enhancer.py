"""Unit tests for verified query enhancer."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def sample_verified_query():
    """Create a sample verified query for testing."""
    from agent_platform.core.semantic_data_model.types import (
        QueryParameter,
        VerifiedQuery,
    )

    return VerifiedQuery(
        name="Driver Race Count",
        nlq="Show data",
        verified_at="2024-01-01T00:00:00Z",
        verified_by="user_123",
        sql="SELECT driver_name, COUNT(*) as race_count FROM drivers GROUP BY driver_name HAVING COUNT(*) > :count",
        parameters=[
            QueryParameter(
                name="count",
                data_type="integer",
                example_value=10,
                description="Please provide description for this parameter",
            )
        ],
    )


@pytest.fixture
def sample_sdm():
    """Create a sample semantic data model."""
    from agent_platform.core.semantic_data_model.types import SemanticDataModel

    sdm = SemanticDataModel(
        name="formula_1",
        description="Formula 1 racing data",
        tables=[
            {
                "name": "drivers",
                "description": "Information about Formula 1 drivers",
                "base_table": {
                    "data_connection_id": "conn_123",
                    "table": "drivers",
                },
                "dimensions": [
                    {
                        "name": "driver_name",
                        "description": "The name of the driver",
                        "expr": "name",
                        "data_type": "TEXT",
                        "unique": False,
                        "sample_values": ["Lewis Hamilton"],
                    }
                ],
                "metrics": [
                    {
                        "name": "race_count",
                        "description": "Total number of races participated in",
                        "expr": "COUNT(*)",
                        "data_type": "NUMBER",
                    }
                ],
            }
        ],
    )

    return sdm


@pytest.fixture
def mock_user():
    """Create a mock user."""
    user = MagicMock()
    user.user_id = "user_123"
    return user


@pytest.fixture
def mock_storage():
    """Create a mock storage."""
    return MagicMock()


@pytest.fixture
def mock_llm_response_success():
    """Create a mock LLM response with valid enhanced metadata."""
    import json

    from agent_platform.core.responses.content import ResponseToolUseContent
    from agent_platform.core.responses.response import ResponseMessage

    tool_input_data = {
        "query_name": "High Performing Drivers",
        "nlq": "Which drivers have participated in more than a certain number of races?",
        "parameter_descriptions": [
            {
                "name": "count",
                "description": "Minimum number of races the driver must have participated in",
            }
        ],
    }

    tool_call = ResponseToolUseContent(
        tool_call_id="call_123",
        tool_name="enhance_verified_query",
        tool_input_raw=json.dumps(tool_input_data),
    )

    return ResponseMessage(
        role="agent",
        content=[tool_call],
    )


@pytest.fixture
def mock_llm_response_invalid():
    """Create a mock LLM response with invalid metadata (missing parameter)."""
    import json

    from agent_platform.core.responses.content import ResponseToolUseContent
    from agent_platform.core.responses.response import ResponseMessage

    tool_input_data = {
        "query_name": "High Performing Drivers",
        "nlq": "Which drivers have participated in more than a certain number of races?",
        "parameter_descriptions": [],  # Missing parameter!
    }

    tool_call = ResponseToolUseContent(
        tool_call_id="call_123",
        tool_name="enhance_verified_query",
        tool_input_raw=json.dumps(tool_input_data),
    )

    return ResponseMessage(
        role="agent",
        content=[tool_call],
    )


@pytest.mark.asyncio
async def test_enhancer_merge_enhanced_metadata(
    mock_user,
    mock_storage,
    sample_verified_query,
    mock_llm_response_success,
):
    """Test that enhanced metadata is merged correctly with original query."""
    from agent_platform.server.semantic_data_models.verified_queries.enhancer.enhancer import (
        VerifiedQueryEnhancer,
    )

    enhancer = VerifiedQueryEnhancer(
        user=mock_user,
        storage=mock_storage,
        agent_id="agent_123",
    )

    merged = enhancer._merge_enhanced_metadata(
        original_query=sample_verified_query,
        llm_response=mock_llm_response_success,
    )

    # Check enhanced fields
    assert merged.name == "High Performing Drivers"
    assert merged.nlq == "Which drivers have participated in more than a certain number of races?"

    # Check preserved fields
    assert merged.sql == sample_verified_query.sql
    assert merged.verified_at == sample_verified_query.verified_at
    assert merged.verified_by == sample_verified_query.verified_by

    # Check merged parameters
    assert merged.parameters is not None
    assert len(merged.parameters) == 1
    param = merged.parameters[0]
    assert param.name == "count"
    assert param.data_type == "integer"
    assert param.example_value == 10
    assert param.description == "Minimum number of races the driver must have participated in"


@pytest.mark.asyncio
async def test_enhancer_extract_enhanced_metadata_success(
    mock_user,
    mock_storage,
    mock_llm_response_success,
):
    """Test that enhanced metadata is extracted correctly from LLM response."""
    from agent_platform.server.semantic_data_models.verified_queries.enhancer.enhancer import (
        VerifiedQueryEnhancer,
    )

    enhancer = VerifiedQueryEnhancer(
        user=mock_user,
        storage=mock_storage,
        agent_id="agent_123",
    )

    metadata = enhancer._extract_enhanced_metadata(mock_llm_response_success)

    assert metadata.query_name == "High Performing Drivers"
    assert metadata.nlq == "Which drivers have participated in more than a certain number of races?"
    assert len(metadata.parameter_descriptions) == 1
    assert metadata.parameter_descriptions[0].name == "count"


@pytest.mark.asyncio
async def test_enhancer_extract_enhanced_metadata_no_tool_call(
    mock_user,
    mock_storage,
):
    """Test that extraction fails when no tool call found."""
    from agent_platform.core.responses.content.text import ResponseTextContent
    from agent_platform.core.responses.response import ResponseMessage
    from agent_platform.server.semantic_data_models.verified_queries.enhancer.enhancer import (
        VerifiedQueryEnhancer,
    )

    enhancer = VerifiedQueryEnhancer(
        user=mock_user,
        storage=mock_storage,
        agent_id="agent_123",
    )

    # Response with no tool call
    response = ResponseMessage(
        role="agent",
        content=[ResponseTextContent(text="I can't do that")],
    )

    with pytest.raises(ValueError, match="No tool call found"):
        enhancer._extract_enhanced_metadata(response)


@pytest.mark.asyncio
async def test_enhancer_fallback_on_failure(
    mock_user,
    mock_storage,
    sample_verified_query,
    sample_sdm,
    monkeypatch,
):
    """Test that enhancer falls back to original query on failure."""
    from agent_platform.server.semantic_data_models.verified_queries.enhancer.enhancer import (
        VerifiedQueryEnhancer,
    )

    # Mock _call_llm to raise an exception
    async def mock_call_llm(*args, **kwargs):
        raise Exception("LLM error")

    enhancer = VerifiedQueryEnhancer(
        user=mock_user,
        storage=mock_storage,
        agent_id="agent_123",
        max_retry_attempts=1,
    )

    monkeypatch.setattr(enhancer, "_call_llm", mock_call_llm)

    # Should return original query on failure
    result = await enhancer.enhance_verified_query(
        verified_query=sample_verified_query,
        sdm=sample_sdm,
    )

    assert result == sample_verified_query
    assert result.name == "Driver Race Count"  # Original name


@pytest.mark.asyncio
async def test_enhancer_add_error_feedback_to_prompt(
    mock_user,
    mock_storage,
    mock_llm_response_invalid,
):
    """Test that error feedback is added to prompt correctly using PromptThread."""
    from agent_platform.core.prompts.messages import PromptTextContent, PromptUserMessage
    from agent_platform.server.semantic_data_models.enhancer.prompts import PromptThread
    from agent_platform.server.semantic_data_models.verified_queries.enhancer.enhancer import (
        VerifiedQueryEnhancer,
    )

    enhancer = VerifiedQueryEnhancer(
        user=mock_user,
        storage=mock_storage,
        agent_id="agent_123",
    )

    original_prompt = PromptThread(system_instruction="Test", messages=[])
    validation_errors = "- parameters: Missing required parameter 'count'"

    updated_prompt = enhancer._add_error_feedback_to_prompt(
        prompt=original_prompt,
        response=mock_llm_response_invalid,
        validation_errors=validation_errors,
    )

    # Should have added 2 messages (agent + user feedback) via append_response_and_error
    assert len(updated_prompt.messages) == 2

    # Check that error feedback is in the new user message
    last_message = updated_prompt.messages[-1]
    assert isinstance(last_message, PromptUserMessage)

    assert len(last_message.content) > 0
    first_content = last_message.content[0]
    assert isinstance(first_content, PromptTextContent)
    message_text = first_content.text
    # Error message should contain the validation errors and parameter name
    assert message_text.startswith("The previous enhancement had validation errors")
    assert "- parameters: Missing required parameter 'count'" in message_text
