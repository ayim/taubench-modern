"""Unit tests for error response classes."""

import json
import uuid

from agent_platform.core.errors.responses import (
    ErrorCode,
    ErrorResponse,
)


class TestErrorResponse:
    """Tests for the base ErrorResponse class."""

    def test_default_initialization(self) -> None:
        """Test ErrorResponse with default values."""
        response = ErrorResponse(ErrorCode.UNEXPECTED)

        assert response.code == "unexpected"
        assert response.message == "An unexpected error occurred."
        assert isinstance(response.error_id, str | uuid.UUID)

    def test_custom_initialization(self) -> None:
        """Test ErrorResponse with custom values."""
        response = ErrorResponse(
            ErrorCode.UNEXPECTED,
            message_override="Custom error message",
        )

        assert response.code == "unexpected"
        assert response.message == "Custom error message"
        assert isinstance(response.error_id, str | uuid.UUID)

    def test_error_id_is_unique(self) -> None:
        """Test that each ErrorResponse gets a unique error_id."""
        response1 = ErrorResponse(ErrorCode.UNEXPECTED)
        response2 = ErrorResponse(ErrorCode.UNEXPECTED)

        assert response1.error_id != response2.error_id

    def test_model_dump_python_mode(self) -> None:
        """Test model_dump in python mode."""
        response = ErrorResponse(
            ErrorCode.UNEXPECTED,
            message_override="Test message",
        )

        result = response.model_dump(mode="python")

        assert result["code"] == "unexpected"
        assert result["message"] == "Test message"
        assert "error_id" in result
        assert isinstance(result["error_id"], str | uuid.UUID)
        # Verify data is NOT included in response
        assert "data" not in result

    def test_model_dump_json_mode(self) -> None:
        """Test model_dump in json mode."""
        response = ErrorResponse(
            ErrorCode.UNEXPECTED,
            message_override="Test message",
        )

        result = response.model_dump(mode="json")

        assert result["code"] == "unexpected"
        assert result["message"] == "Test message"
        assert "error_id" in result
        # In json mode, error_id should be serializable
        assert isinstance(result["error_id"], str)
        # Verify data is NOT included in response
        assert "data" not in result

    def test_model_dump_json_string(self) -> None:
        """Test model_dump_json returns valid JSON string."""
        response = ErrorResponse(
            ErrorCode.UNEXPECTED,
            message_override="Test message",
        )

        json_str = response.model_dump_json()

        # Should be valid JSON
        parsed = json.loads(json_str)
        assert parsed["code"] == "unexpected"
        assert parsed["message"] == "Test message"
        assert "error_id" in parsed
        # Verify data is NOT included in response
        assert "data" not in parsed

    def test_no_data_in_serialization(self) -> None:
        """Test that data is never included in serialization to prevent leaking sensitive info."""
        response = ErrorResponse(ErrorCode.UNEXPECTED, message_override="Test message")

        # Test python mode
        python_result = response.model_dump(mode="python")
        assert "data" not in python_result

        # Test json mode
        json_result = response.model_dump(mode="json")
        assert "data" not in json_result

        # Test JSON string
        json_str = response.model_dump_json()
        parsed = json.loads(json_str)
        assert "data" not in parsed


class TestBadRequestErrorResponse:
    """Tests for BadRequestErrorResponse."""

    def test_default_initialization(self) -> None:
        """Test BadRequestErrorResponse with default values."""
        response = ErrorResponse(ErrorCode.BAD_REQUEST)

        assert response.code == "bad_request"
        assert response.message == "The request was invalid. Please check the request and try again."

    def test_custom_message(self) -> None:
        """Test BadRequestErrorResponse with custom message."""
        response = ErrorResponse(ErrorCode.BAD_REQUEST, message_override="Custom bad request message")

        assert response.code == "bad_request"
        assert response.message == "Custom bad request message"

    def test_serialization_excludes_data(self) -> None:
        """Test BadRequestErrorResponse serialization excludes data."""
        response = ErrorResponse(ErrorCode.BAD_REQUEST, message_override="Custom message")

        result = response.model_dump(mode="json")
        assert "data" not in result


class TestUnprocessableEntityErrorResponse:
    """Tests for UnprocessableEntityErrorResponse."""

    def test_default_initialization(self) -> None:
        """Test UnprocessableEntityErrorResponse with default values."""
        response = ErrorResponse(ErrorCode.UNPROCESSABLE_ENTITY)

        assert response.code == "unprocessable_entity"
        assert response.message == "Request validation failed. Please check the request and try again."

    def test_custom_message(self) -> None:
        """Test UnprocessableEntityErrorResponse with custom message."""
        response = ErrorResponse(ErrorCode.UNPROCESSABLE_ENTITY, message_override="Validation failed for field X")

        assert response.code == "unprocessable_entity"
        assert response.message == "Validation failed for field X"


class TestUnauthorizedErrorResponse:
    """Tests for UnauthorizedErrorResponse."""

    def test_default_initialization(self) -> None:
        """Test UnauthorizedErrorResponse with default values."""
        response = ErrorResponse(ErrorCode.UNAUTHORIZED)

        assert response.code == "unauthorized"
        assert response.message == "You are not authorized to access this resource."

    def test_custom_message(self) -> None:
        """Test UnauthorizedErrorResponse with custom message."""
        response = ErrorResponse(ErrorCode.UNAUTHORIZED, message_override="Invalid API key")

        assert response.code == "unauthorized"
        assert response.message == "Invalid API key"


