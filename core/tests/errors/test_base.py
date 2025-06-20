"""Unit tests for base platform error classes."""

import json
import uuid

from starlette.status import HTTP_500_INTERNAL_SERVER_ERROR, WS_1011_INTERNAL_ERROR

from agent_platform.core.errors.base import (
    PlatformError,
    PlatformHTTPError,
    PlatformWebSocketError,
)
from agent_platform.core.errors.responses import ErrorCode


class TestPlatformError:
    """Tests for the base PlatformError class."""

    def test_none_message_behavior(self) -> None:
        """Test that explicit None message still uses the default message."""
        error = PlatformError(message=None)

        # When None is passed explicitly, ErrorResponse still uses the default message
        assert error.response.message == "An unexpected error occurred."
        # str() should handle the message gracefully
        assert str(error) == "An unexpected error occurred."

    def test_default_behavior_is_none(self) -> None:
        """Test that default behavior uses the default message from ErrorCode."""
        error = PlatformError()

        # Uses default message from ErrorCode.UNEXPECTED
        assert error.response.code == "unexpected"
        assert error.response.message == "An unexpected error occurred."
        # Data is on the error object, not the response
        assert error.data == {}
        assert isinstance(error.response.error_id, str | uuid.UUID)

    def test_str_representation(self) -> None:
        """Test string representation of error."""
        error = PlatformError(message="Test error message")

        assert str(error) == "Test error message"

    def test_repr_representation(self) -> None:
        """Test repr representation of error."""
        error = PlatformError(message="Test error message")

        repr_str = repr(error)
        assert "PlatformError" in repr_str
        assert "code='unexpected'" in repr_str
        assert "message='Test error message'" in repr_str
        assert "error_id=" in repr_str
        # Should not contain the actual data to avoid potential issues with large objects
        assert str(error.data) not in repr_str

    def test_to_log_context(self) -> None:
        """Test structured logging context generation."""
        data = {"operation": "file_save", "user_id": "user123"}
        error = PlatformError(
            message="Operation failed",
            data=data,
        )

        context = error.to_log_context()

        # Should have error nested under 'error' key
        assert "error" in context
        error_dict = context["error"]
        assert error_dict["code"] == "unexpected"
        assert error_dict["message"] == "Operation failed"
        assert "error_id" in error_dict

        # Data should be merged at top level for easy access
        assert context["operation"] == "file_save"
        assert context["user_id"] == "user123"


class TestPlatformHTTPError:
    """Tests for PlatformHTTPError class."""

    def test_default_behavior(self) -> None:
        """Test default HTTP error behavior."""
        error = PlatformHTTPError(ErrorCode.UNEXPECTED)

        assert error.status_code == HTTP_500_INTERNAL_SERVER_ERROR
        assert error.headers is None
        # Data is on the error object, not the response
        assert error.data == {}

    def test_to_log_context_includes_http_fields(self) -> None:
        """Test that HTTP error context includes HTTP-specific fields."""
        error = PlatformHTTPError(
            ErrorCode.NOT_FOUND,
            message="HTTP error",
            status_code=404,
            headers={"X-Request-ID": "abc123"},
        )

        context = error.to_log_context()

        # HTTP fields should be at top level
        assert context["status_code"] == 404
        assert context["headers"] == {"X-Request-ID": "abc123"}

    def test_to_log_context_without_headers(self) -> None:
        """Test HTTP error context when no headers are provided."""
        error = PlatformHTTPError(ErrorCode.UNEXPECTED, message="HTTP error", status_code=500)

        context = error.to_log_context()

        # Should have status_code but not headers
        assert context["status_code"] == 500
        assert "headers" not in context


class TestPlatformWebSocketError:
    """Tests for PlatformWebSocketError class."""

    def test_default_behavior(self) -> None:
        """Test default WebSocket error behavior."""
        error = PlatformWebSocketError(ErrorCode.UNEXPECTED)

        assert error.close_code == WS_1011_INTERNAL_ERROR
        assert error.reason == "An unexpected error occurred."
        # Data is on the error object, not the response
        assert error.data == {}

    def test_to_log_context_includes_websocket_fields(self) -> None:
        """Test that WebSocket error context includes WebSocket-specific fields."""
        error = PlatformWebSocketError(
            ErrorCode.BAD_REQUEST,
            message="WebSocket error",
            close_code=1008,
            reason="Policy violation",
        )

        context = error.to_log_context()

        # WebSocket fields should be at top level with websocket_ prefix
        assert context["websocket_close_code"] == 1008
        assert context["websocket_reason"] == "Policy violation"

    def test_websocket_compatibility(self) -> None:
        """Test that WebSocket errors work with standard WebSocket patterns."""
        error = PlatformWebSocketError(
            ErrorCode.BAD_REQUEST,
            message="Invalid data",
            close_code=1003,
            reason="Unsupported data",
        )

        # These properties should be available for WebSocket compatibility
        assert error.close_code == 1003
        assert error.reason == "Unsupported data"


class TestErrorSystemIntegration:
    """Integration tests for the error system."""

    def test_structured_logging_compatibility(self) -> None:
        """Test that errors produce structured logs compatible with logging systems."""
        error = PlatformError(
            message="Database connection failed",
            data={
                "host": "db.example.com",
                "port": 5432,
                "database": "production",
                "retry_count": 3,
            },
        )

        context = error.to_log_context()

        # Should be JSON serializable
        json_str = json.dumps(context)
        parsed = json.loads(json_str)

        # Should have consistent structure
        assert "error" in parsed
        assert parsed["host"] == "db.example.com"
        assert parsed["retry_count"] == 3

    def test_error_wrapping_patterns(self) -> None:
        """Test common error wrapping patterns."""
        try:
            raise ValueError("Original error")
        except ValueError as e:
            wrapped_error = PlatformError(
                message="Wrapped error occurred",
                data={
                    "original_error": str(e),
                    "error_type": type(e).__name__,
                },
            )

        # Should preserve context while wrapping
        assert wrapped_error.data["original_error"] == "Original error"
        assert wrapped_error.data["error_type"] == "ValueError"

    def test_sensitive_data_handling(self) -> None:
        """Test that PlatformError can safely handle sensitive data."""
        # PlatformError is designed for internal use, so it should handle sensitive data
        sensitive_data = {
            "password": "secret123",
            "api_key": "sk-1234567890",
            "internal_config": {"db_password": "dbsecret"},
        }

        error = PlatformError(
            message="Internal configuration error",
            data=sensitive_data,
        )

        # Data should be preserved for internal logging (stored on error object)
        assert error.data == sensitive_data

        # But PlatformHTTPError should be more careful since it may be exposed
        http_error = PlatformHTTPError(
            ErrorCode.UNEXPECTED,
            message="External API error",
            data=sensitive_data,
            status_code=500,
        )

        # Data is on the error object, not exposed in response
        assert http_error.data is not None
        # Data should not contain sensitive info in a real scenario, but
        # the system allows it since the response itself doesn't include data
        assert "password" not in http_error.response.model_dump(mode="json")
        assert "api_key" not in http_error.response.model_dump(mode="json")
