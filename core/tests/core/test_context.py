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

    def test_init_without_config(self) -> None:
        """Test LangSmithContext initialization without config."""
        context = LangSmithContext()
        assert context.client is None

    def test_init_with_config(self) -> None:
        """Test LangSmithContext initialization with config."""
        config = ObservabilityConfig(
            type="langsmith",
            api_url="http://test",
            api_key="test_key",
        )
        context = LangSmithContext(config)
        assert context.client is not None
        assert context.client.api_url == "http://test"
        assert context.client.api_key == "test_key"

    def test_create_run_with_client(self, mock_user: User) -> None:
        """Test creating run with client."""
        config = ObservabilityConfig(
            type="langsmith",
            api_url="http://test",
            api_key="test_key",
        )
        context = LangSmithContext(config)

        # Mock the client itself instead of just the method
        mock_client = MagicMock()
        mock_client.create_run.return_value = {"run_id": "test_run"}
        context.client = mock_client
        user_context = UserContext(user=mock_user, profile={})

        run = context.create_run(
            name="test",
            run_type="chain",
            inputs={},
            user_context=user_context,
        )
        assert run == {"run_id": "test_run"}

    def test_end_run_with_client(self) -> None:
        """Test ending run with client."""
        config = ObservabilityConfig(
            type="langsmith",
            api_url="http://test",
            api_key="test_key",
        )
        context = LangSmithContext(config)

        # Mock the client itself instead of just the method
        mock_client = MagicMock()
        mock_client.update_run.return_value = {
            "run_id": "test_run",
            "status": "completed",
        }
        context.client = mock_client

        context.end_run(
            run_id="test_run_id",
            outputs={"test": "value"},
        )

    @pytest.mark.asyncio
    async def test_trace_llm_with_client(self, mock_user: User) -> None:
        """Test tracing LLM operations with client."""
        config = ObservabilityConfig(
            type="langsmith",
            api_url="http://test",
            api_key="test_key",
        )
        context = LangSmithContext(config)

        # Create a mock run object with an id attribute
        mock_run = MagicMock()
        mock_run.id = "test_run"

        # Mock the client itself instead of just the methods
        mock_client = MagicMock()
        mock_client.create_run.return_value = mock_run
        mock_client.update_run.return_value = mock_run
        context.client = mock_client

        user_context = UserContext(user=mock_user, profile={})

        async with context.trace_llm(
            name="test",
            inputs={},
            user_context=user_context,
        ) as run:
            assert run is not None
            assert run.id == "test_run"

    @pytest.mark.asyncio
    async def test_trace_llm_without_client(self, mock_user: User) -> None:
        """Test tracing LLM operations without client."""
        context = LangSmithContext()
        user_context = UserContext(user=mock_user, profile={})

        async with context.trace_llm(
            name="test",
            inputs={},
            user_context=user_context,
        ) as run:
            assert run is None

    @pytest.mark.asyncio
    async def test_trace_llm_with_error(self, mock_user: User) -> None:
        """Test tracing LLM operations with error."""
        config = ObservabilityConfig(
            type="langsmith",
            api_url="http://test",
            api_key="test_key",
        )
        context = LangSmithContext(config)

        # Create a mock run object with an id attribute
        mock_run = MagicMock()
        mock_run.id = "test_run"

        # Mock the client itself instead of just the methods
        mock_client = MagicMock()
        mock_client.create_run.return_value = mock_run
        mock_client.update_run.return_value = mock_run
        context.client = mock_client

        user_context = UserContext(user=mock_user, profile={})

        with pytest.raises(ValueError, match="Test error"):
            async with context.trace_llm(
                name="test",
                inputs={},
                user_context=user_context,
            ):
                raise ValueError("Test error")


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
