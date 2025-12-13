import json
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi import Request, WebSocket
from opentelemetry.metrics import Counter, Histogram, MeterProvider
from opentelemetry.trace import Span, TracerProvider
from requests import Response

from agent_platform.core.agent.observability_config import ObservabilityConfig
from agent_platform.core.context import (
    AgentServerContext,
    HttpContext,
    LangSmithContext,
    UserContext,
)
from agent_platform.core.user import User


@pytest.fixture
def mock_user() -> User:
    """Create a mock user for testing."""
    return User(
        user_id="test_user_id",
        sub="tenant:test_tenant:user:test_user",
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def mock_request() -> Request:
    """Create a mock request for testing."""
    return MagicMock(spec=Request)


@pytest.fixture
def mock_response() -> Response:
    """Create a mock response for testing."""
    return MagicMock(spec=Response)


@pytest.fixture
def mock_websocket(mock_request: Request, mock_response: Response) -> WebSocket:
    """Create a mock websocket for testing."""
    mock_ws = MagicMock(spec=WebSocket)
    mock_ws._request = mock_request
    mock_ws._response = mock_response
    return mock_ws


@pytest.fixture
def mock_tracer_provider() -> TracerProvider:
    """Create a mock tracer provider for testing."""
    provider = MagicMock(spec=TracerProvider)
    provider.get_tracer.return_value = MagicMock()
    provider.get_tracer.return_value.start_span.return_value = MagicMock(spec=Span)
    return provider


@pytest.fixture
def mock_meter_provider() -> MeterProvider:
    """Create a mock meter provider for testing."""
    provider = MagicMock(spec=MeterProvider)
    provider.get_meter.return_value = MagicMock()
    provider.get_meter.return_value.create_counter.return_value = MagicMock(
        spec=Counter,
    )
    provider.get_meter.return_value.create_histogram.return_value = MagicMock(
        spec=Histogram,
    )
    return provider


class TestHttpContext:
    """Tests for HttpContext class."""

    def test_init(self, mock_request: Request, mock_response: Response) -> None:
        """Test HttpContext initialization."""
        context = HttpContext(request=mock_request, response=mock_response)
        assert context.request == mock_request
        assert context.response == mock_response

    def test_set_response_status(
        self,
        mock_request: Request,
        mock_response: Response,
    ) -> None:
        """Test setting response status."""
        context = HttpContext(request=mock_request, response=mock_response)
        context.set_response_status(200, "OK")
        assert mock_response.status_code == 200
        assert mock_response.reason == "OK"


class TestUserContext:
    """Tests for UserContext class."""

    def test_init(self, mock_user: User) -> None:
        """Test UserContext initialization."""
        profile = {"key": "value"}
        context = UserContext(user=mock_user, profile=profile)
        assert context.user == mock_user
        assert context.profile == profile


class TestLangSmithContext:
    """Tests for LangSmithContext class."""

    @pytest.fixture
    def mock_server_context(self) -> MagicMock:
        """Create a mock server context for testing."""
        mock_context = MagicMock()
        mock_span = MagicMock()
        mock_context_manager = MagicMock()
        mock_context_manager.__enter__ = MagicMock(return_value=mock_span)
        mock_context_manager.__exit__ = MagicMock(return_value=None)
        mock_context.start_span.return_value = mock_context_manager
        return mock_context

    def test_init_without_config(self, mock_server_context: MagicMock) -> None:
        """Test LangSmithContext initialization without config."""
        context = LangSmithContext(mock_server_context)
        assert context.config is None
        assert context.server_context == mock_server_context

    def test_init_with_config(self, mock_server_context: MagicMock) -> None:
        """Test LangSmithContext initialization with config."""
        # Create a config with langsmith settings
        config = ObservabilityConfig(
            type="langsmith",
            api_url="http://test",
            api_key="test_key",
            settings={"project_name": "test_project"},
        )

        # Create the context
        context = LangSmithContext(mock_server_context, config)

        # Verify the config was stored
        assert context.config == config
        assert context.server_context == mock_server_context

    def test_init_requires_server_context(self) -> None:
        """Test that LangSmithContext requires a server_context."""
        with pytest.raises(TypeError, match="missing 1 required positional argument"):
            LangSmithContext()  # type: ignore

    def test_format_tool_call_basic(self, mock_server_context: MagicMock) -> None:
        """Test basic tool call formatting."""
        context = LangSmithContext(mock_server_context)

        tool_call = {
            "id": "call_123",
            "type": "function",
            "function": {
                "name": "test_function",
                "arguments": '{"param1": "value1", "param2": 42}',
            },
        }

        result = context._format_tool_call(tool_call)

        # Parse the result to verify structure

        parsed_result = json.loads(result)

        assert parsed_result["id"] == "call_123"
        assert parsed_result["type"] == "function"
        assert parsed_result["function"]["name"] == "test_function"
        assert parsed_result["function"]["arguments"] == {"param1": "value1", "param2": 42}

    def test_format_tool_call_with_object_arguments(self, mock_server_context: MagicMock) -> None:
        """Test tool call formatting when arguments are already an object."""
        context = LangSmithContext(mock_server_context)

        tool_call = {
            "id": "call_123",
            "type": "function",
            "function": {
                "name": "another_function",
                "arguments": {"param1": "value1", "param2": 42},
            },
        }

        result = context._format_tool_call(tool_call)

        parsed_result = json.loads(result)

        assert parsed_result["id"] == "call_123"
        assert parsed_result["type"] == "function"
        assert parsed_result["function"]["name"] == "another_function"
        assert parsed_result["function"]["arguments"] == {"param1": "value1", "param2": 42}

    def test_format_tool_call_without_function(self, mock_server_context: MagicMock) -> None:
        """Test tool call formatting when function data is missing."""
        context = LangSmithContext(mock_server_context)

        tool_call = {"id": "call_123", "type": "function"}

        result = context._format_tool_call(tool_call)

        parsed_result = json.loads(result)

        assert parsed_result["id"] == "call_123"
        assert parsed_result["type"] == "function"
        assert "function" not in parsed_result

    def test_format_tool_call_without_arguments(self, mock_server_context: MagicMock) -> None:
        """Test tool call formatting when arguments are missing."""
        context = LangSmithContext(mock_server_context)

        tool_call = {"id": "call_123", "type": "function", "function": {"name": "no_args_function"}}

        result = context._format_tool_call(tool_call)

        parsed_result = json.loads(result)

        assert parsed_result["id"] == "call_123"
        assert parsed_result["type"] == "function"
        assert parsed_result["function"]["name"] == "no_args_function"
        assert "arguments" not in parsed_result["function"]

    def test_format_tool_call_with_malformed_json(self, mock_server_context: MagicMock) -> None:
        """Test tool call formatting with malformed JSON arguments."""
        context = LangSmithContext(mock_server_context)

        tool_call = {
            "id": "call_123",
            "type": "function",
            "function": {
                "name": "bad_function",
                "arguments": '{"param1": value1, "param2": 42}',  # Invalid JSON
            },
        }
        result = context._format_tool_call(tool_call)

        parsed_result = json.loads(result)

        assert parsed_result["id"] == "call_123"
        assert parsed_result["type"] == "function"
        assert parsed_result["function"]["name"] == "bad_function"
        assert parsed_result["function"]["arguments"] == '{"param1": value1, "param2": 42}'

    def test_format_tool_call_missing_optional_fields(self, mock_server_context: MagicMock) -> None:
        """Test tool call formatting when optional fields are missing."""
        context = LangSmithContext(mock_server_context)

        tool_call = {"function": {"name": "minimal_function", "arguments": "{}"}}

        result = context._format_tool_call(tool_call)

        parsed_result = json.loads(result)

        assert parsed_result["id"] is None
        assert parsed_result["type"] is None
        assert parsed_result["function"]["name"] == "minimal_function"
        assert parsed_result["function"]["arguments"] == {}

    @pytest.mark.asyncio
    async def test_trace_llm_calls_server_context_start_span(self, mock_server_context: MagicMock) -> None:
        """Test that LangSmithContext.trace_llm() calls server_context.start_span()."""
        context = LangSmithContext(mock_server_context)

        user_context = UserContext(
            user=User(
                user_id="test_user",
                sub="test_sub",
                created_at=datetime.now(UTC),
            ),
            profile={},
        )

        metadata = {"trace_name": "test_trace_name", "provider": "test_provider"}

        async with context.trace_llm(
            name="test_operation",
            inputs={"messages": [{"role": "user", "content": "test"}]},
            user_context=user_context,
            metadata=metadata,
        ) as span_data:
            assert span_data is not None
            assert "span" in span_data

        # Verify server_context.start_span was called with correct attributes
        mock_server_context.start_span.assert_called_once_with(
            "test_operation",
            attributes={
                "langsmith.span.kind": "llm",
                "langsmith.trace.name": "test_trace_name",
            },
        )

    @pytest.mark.asyncio
    async def test_trace_llm_without_langsmith_config(self, mock_server_context: MagicMock) -> None:
        """Test trace_llm context manager when no LangSmith config is provided."""
        context = LangSmithContext(mock_server_context)  # No config provided

        user_context = UserContext(
            user=User(
                user_id="test_user",
                sub="test_sub",
                created_at=datetime.now(UTC),
            ),
            profile={},
        )

        async with context.trace_llm(
            name="test_trace",
            inputs={"prompt": "test prompt"},
            user_context=user_context,
        ) as result:
            # Should still yield span data for OpenTelemetry tracing, even without LangSmith
            assert result is not None
            assert "span" in result
            assert result["span"] is not None

        mock_server_context.start_span.assert_called_once()

    @pytest.mark.asyncio
    async def test_trace_llm_with_metadata(self, mock_server_context: MagicMock) -> None:
        """Test trace_llm context manager with metadata."""
        context = LangSmithContext(mock_server_context)

        user_context = UserContext(
            user=User(
                user_id="test_user",
                sub="test_sub",
                created_at=datetime.now(UTC),
            ),
            profile={},
        )

        inputs = {"messages": [{"role": "user", "content": "test message"}]}
        metadata = {"provider": "test_provider", "model": "test_model"}

        # Mock the span to verify attributes are set
        mock_span = MagicMock()
        mock_server_context.start_span.return_value.__enter__.return_value = mock_span

        async with context.trace_llm(
            name="test_trace",
            inputs=inputs,
            user_context=user_context,
            metadata=metadata,
        ) as span_data:
            # Add test output
            if span_data:
                span_data["output"] = [{"role": "assistant", "content": "test response"}]

        # Verify span attributes were set
        mock_span.set_attribute.assert_any_call("langsmith.span.kind", "llm")
        mock_span.set_attribute.assert_any_call("gen_ai.system", "test_provider")
        mock_span.set_attribute.assert_any_call("gen_ai.request.model", "test_model")

    @pytest.mark.asyncio
    async def test_trace_llm_with_error(self, mock_server_context: MagicMock) -> None:
        """Test trace_llm context manager with an error."""
        context = LangSmithContext(mock_server_context)

        user_context = UserContext(
            user=User(
                user_id="test_user",
                sub="test_sub",
                created_at=datetime.now(UTC),
            ),
            profile={},
        )

        # Mock the span to verify error handling
        mock_span = MagicMock()
        mock_server_context.start_span.return_value.__enter__.return_value = mock_span

        # Test with an exception
        with pytest.raises(ValueError, match="Test error"):
            async with context.trace_llm(
                name="test_trace",
                inputs={},
                user_context=user_context,
            ):
                raise ValueError("Test error")

        # Verify error handling
        mock_span.set_status.assert_called()
        mock_span.record_exception.assert_called_once()
        mock_span.set_attribute.assert_any_call("error", "Test error")


class TestAgentServerContext:
    """Tests for AgentServerContext class."""

    @pytest.fixture
    def http_context(
        self,
        mock_request: Request,
        mock_response: Response,
    ) -> HttpContext:
        """Create a mock HTTP context."""
        return HttpContext(request=mock_request, response=mock_response)

    @pytest.fixture
    def user_context(self, mock_user: User) -> UserContext:
        """Create a mock user context."""
        return UserContext(user=mock_user, profile={})

    def test_init(
        self,
        http_context: HttpContext,
        user_context: UserContext,
        mock_tracer_provider: TracerProvider,
        mock_meter_provider: MeterProvider,
    ) -> None:
        """Test AgentServerContext initialization."""
        context = AgentServerContext(
            http=http_context,
            user_context=user_context,
            tracer_provider=mock_tracer_provider,
            meter_provider=mock_meter_provider,
        )
        assert context.http == http_context
        assert context.user_context == user_context
        assert context.tracer_provider == mock_tracer_provider
        assert context.meter_provider == mock_meter_provider
        assert context.langsmith is not None

    def test_init_missing_required(
        self,
        http_context: HttpContext,
        user_context: UserContext,
        mock_tracer_provider: TracerProvider,
        mock_meter_provider: MeterProvider,
    ) -> None:
        """Test initialization fails with missing required arguments."""
        with pytest.raises(ValueError, match="All context resources must be provided"):
            AgentServerContext(
                http=None,  # type: ignore
                user_context=user_context,
                tracer_provider=mock_tracer_provider,
                meter_provider=mock_meter_provider,
            )

    def test_from_request_http(
        self,
        mock_request: Request,
        mock_user: User,
        mock_tracer_provider: TracerProvider,
        mock_meter_provider: MeterProvider,
    ) -> None:
        """Test creating context from HTTP request."""
        with patch("agent_platform.core.context.trace.get_tracer_provider") as mock_get_tracer:
            with patch("agent_platform.core.context.metrics.get_meter_provider") as mock_get_meter:
                mock_get_tracer.return_value = mock_tracer_provider
                mock_get_meter.return_value = mock_meter_provider

                context = AgentServerContext.from_request(
                    request=mock_request,
                    user=mock_user,
                )
                assert isinstance(context, AgentServerContext)
                assert context.user_context.user == mock_user

    def test_from_request_websocket(
        self,
        mock_websocket: WebSocket,
        mock_user: User,
        mock_tracer_provider: TracerProvider,
        mock_meter_provider: MeterProvider,
    ) -> None:
        """Test creating context from WebSocket."""
        with patch(
            "agent_platform.core.context.trace.get_tracer_provider",
        ) as mock_get_tracer:
            with patch(
                "agent_platform.core.context.metrics.get_meter_provider",
            ) as mock_get_meter:
                mock_get_tracer.return_value = mock_tracer_provider
                mock_get_meter.return_value = mock_meter_provider

                context = AgentServerContext.from_request(
                    request=mock_websocket,
                    user=mock_user,
                )
                assert isinstance(context, AgentServerContext)
                assert context.user_context.user == mock_user

    @pytest.mark.asyncio
    async def test_start_span(
        self,
        http_context: HttpContext,
        user_context: UserContext,
        mock_tracer_provider: TracerProvider,
        mock_meter_provider: MeterProvider,
    ) -> None:
        """Test starting a span."""
        context = AgentServerContext(
            http=http_context,
            user_context=user_context,
            tracer_provider=mock_tracer_provider,
            meter_provider=mock_meter_provider,
        )

        with context.start_span("test_span") as span:
            assert span is not None
            assert context._current_span == span

        assert context._current_span is None

    def test_add_span_attributes(
        self,
        http_context: HttpContext,
        user_context: UserContext,
        mock_tracer_provider: TracerProvider,
        mock_meter_provider: MeterProvider,
    ) -> None:
        """Test adding span attributes."""
        context = AgentServerContext(
            http=http_context,
            user_context=user_context,
            tracer_provider=mock_tracer_provider,
            meter_provider=mock_meter_provider,
        )

        mock_span = MagicMock(spec=Span)
        context.add_span_attributes(mock_span, {"key": "value"})
        mock_span.set_attribute.assert_called_once_with("key", "value")

    def test_record_metric(
        self,
        http_context: HttpContext,
        user_context: UserContext,
        mock_tracer_provider: TracerProvider,
        mock_meter_provider: MeterProvider,
    ) -> None:
        """Test recording a metric."""
        context = AgentServerContext(
            http=http_context,
            user_context=user_context,
            tracer_provider=mock_tracer_provider,
            meter_provider=mock_meter_provider,
        )

        context.record_metric("test_metric", 1.0)
        assert "test_metric" in context._metric_cache

    def test_increment_counter(
        self,
        http_context: HttpContext,
        user_context: UserContext,
        mock_tracer_provider: TracerProvider,
        mock_meter_provider: MeterProvider,
    ) -> None:
        """Test incrementing a counter."""
        context = AgentServerContext(
            http=http_context,
            user_context=user_context,
            tracer_provider=mock_tracer_provider,
            meter_provider=mock_meter_provider,
        )

        context.increment_counter("test_counter")
        assert "test_counter" in context._metric_cache

    def test_get_profile_value(
        self,
        http_context: HttpContext,
        user_context: UserContext,
        mock_tracer_provider: TracerProvider,
        mock_meter_provider: MeterProvider,
    ) -> None:
        """Test getting a profile value."""
        context = AgentServerContext(
            http=http_context,
            user_context=user_context,
            tracer_provider=mock_tracer_provider,
            meter_provider=mock_meter_provider,
        )

        assert context.get_profile_value("nonexistent", "default") == "default"
        context.user_context.profile["test_key"] = "test_value"
        assert context.get_profile_value("test_key") == "test_value"
