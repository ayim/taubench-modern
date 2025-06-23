"""Unit tests for streaming error classes."""

import json

import pytest
from starlette.status import WS_1008_POLICY_VIOLATION, WS_1011_INTERNAL_ERROR

from agent_platform.core.errors.base import PlatformWebSocketError
from agent_platform.core.errors.responses import ErrorResponse
from agent_platform.core.errors.streaming import (
    NoPlatformOrModelFoundError,
    StreamingError,
    StreamingKernelError,
)


class TestStreamingError:
    """Tests for the base StreamingError class."""

    def test_inheritance_from_platform_websocket_error(self) -> None:
        """Test that StreamingError inherits from PlatformWebSocketError."""
        error = StreamingError(message="Streaming failed")

        assert isinstance(error, PlatformWebSocketError)
        assert isinstance(error, StreamingError)

    def test_default_initialization(self) -> None:
        """Test StreamingError with default values."""
        error = StreamingError()

        assert error.response.code == "unexpected"
        assert error.response.message == "An unexpected error occurred."
        assert error.close_code == WS_1011_INTERNAL_ERROR
        assert error.reason == "An unexpected error occurred."

    def test_custom_initialization(self) -> None:
        """Test StreamingError with custom values."""
        custom_data = {"stream_id": "stream_123", "operation": "message_processing"}
        error = StreamingError(
            message="Stream processing failed",
            data=custom_data,
            close_code=1003,
            reason="Invalid data",
        )

        assert error.response.message == "Stream processing failed"
        assert error.data == custom_data
        assert error.close_code == 1003
        assert error.reason == "Invalid data"

    def test_websocket_close_context(self) -> None:
        """Test that StreamingError includes WebSocket close context in logs."""
        error = StreamingError(
            message="Connection lost",
            close_code=1006,
            reason="Abnormal closure",
        )

        context = error.to_log_context()

        assert "error" in context
        assert context["websocket_close_code"] == 1006
        assert context["websocket_reason"] == "Abnormal closure"


class TestStreamingKernelError:
    """Tests for StreamingKernelError class."""

    def test_inheritance_from_streaming_error(self) -> None:
        """Test that StreamingKernelError inherits from StreamingError."""
        error = StreamingKernelError(message="Kernel error")

        assert isinstance(error, StreamingError)
        assert isinstance(error, StreamingKernelError)

    def test_default_initialization(self) -> None:
        """Test StreamingKernelError with default values."""
        error = StreamingKernelError()

        assert error.response.code == "unexpected"
        assert error.response.message == "An unexpected error occurred."
        assert error.close_code == WS_1011_INTERNAL_ERROR

    def test_custom_initialization(self) -> None:
        """Test StreamingKernelError with custom values."""
        custom_data = {
            "kernel_id": "kernel_abc123",
            "agent_id": "agent_456",
            "operation": "invoke_architecture",
        }
        error = StreamingKernelError(
            message="Agent architecture invocation failed",
            data=custom_data,
            close_code=1008,
            reason="Policy violation",
        )

        assert error.response.message == "Agent architecture invocation failed"
        assert error.data == custom_data
        assert error.close_code == 1008
        assert error.reason == "Policy violation"

    def test_kernel_context_logging(self) -> None:
        """Test that kernel errors include relevant context for debugging."""
        error = StreamingKernelError(
            message="Model execution timeout",
            data={
                "kernel_id": "kernel_xyz",
                "model_name": "gpt-4",
                "timeout_seconds": 30,
                "partial_response": "Hello, I was processing...",
            },
        )

        context = error.to_log_context()

        assert "error" in context
        assert context["kernel_id"] == "kernel_xyz"
        assert context["model_name"] == "gpt-4"
        assert context["timeout_seconds"] == 30