class TestNotFoundErrorResponse:
    """Tests for NotFoundErrorResponse."""

    def test_default_initialization(self) -> None:
        """Test NotFoundErrorResponse with default values."""
        response = ErrorResponse(ErrorCode.NOT_FOUND)

        assert response.code == "not_found"
        assert response.message == "The requested resource was not found."

    def test_custom_message(self) -> None:
        """Test NotFoundErrorResponse with custom message."""
        response = ErrorResponse(ErrorCode.NOT_FOUND, message_override="User not found")

        assert response.code == "not_found"
        assert response.message == "User not found"


class TestForbiddenErrorResponse:
    """Tests for ForbiddenErrorResponse."""

    def test_default_initialization(self) -> None:
        """Test ForbiddenErrorResponse with default values."""
        response = ErrorResponse(ErrorCode.FORBIDDEN)

        assert response.code == "forbidden"
        assert response.message == "You do not have permission to access this resource."

    def test_custom_message(self) -> None:
        """Test ForbiddenErrorResponse with custom message."""
        response = ErrorResponse(ErrorCode.FORBIDDEN, message_override="Admin access required")

        assert response.code == "forbidden"
        assert response.message == "Admin access required"


class TestConflictErrorResponse:
    """Tests for ConflictErrorResponse."""

    def test_default_initialization(self) -> None:
        """Test ConflictErrorResponse with default values."""
        response = ErrorResponse(ErrorCode.CONFLICT)

        assert response.code == "conflict"
        assert response.message == "The request conflicts with an existing resource."

    def test_custom_message(self) -> None:
        """Test ConflictErrorResponse with custom message."""
        response = ErrorResponse(ErrorCode.CONFLICT, message_override="Username already exists")

        assert response.code == "conflict"
        assert response.message == "Username already exists"


class TestMethodNotAllowedErrorResponse:
    """Tests for MethodNotAllowedErrorResponse."""

    def test_default_initialization(self) -> None:
        """Test MethodNotAllowedErrorResponse with default values."""
        response = ErrorResponse(ErrorCode.METHOD_NOT_ALLOWED)

        assert response.code == "method_not_allowed"
        assert response.message == "The requested method is not allowed for this resource."

    def test_custom_message(self) -> None:
        """Test MethodNotAllowedErrorResponse with custom message."""
        response = ErrorResponse(ErrorCode.METHOD_NOT_ALLOWED, message_override="POST not allowed on this endpoint")

        assert response.code == "method_not_allowed"
        assert response.message == "POST not allowed on this endpoint"


class TestTooManyRequestsErrorResponse:
    """Tests for TooManyRequestsErrorResponse."""

    def test_default_initialization(self) -> None:
        """Test TooManyRequestsErrorResponse with default values."""
        response = ErrorResponse(ErrorCode.TOO_MANY_REQUESTS)

        assert response.code == "too_many_requests"
        assert response.message == "Too many requests. Please try again later."

    def test_custom_message(self) -> None:
        """Test TooManyRequestsErrorResponse with custom message."""
        response = ErrorResponse(
            ErrorCode.TOO_MANY_REQUESTS,
            message_override="Rate limit exceeded: 100 requests per minute",
        )

        assert response.code == "too_many_requests"
        assert response.message == "Rate limit exceeded: 100 requests per minute"


class TestAllErrorResponseTypes:
    """Integration tests for all error response types."""

    def test_all_error_codes_are_unique(self) -> None:
        """Test that all error response types have unique codes."""
        error_responses = [
            ErrorResponse(ErrorCode.UNEXPECTED),
            ErrorResponse(ErrorCode.BAD_REQUEST),
            ErrorResponse(ErrorCode.UNPROCESSABLE_ENTITY),
            ErrorResponse(ErrorCode.UNAUTHORIZED),
            ErrorResponse(ErrorCode.NOT_FOUND),
            ErrorResponse(ErrorCode.FORBIDDEN),
            ErrorResponse(ErrorCode.CONFLICT),
            ErrorResponse(ErrorCode.METHOD_NOT_ALLOWED),
            ErrorResponse(ErrorCode.TOO_MANY_REQUESTS),
        ]

        codes = [response.code for response in error_responses]
        assert len(codes) == len(set(codes)), "Error codes should be unique"

    def test_all_responses_serialize_consistently(self) -> None:
        """Test that all error response types serialize consistently without data fields."""
        error_codes = [
            ErrorCode.UNEXPECTED,
            ErrorCode.BAD_REQUEST,
            ErrorCode.UNPROCESSABLE_ENTITY,
            ErrorCode.UNAUTHORIZED,
            ErrorCode.NOT_FOUND,
            ErrorCode.FORBIDDEN,
            ErrorCode.CONFLICT,
            ErrorCode.METHOD_NOT_ALLOWED,
            ErrorCode.TOO_MANY_REQUESTS,
        ]

        for error_code in error_codes:
            response = ErrorResponse(error_code, message_override="Test message")

            # Test python mode
            python_dict = response.model_dump(mode="python")
            assert "code" in python_dict
            assert "message" in python_dict
            assert "error_id" in python_dict
            # Verify data is NOT included in any response
            assert "data" not in python_dict

            # Test json mode
            json_dict = response.model_dump(mode="json")
            assert "code" in json_dict
            assert "message" in json_dict
            assert "error_id" in json_dict
            # Verify data is NOT included in any response
            assert "data" not in json_dict

            # Test json string
            json_str = response.model_dump_json()
            parsed = json.loads(json_str)
            assert "code" in parsed
            assert "message" in parsed
            assert "error_id" in parsed
            # Verify data is NOT included in any response
            assert "data" not in parsed
