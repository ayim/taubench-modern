import re
from collections.abc import AsyncGenerator, Callable, Generator
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
from typing import Any, Literal, Optional, cast

from fastapi import Request, WebSocket
from langsmith import Client
from opentelemetry import context, metrics, trace
from opentelemetry.metrics import Counter, Histogram, MeterProvider
from opentelemetry.trace import (
    Span,
    SpanContext,
    Status,
    StatusCode,
    TraceFlags,
    TracerProvider,
)
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from requests.models import Response

from agent_platform.core.agent.observability_config import ObservabilityConfig
from agent_platform.core.user import User

# Define valid run types for LangSmith
RunType = Literal["chain", "llm", "tool", "retriever", "embedding", "prompt", "parser"]

# W3C Trace Context format: version(2)-trace-id(32)-parent-id(16)-flags(2)
TRACEPARENT_REGEX = re.compile(
    r"^(?P<version>[0-9a-f]{2})-"
    r"(?P<trace_id>[0-9a-f]{32})-"
    r"(?P<parent_id>[0-9a-f]{16})-"
    r"(?P<flags>[0-9a-f]{2})$"
)


@dataclass
class UserContext:
    """User context information."""

    user: User
    profile: dict[str, Any]


class LangSmithContext:
    """LangSmith context information and operations."""

    def __init__(self, config: ObservabilityConfig | None = None):
        """Initialize LangSmith context with optional configuration.

        Args:
            config: Optional observability configuration for LangSmith
        """
        self.client: Client | None = None
        if config and config.type == "langsmith":
            self.client = Client(
                api_url=config.api_url,
                api_key=config.api_key,
            )

    def create_run(
        self,
        name: str,
        run_type: RunType,
        inputs: dict[str, Any],
        user_context: UserContext,
        **kwargs: Any,
    ) -> Any:
        """Create a new run in LangSmith.

        Args:
            name: Name of the run
            run_type: Type of run (chain, llm, tool, etc.)
            inputs: Input values for the run
            user_context: User context for adding user information
            **kwargs: Additional arguments to pass to create_run

        Returns:
            The created run object

        Raises:
            ValueError: If LangSmith client is not initialized
        """
        if not self.client:
            raise ValueError("LangSmith client not initialized")

        run_inputs = inputs.copy()
        run_inputs.update(
            {
                "user": user_context.user.user_id,
                "organization": user_context.user.cr_tenant_id or "unknown",
            }
        )

        return self.client.create_run(
            name=name,
            run_type=run_type,
            inputs=run_inputs,
            **kwargs,
        )

    def end_run(
        self,
        run_id: str,
        outputs: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        """End a LangSmith run.

        Args:
            run_id: ID of the run to end
            outputs: Output values from the run
            error: Error message if the run failed

        Raises:
            ValueError: If LangSmith client is not initialized
        """
        if not self.client:
            raise ValueError("LangSmith client not initialized")

        if error:
            self.client.update_run(
                run_id,
                end_time=None,  # Auto-set to now
                error=error,
            )
        else:
            self.client.update_run(
                run_id,
                end_time=None,  # Auto-set to now
                outputs=outputs or {},
            )

    @asynccontextmanager
    async def trace_llm(
        self,
        name: str,
        inputs: dict[str, Any],
        user_context: UserContext,
        metadata: dict[str, Any] | None = None,
    ) -> AsyncGenerator[Any | None, None]:
        """Context manager to trace LLM operations with LangSmith.

        Args:
            name: Name of the operation
            inputs: Input values for the operation
            user_context: User context for the operation
            metadata: Additional metadata for the trace

        Yields:
            The LangSmith run object if LangSmith is enabled, None otherwise
        """
        run = None
        try:
            if self.client:
                run = self.create_run(
                    name=name,
                    run_type="llm",
                    inputs=inputs,
                    user_context=user_context,
                    metadata=metadata or {},
                )
            yield run
        except Exception as e:
            if run is not None:
                self.end_run(run.id, error=str(e))
            raise
        else:
            if run is not None:
                self.end_run(run.id)

    async def _yield_none(self) -> AsyncGenerator[None, None]:
        """Helper method to yield None in an async context."""
        yield None


@dataclass
class TraceContext:
    """W3C Trace Context information."""

    version: str
    trace_id: str
    parent_id: str
    flags: str

    @classmethod
    def from_header(cls, header_value: str) -> Optional["TraceContext"]:
        """Create TraceContext from traceparent header value.

        Args:
            header_value: The traceparent header value

        Returns:
            TraceContext if valid, None if invalid format
        """
        if not header_value:
            return None

        match = TRACEPARENT_REGEX.match(header_value)
        if not match:
            return None

        return cls(
            version=match.group("version"),
            trace_id=match.group("trace_id"),
            parent_id=match.group("parent_id"),
            flags=match.group("flags"),
        )

    def to_header(self) -> str:
        """Convert to traceparent header value.

        Returns:
            Formatted traceparent header value
        """
        return f"{self.version}-{self.trace_id}-{self.parent_id}-{self.flags}"

    def to_span_context(self) -> SpanContext:
        """Convert to OpenTelemetry SpanContext.

        Returns:
            OpenTelemetry SpanContext
        """
        return SpanContext(
            trace_id=int(self.trace_id, 16),
            span_id=int(self.parent_id, 16),
            is_remote=True,
            trace_flags=TraceFlags(int(self.flags, 16)),
        )


@dataclass
class HttpContext:
    """HTTP context information."""

    request: Request
    response: Response
    _propagator: TraceContextTextMapPropagator = field(init=False)

    def __post_init__(self) -> None:
        """Initialize the propagator after dataclass initialization."""
        self._propagator = TraceContextTextMapPropagator()

    def set_response_status(
        self,
        status_code: int,
        message: str | None = None,
    ) -> None:
        """Set the HTTP response status code and optional message.

        Args:
            status_code: HTTP status code
            message: Optional status message
        """
        self.response.status_code = status_code
        if message:
            self.response.reason = message

    @property
    def trace_context(self) -> TraceContext | None:
        """Get trace context from request headers.

        Returns:
            TraceContext if traceparent header present and valid, None otherwise
        """
        header_value = self.request.headers.get("traceparent")
        return TraceContext.from_header(header_value) if header_value else None

    def inject_trace_context(self, span: Span) -> None:
        """Inject current trace context into response headers.

        Args:
            span: Current span to get trace context from
        """
        # Use the propagator to inject the context into a dict
        headers = {}
        self._propagator.inject(headers, context.get_current())

        # Copy the injected headers to the response
        for key, value in headers.items():
            self.response.headers[key] = value


@dataclass
class AgentServerConfig:
    """Configuration for AgentServerContext."""

    http: HttpContext
    user_context: UserContext
    tracer_provider: TracerProvider
    meter_provider: MeterProvider
    observability_config: ObservabilityConfig | None = None
    version: str | None = None


class AgentServerContext:
    """
    A context class that acts as a wrapper for resources frequently used during the
    execution of a service call.

    This class provides a unified interface for accessing common resources like
    tracing, metrics, and user context during service execution. It implements the
    context manager protocol for automatic resource cleanup.
    """

    def __init__(  # noqa: PLR0913
        self,
        http: HttpContext,
        user_context: UserContext,
        tracer_provider: TracerProvider,
        meter_provider: MeterProvider,
        observability_config: ObservabilityConfig | None = None,
        version: str | None = None,
    ):
        """Initialize the context with necessary resources.

        Args:
            http: HTTP context containing request/response information
            user_context: User context containing authenticated user information
            tracer_provider: OpenTelemetry tracer provider
            meter_provider: OpenTelemetry meter provider
            observability_config: Optional configuration for observability
                (e.g. LangSmith)
            version: Optional version string for instrumentation
        """
        if not all([user_context, http]):
            raise ValueError("All context resources must be provided")

        # Store the HTTP and user context
        self.http = http
        self.user_context = user_context

        # Initialize OpenTelemetry components
        self.tracer_provider = tracer_provider
        self.meter_provider = meter_provider

        # Create tracer and meter
        version_str = version if version is not None else ""
        self.tracer = trace.get_tracer(
            "agent_server",
            instrumenting_library_version=version_str,
            tracer_provider=self.tracer_provider,
        )

        self.meter = metrics.get_meter(
            "agent_server",
            version=version_str,
            meter_provider=self.meter_provider,
        )

        # Create common metrics
        self.request_counter = self.meter.create_counter(
            name="http_requests_total",
            description="Total number of HTTP requests",
            unit="1",
        )

        self.request_duration = self.meter.create_histogram(
            name="http_request_duration_seconds",
            description="HTTP request duration in seconds",
            unit="s",
        )

        # Cache for created metrics
        self._metric_cache: dict[str, Counter | Histogram] = {}

        self._current_span = None

        # Initialize LangSmith context
        self.langsmith = LangSmithContext(observability_config)

    @classmethod
    def from_request(
        cls,
        request: Request | WebSocket,
        user: User,
        profile: dict[str, Any] | None = None,
        observability_config: ObservabilityConfig | None = None,
        version: str | None = None,
    ) -> "AgentServerContext":
        """Create an AgentServerContext from common request inputs.

        This is a convenience method for creating a context from a FastAPI
        request/websocket and authenticated user, which is the most common pattern
        in API routes.

        Args:
            request: FastAPI Request or WebSocket object
            user: Authenticated user
            profile: Optional user profile data
            observability_config: Optional observability configuration
            version: Optional version string for instrumentation

        Returns:
            Initialized AgentServerContext
        """
        # Create HTTP context from request
        response = getattr(request, "_response", None)
        # For WebSocket, we can access the underlying request
        base_request = getattr(request, "_request", request)
        http_context = HttpContext(
            request=cast(Request, base_request),
            response=cast(Response, response) if response else Response(),
        )

        # Create user context
        user_context = UserContext(user=user, profile=profile or {})

        # Get tracer and meter providers
        tracer_provider = trace.get_tracer_provider()
        meter_provider = metrics.get_meter_provider()

        return cls(
            http=http_context,
            user_context=user_context,
            tracer_provider=tracer_provider,
            meter_provider=meter_provider,
            observability_config=observability_config,
            version=version,
        )

    def __enter__(self) -> "AgentServerContext":
        """Enter the context manager."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit the context manager and cleanup resources."""
        if self._current_span:
            self.end_span(self._current_span)

    @contextmanager
    def start_span(
        self,
        name: str,
        attributes: dict[str, Any] | None = None,
    ) -> Generator[Span, None, None]:
        """
        Start a new span with the given name and optional attributes.

        Args:
            name: Name of the span
            attributes: Optional dictionary of span attributes

        Yields:
            The created span object
        """
        with self.tracer.start_as_current_span(name) as span:
            if attributes:
                for key, value in attributes.items():
                    span.set_attribute(key, value)

            # Add common attributes
            span.set_attribute("user", self.user_context.user.user_id)
            span.set_attribute(
                "organization",
                self.user_context.user.cr_tenant_id or "unknown",
            )

            try:
                self._current_span = span
                yield span
            finally:
                self._current_span = None

    def add_span_attributes(self, span: Span, attributes: dict[str, Any]) -> None:
        """
        Add attributes to the given span.

        Args:
            span: The span to add attributes to
            attributes: Dictionary of attribute key-value pairs
        """
        for key, value in attributes.items():
            span.set_attribute(key, value)

    def log_with_context(
        self,
        message: str,
        level: str = "info",
        extra_context: dict[str, Any] | None = None,
    ) -> None:
        """
        Log a message with additional OTEL and custom context.

        Args:
            message: The message to log
            level: Logging level (default: 'info')
            extra_context: Additional context to include in the log
        """
        current_span = trace.get_current_span()
        ctx = {
            "trace_id": current_span.get_span_context().trace_id,
            "span_id": current_span.get_span_context().span_id,
            "user": self.user_context.user.user_id,
            "organization": self.user_context.user.cr_tenant_id or "unknown",
        }
        if extra_context:
            ctx.update(extra_context)

        current_span.add_event(f"{message} {context}")

    def record_metric(
        self,
        name: str,
        value: int | float,
        labels: dict[str, str] | None = None,
    ) -> None:
        """
        Record a custom metric with optional labels.

        Args:
            name: Name of the metric
            value: Value to record
            labels: Optional dictionary of label key-value pairs
        """
        labels = labels or {}
        labels.update(
            {
                "user": self.user_context.user.user_id,
                "organization": self.user_context.user.cr_tenant_id or "unknown",
            },
        )

        # Get or create the metric
        if name not in self._metric_cache:
            self._metric_cache[name] = self.meter.create_histogram(
                name=name,
                description=f"Custom metric: {name}",
                unit="1",
            )

        metric = self._metric_cache[name]
        if isinstance(metric, Counter):
            metric.add(value, labels)
        elif isinstance(metric, Histogram):
            metric.record(value, labels)

    def increment_counter(
        self,
        name: str,
        increment: int = 1,
        labels: dict[str, str] | None = None,
    ) -> None:
        """
        Increment a counter metric with optional labels.

        Args:
            name: Name of the counter
            increment: Amount to increment by (default: 1)
            labels: Optional dictionary of label key-value pairs
        """
        labels = labels or {}
        labels.update(
            {
                "user": self.user_context.user.user_id,
                "organization": self.user_context.user.cr_tenant_id or "unknown",
            },
        )

        # Get or create the counter
        if name not in self._metric_cache:
            self._metric_cache[name] = self.meter.create_counter(
                name=name,
                description=f"Counter metric: {name}",
                unit="1",
            )

        metric = self._metric_cache[name]
        if isinstance(metric, Counter):
            metric.add(increment, labels)
        elif isinstance(metric, Histogram):
            metric.record(increment, labels)

    def get_profile_value(self, key: str, default: Any = None) -> Any:
        """
        Get a profile value.

        Args:
            key: Profile key
            default: Default value if profile key not found

        Returns:
            The profile value or default
        """
        return self.user_context.profile.get(key, default)

    def trace_function(self, func: Callable) -> Callable:
        """
        Decorator to trace the execution of a function.

        This decorator can be used in two ways:
        1. As an instance method decorator:
           >>> @ctx.trace_function
           ... def my_method(self, ...):
           ...     pass

        2. As a function decorator where context is passed as first parameter:
           >>> @ctx.trace_function
           ... def my_function(ctx: AgentServerContext, ...):
           ...     pass

        Args:
            func: The function to trace

        Returns:
            Wrapped function with tracing
        """

        def wrapper(*args, **kwargs):
            # Check if first argument is self or context
            if args and isinstance(args[0], AgentServerContext):
                # Function receives context as first parameter
                context = args[0]
            else:
                # Instance method or standalone function
                context = self

            with context.start_span(func.__name__) as span:
                try:
                    result = func(*args, **kwargs)
                    span.set_status(Status(StatusCode.OK))
                    return result
                except Exception as e:
                    span.set_status(Status(StatusCode.ERROR))
                    span.record_exception(e)
                    span.set_attribute("error.type", type(e).__name__)
                    raise

        return wrapper

    def log_trace(self, message: str) -> None:
        """Log a trace message using the current span."""
        current_span = trace.get_current_span()
        current_span.add_event(message)

    def end_span(self, span):
        """End the given span."""
        span.end()

    @contextmanager
    def trace_llm(
        self,
        name: str,
        inputs: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> Generator[Any, None, None]:
        """Context manager to trace LLM operations with OpenTelemetry.

        Args:
            name: Name of the operation
            inputs: Input values for the operation
            metadata: Additional metadata for the trace

        Yields:
            None, as this only handles OpenTelemetry tracing
        """
        with self.start_span(name) as span:
            if metadata:
                self.add_span_attributes(span, metadata)

            try:
                yield None
                span.set_status(Status(StatusCode.OK))
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR))
                span.record_exception(e)
                raise

    # Additional methods to interact with the resources
    # If you find yourself repeating the same code/patterns relating to context,
    # consider adding a helper method here.