class TestNoPlatformOrModelFoundError:
    """Tests for NoPlatformOrModelFoundError class."""

    def test_inheritance_from_streaming_kernel_error(self) -> None:
        """Test that NoPlatformOrModelFoundError inherits correctly."""
        error = NoPlatformOrModelFoundError()

        assert isinstance(error, StreamingKernelError)
        assert isinstance(error, NoPlatformOrModelFoundError)

    def test_default_initialization(self) -> None:
        """Test NoPlatformOrModelFoundError with default values."""
        error = NoPlatformOrModelFoundError()

        assert error.response.code == "not_found"
        assert error.response.message == "No platform or model found for the requested parameters."
        assert error.close_code == WS_1008_POLICY_VIOLATION
        assert error.reason == "No platform or model found for the requested parameters."

    def test_custom_initialization(self) -> None:
        """Test NoPlatformOrModelFoundError with custom values."""
        custom_data = {
            "requested_model": "non-existent-model",
            "available_models": ["gpt-3.5-turbo", "gpt-4"],
            "platform": "openai",
        }
        error = NoPlatformOrModelFoundError(
            message="Model 'non-existent-model' not available",
            data=custom_data,
            close_code=1000,
            reason="Model not found",
        )

        assert error.response.message == "Model 'non-existent-model' not available"
        assert error.data == custom_data
        assert error.close_code == 1000
        assert error.reason == "Model not found"

    def test_response_class_is_not_found(self) -> None:
        """Test that NoPlatformOrModelFoundError uses NotFoundErrorResponse."""
        error = NoPlatformOrModelFoundError()

        assert isinstance(error.response, ErrorResponse)
        assert error.response.code == "not_found"

    def test_model_selection_context(self) -> None:
        """Test error context for model selection scenarios."""
        error = NoPlatformOrModelFoundError(
            message="No suitable model found",
            data={
                "requested_capabilities": ["vision", "function_calling"],
                "available_platforms": ["openai", "anthropic"],
                "selection_criteria": {
                    "max_tokens": 4096,
                    "supports_streaming": True,
                },
                "fallback_attempted": False,
            },
        )

        context = error.to_log_context()
        error_dict = context["error"]

        assert error_dict["code"] == "not_found"
        assert context["requested_capabilities"] == ["vision", "function_calling"]
        assert context["available_platforms"] == ["openai", "anthropic"]
        assert "selection_criteria" in context

    def test_platform_discovery_context(self) -> None:
        """Test error context for platform discovery scenarios."""
        error = NoPlatformOrModelFoundError(
            data={
                "platform_config": {
                    "api_key_provided": True,
                    "endpoint_reachable": False,
                    "last_health_check": "2024-01-01T00:00:00Z",
                },
                "discovery_errors": [
                    "Connection timeout to OpenAI API",
                    "Invalid API key for Anthropic",
                ],
            }
        )

        context = error.to_log_context()

        assert "platform_config" in context
        assert "discovery_errors" in context
        assert len(context["discovery_errors"]) == 2


