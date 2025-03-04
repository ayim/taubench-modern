import json
from dataclasses import FrozenInstanceError
from typing import Any

import pytest

from agent_server_types_v2.responses import (
    ResponseMessage,
    ResponseTextContent,
    TokenUsage,
)


class TestTokenUsage:
    """Tests for the TokenUsage class."""

    def test_init_default(self) -> None:
        """Test that TokenUsage initializes with default values."""
        usage = TokenUsage()
        assert usage.input_tokens == 0
        assert usage.output_tokens == 0
        assert usage.total_tokens == 0

    def test_init_with_values(self) -> None:
        """Test that TokenUsage initializes with provided values."""
        usage = TokenUsage(input_tokens=10, output_tokens=20, total_tokens=30)
        assert usage.input_tokens == 10
        assert usage.output_tokens == 20
        assert usage.total_tokens == 30

    def test_immutability(self) -> None:
        """Test that TokenUsage is immutable."""
        usage = TokenUsage(input_tokens=10, output_tokens=20, total_tokens=30)
        with pytest.raises(FrozenInstanceError):
            # This should raise an exception because TokenUsage is frozen
            usage.input_tokens = 100  # type: ignore


class TestResponseMessage:
    """Tests for the ResponseMessage class."""

    @pytest.fixture
    def sample_text_content(self) -> ResponseTextContent:
        """Create a sample text content for testing."""
        return ResponseTextContent(text="Hello, world!")

    @pytest.fixture
    def sample_response_dict(
        self,
        sample_text_content: ResponseTextContent,
    ) -> dict[str, Any]:
        """Create a sample response dictionary for testing."""
        return {
            "content": [sample_text_content.model_dump()],
            "role": "agent",
            "usage": {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30},
            "stop_reason": "end_turn",
            "metrics": {"latency_ms": 150},
            "metadata": {"model": "test-model"},
            "additional_response_fields": {"custom_field": "value"},
        }

    def test_init(self, sample_text_content: ResponseTextContent) -> None:
        """Test that ResponseMessage initializes correctly."""
        response = ResponseMessage(
            content=[sample_text_content],
            role="agent",
        )
        assert response.content == [sample_text_content]
        assert response.role == "agent"
        assert response.raw_response is None
        assert response.stop_reason is None
        assert isinstance(response.usage, TokenUsage)
        assert response.metrics == {}
        assert response.metadata == {}
        assert response.additional_response_fields == {}

    def test_init_with_all_fields(
        self,
        sample_text_content: ResponseTextContent,
    ) -> None:
        """Test that ResponseMessage initializes with all fields."""
        usage = TokenUsage(input_tokens=10, output_tokens=20, total_tokens=30)
        response = ResponseMessage(
            content=[sample_text_content],
            role="agent",
            raw_response={"some": "data"},
            stop_reason="end_turn",
            usage=usage,
            metrics={"latency_ms": 150},
            metadata={"model": "test-model"},
            additional_response_fields={"custom_field": "value"},
        )
        assert response.content == [sample_text_content]
        assert response.role == "agent"
        assert response.raw_response == {"some": "data"}
        assert response.stop_reason == "end_turn"
        assert response.usage == usage
        assert response.metrics == {"latency_ms": 150}
        assert response.metadata == {"model": "test-model"}
        assert response.additional_response_fields == {"custom_field": "value"}

    def test_model_validate(self, sample_response_dict: dict[str, Any]) -> None:
        """Test that model_validate creates a ResponseMessage from a dictionary."""
        response = ResponseMessage.model_validate(sample_response_dict)
        assert isinstance(response, ResponseMessage)
        assert len(response.content) == 1
        assert isinstance(response.content[0], ResponseTextContent)
        assert response.content[0].text == "Hello, world!"
        assert response.role == "agent"
        assert response.stop_reason == "end_turn"
        assert isinstance(response.usage, TokenUsage)
        assert response.usage.input_tokens == 10
        assert response.usage.output_tokens == 20
        assert response.usage.total_tokens == 30
        assert response.metrics == {"latency_ms": 150}
        assert response.metadata == {"model": "test-model"}
        assert response.additional_response_fields == {"custom_field": "value"}

    def test_model_validate_json(self, sample_response_dict: dict[str, Any]) -> None:
        """Test that model_validate_json creates a ResponseMessage
        from a JSON string."""
        json_str = json.dumps(sample_response_dict)
        response = ResponseMessage.model_validate_json(json_str)
        assert isinstance(response, ResponseMessage)
        assert len(response.content) == 1
        assert isinstance(response.content[0], ResponseTextContent)
        assert response.content[0].text == "Hello, world!"

    def test_model_dump(self, sample_text_content: ResponseTextContent) -> None:
        """Test that model_dump converts a ResponseMessage to a dictionary."""
        response = ResponseMessage(
            content=[sample_text_content],
            role="agent",
            stop_reason="end_turn",
        )
        data = response.model_dump()
        assert isinstance(data, dict)
        assert "content" in data
        assert "role" in data
        assert data["role"] == "agent"
        assert data["stop_reason"] == "end_turn"

    def test_model_dump_exclude_none(
        self,
        sample_text_content: ResponseTextContent,
    ) -> None:
        """Test that model_dump with exclude_none excludes None values."""
        response = ResponseMessage(
            content=[sample_text_content],
            role="agent",
        )
        data = response.model_dump(exclude_none=True)
        assert "stop_reason" not in data
        assert "raw_response" not in data

    def test_model_dump_json(self, sample_text_content: ResponseTextContent) -> None:
        """Test that model_dump_json converts a ResponseMessage to a JSON string."""
        response = ResponseMessage(
            content=[sample_text_content],
            role="agent",
        )
        json_str = response.model_dump_json()
        assert isinstance(json_str, str)
        data = json.loads(json_str)
        assert "content" in data
        assert "role" in data

    def test_immutability(self, sample_text_content: ResponseTextContent) -> None:
        """Test that ResponseMessage is immutable."""
        response = ResponseMessage(
            content=[sample_text_content],
            role="agent",
        )
        with pytest.raises(FrozenInstanceError):
            # This should raise an exception because ResponseMessage is frozen
            response.role = "user"  # type: ignore
