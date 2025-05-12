from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi import Request, WebSocket
from opentelemetry.metrics import Counter, Histogram, MeterProvider
from opentelemetry.sdk.trace import TracerProvider as SdkTracerProvider
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

    def test_init_without_config(self) -> None:
        """Test LangSmithContext initialization without config."""
        context = LangSmithContext()
        assert context.tracer is None
        assert context.langsmith_exporter is None

    def test_init_with_config(self) -> None:
        """Test LangSmithContext initialization with config."""
        # Create a config with langsmith settings
        config = ObservabilityConfig(
            type="langsmith",
            api_url="http://test",
            api_key="test_key",
        )

        with (
            patch("agent_platform.core.context.OTLPSpanExporter") as mock_exporter,
            patch(
                "agent_platform.core.context.trace.get_tracer_provider"
            ) as mock_get_provider,
            patch("agent_platform.core.context.trace.get_tracer") as mock_get_tracer,
            patch("agent_platform.core.context.BatchSpanProcessor") as mock_processor,
        ):
            # Set up the mocks
            mock_provider = MagicMock(spec=SdkTracerProvider)
            mock_get_provider.return_value = mock_provider
            mock_tracer = MagicMock()
            mock_get_tracer.return_value = mock_tracer

            # Create the context
            context = LangSmithContext(config)

            # Verify the exporter was created correctly
            mock_exporter.assert_called_once_with(
                endpoint="http://test/otel/v1/traces",
                headers={"x-api-key": "test_key", "Langsmith-Project": "default"},
            )

            # Verify tracer was initialized
            mock_get_tracer.assert_called_once_with("langsmith")
            assert context.tracer is mock_tracer

            # Verify span processor was added
            mock_processor.assert_called_once()
            mock_provider.add_span_processor.assert_called_once()

    @pytest.mark.asyncio
    async def test_trace_llm_without_tracer(self) -> None:
        """Test trace_llm context manager when tracer is None."""
        context = LangSmithContext()  # No config, so tracer is None

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
            assert result is None

    @pytest.mark.asyncio
    async def test_trace_llm_with_tracer(self) -> None:
        """Test trace_llm context manager with a tracer."""
        context = LangSmithContext()

        # Manually create and set a tracer and mock span
        mock_tracer = MagicMock()
        mock_span = MagicMock()

        # Create the context manager properly
        with patch("agent_platform.core.context.trace.get_current_span"):
            # Set up using the mock context manager
            context_mgr = MagicMock()
            context_mgr.__enter__.return_value = mock_span
            context_mgr.__exit__.return_value = None
            mock_tracer.start_as_current_span.return_value = context_mgr

            # Set the tracer
            context.tracer = mock_tracer

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

            async with context.trace_llm(
                name="test_trace",
                inputs=inputs,
                user_context=user_context,
                metadata=metadata,
            ) as span_data:
                # Verify the span was created
                mock_tracer.start_as_current_span.assert_called_once_with("test_trace")

                # Verify important attributes were set on the span
                mock_span.set_attribute.assert_any_call("langsmith.span.kind", "llm")

                # Add test output
                if span_data:
                    span_data["output"] = {
                        "role": "assistant",
                        "content": "test response",
                    }

            # Verify span status was set
            mock_span.set_status.assert_called()

    @pytest.mark.asyncio
    async def test_trace_llm_with_error(self) -> None:
        """Test trace_llm context manager with an error."""
        context = LangSmithContext()

        # Manually set up tracer and span
        mock_tracer = MagicMock()
        mock_span = MagicMock()

        # Set up the context manager
        context_mgr = MagicMock()
        context_mgr.__enter__.return_value = mock_span
        context_mgr.__exit__.return_value = None
        mock_tracer.start_as_current_span.return_value = context_mgr

        # Set the tracer
        context.tracer = mock_tracer

        user_context = UserContext(
            user=User(
                user_id="test_user",
                sub="test_sub",
                created_at=datetime.now(UTC),
            ),
            profile={},
        )

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
        with patch(
            "agent_platform.core.context.trace.get_tracer_provider"
        ) as mock_get_tracer:
            with patch(
                "agent_platform.core.context.metrics.get_meter_provider"
            ) as mock_get_meter:
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