class TestStreamingErrorIntegration:
    """Integration tests for streaming error system."""

    def test_error_hierarchy_consistency(self) -> None:
        """Test that all streaming errors have consistent hierarchy."""
        base_streaming = StreamingError(message="Base streaming error")
        kernel_error = StreamingKernelError(message="Kernel error")
        model_error = NoPlatformOrModelFoundError(message="Model error")

        # Check inheritance chain
        assert isinstance(base_streaming, PlatformWebSocketError)
        assert isinstance(kernel_error, StreamingError)
        assert isinstance(model_error, StreamingKernelError)

        # All should be websocket errors at the base
        assert isinstance(base_streaming, PlatformWebSocketError)
        assert isinstance(kernel_error, PlatformWebSocketError)
        assert isinstance(model_error, PlatformWebSocketError)

    def test_websocket_close_codes_are_appropriate(self) -> None:
        """Test that default close codes make sense for each error type."""
        base_streaming = StreamingError()
        kernel_error = StreamingKernelError()
        model_error = NoPlatformOrModelFoundError()

        # Base streaming error should use internal error
        assert base_streaming.close_code == WS_1011_INTERNAL_ERROR

        # Kernel error should also use internal error by default
        assert kernel_error.close_code == WS_1011_INTERNAL_ERROR

        # Model not found should use policy violation (configuration issue)
        assert model_error.close_code == WS_1008_POLICY_VIOLATION

    def test_all_streaming_errors_serialize_consistently(self) -> None:
        """Test that all streaming errors serialize to JSON properly."""
        errors = [
            StreamingError(
                message="Base error",
                data={"type": "base"},
            ),
            StreamingKernelError(
                message="Kernel error",
                data={"kernel_id": "test", "type": "kernel"},
            ),
            NoPlatformOrModelFoundError(
                message="Model not found",
                data={"model": "test-model", "type": "model"},
            ),
        ]

        for error in errors:
            context = error.to_log_context()

            # Should be JSON serializable
            json_str = json.dumps(context)
            parsed = json.loads(json_str)

            # Should have consistent structure
            assert "error" in parsed
            error_dict = parsed["error"]
            assert "code" in error_dict
            assert "message" in error_dict
            assert "error_id" in error_dict
            assert "websocket_close_code" in parsed
            assert "websocket_reason" in parsed

    def test_exception_catching_patterns(self) -> None:
        """Test common exception catching patterns for streaming errors."""
        # Test catching specific error types
        with pytest.raises(NoPlatformOrModelFoundError):
            raise NoPlatformOrModelFoundError(message="Model error")

        with pytest.raises(StreamingKernelError):
            raise NoPlatformOrModelFoundError(message="Model error")

        with pytest.raises(StreamingError):
            raise StreamingKernelError(message="Kernel error")

        with pytest.raises(PlatformWebSocketError):
            raise StreamingError(message="Streaming error")

    def test_real_world_streaming_scenarios(self) -> None:
        """Test realistic streaming error scenarios."""
        # Scenario 1: Agent architecture invocation fails
        architecture_error = StreamingKernelError(
            message="Agent architecture 'default' failed during message processing",
            data={
                "architecture_name": "default",
                "agent_id": "agent_12345",
                "user_id": "user_67890",
                "message_count": 3,
                "failure_stage": "tool_execution",
                "tool_name": "web_search",
                "partial_output": "I was searching for information about...",
            },
            close_code=1011,
            reason="Internal processing error",
        )

        assert architecture_error.data is not None
        assert "architecture_name" in architecture_error.data
        assert architecture_error.data["failure_stage"] == "tool_execution"

        # Scenario 2: No suitable model found for requirements
        model_error = NoPlatformOrModelFoundError(
            message="No model supports required capabilities",
            data={
                "required_capabilities": ["vision", "function_calling", "long_context"],
                "user_preferences": {"provider": "openai", "model_family": "gpt-4"},
                "available_models": {
                    "openai": ["gpt-3.5-turbo", "gpt-4"],
                    "anthropic": ["claude-3-sonnet"],
                },
                "capability_matrix": {
                    "gpt-4": {"vision": True, "function_calling": True, "long_context": False},
                    "claude-3-sonnet": {
                        "vision": True,
                        "function_calling": False,
                        "long_context": True,
                    },
                },
            },
        )

        assert model_error.response.code == "not_found"
        assert model_error.data is not None
        assert "capability_matrix" in model_error.data

        # Scenario 3: Connection issues during streaming
        connection_error = StreamingError(
            message="WebSocket connection lost during streaming",
            data={
                "connection_duration_seconds": 45.3,
                "bytes_transmitted": 2048,
                "last_ping_timestamp": "2024-01-01T12:00:00Z",
                "reconnection_attempts": 3,
                "client_info": {
                    "user_agent": "AgentPlatform/1.0",
                    "ip_address": "192.168.1.100",
                },
            },
            close_code=1006,
            reason="Abnormal closure",
        )

        assert connection_error.close_code == 1006
        assert connection_error.data is not None
        assert connection_error.data["reconnection_attempts"] == 3

    def test_streaming_error_with_structured_logging_integration(self) -> None:
        """Test that streaming errors work well with structured logging systems."""
        # Simulate a complex streaming error with rich context
        error = StreamingKernelError(
            message="Agent execution timeout with partial completion",
            data={
                "execution_context": {
                    "agent_id": "agent_production_v2_123",
                    "user_id": "user_premium_456",
                    "session_id": "session_789",
                    "architecture": "default",
                    "model_config": {
                        "provider": "openai",
                        "model": "gpt-4",
                        "temperature": 0.7,
                        "max_tokens": 2048,
                    },
                },
                "execution_timeline": [
                    {"stage": "input_validation", "duration_ms": 50, "status": "completed"},
                    {"stage": "model_invocation", "duration_ms": 15000, "status": "timeout"},
                    {"stage": "response_processing", "duration_ms": 0, "status": "skipped"},
                ],
                "partial_results": {
                    "tokens_generated": 1024,
                    "tool_calls_made": 2,
                    "tool_calls_completed": 1,
                    "last_complete_sentence": "I have successfully retrieved the weather "
                    "data for New York.",
                },
                "resource_usage": {
                    "cpu_percent": 85.2,
                    "memory_mb": 512,
                    "api_calls_made": 3,
                    "api_quota_remaining": 997,
                },
            },
        )

        # Test that this complex structure serializes properly
        context = error.to_log_context()
        json_str = json.dumps(context)
        parsed = json.loads(json_str)

        # Verify structure is preserved
        execution_ctx = parsed["execution_context"]
        assert execution_ctx["agent_id"] == "agent_production_v2_123"
        assert execution_ctx["model_config"]["provider"] == "openai"

        timeline = parsed["execution_timeline"]
        assert len(timeline) == 3
        assert timeline[1]["status"] == "timeout"

        partial = parsed["partial_results"]
        assert partial["tokens_generated"] == 1024
        assert partial["tool_calls_completed"] == 1
