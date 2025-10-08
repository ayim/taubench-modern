import json
import logging
import re
from collections.abc import AsyncGenerator, Callable, Generator
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
from typing import Any, Literal, Optional, cast

from fastapi import Request, WebSocket
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

# Import for getting the LangSmith processor
from agent_platform.core.conditional_langsmith_processor import ConditionalLangSmithProcessor
from agent_platform.core.user import User

logger = logging.getLogger(__name__)
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
    """LangSmith context information and operations using OpenTelemetry."""

    def __init__(
        self,
        server_context: "AgentServerContext",
        config: ObservabilityConfig | None = None,
    ):
        """Initialize LangSmith context with server context and optional configuration.

        Args:
            server_context: Server context for span creation (required)
            config: Optional observability configuration for LangSmith
        """
        self.config = config
        self.server_context = server_context

        # When new threads are created, an AgentServerContext object
        # is initialized with no observability config.
        # This object is used to update counters, and no LangSmith
        # operations are performed.
        # In this case, the LangSmithContext is initialized with
        # no config and this debug statement will be printed.
        logger.debug(
            f"LangSmithContext initialized with config: {config.type if config else 'None'}"
        )

    def format_response_for_langsmith(self, response) -> list[dict]:  # noqa: C901, PLR0912
        """Formats a response for LangSmith.

        Args:
            response: The response to format

        Returns:
            A list of messages formatted for LangSmith showing content and role
        """
        messages = []
        current_text = ""

        # Handle response with content attribute (ResponseMessage)
        if hasattr(response, "content") and response.content:
            for content_item in response.content:
                # Text content gets accumulated
                if content_item.kind == "text":
                    if content_item.text:
                        current_text += content_item.text
                # Tool calls get their own message
                elif content_item.kind == "tool_use":
                    # First flush any accumulated text
                    if current_text:
                        messages.append({"content": current_text, "role": "assistant"})
                        current_text = ""

                    # Format the tool call
                    tool_call = {
                        "id": content_item.tool_call_id,
                        "type": "function",
                        "function": {
                            "name": content_item.tool_name,
                            "arguments": content_item.tool_input_raw or "{}",
                        },
                    }

                    # Add the tool message
                    messages.append(
                        {
                            "content": self._format_tool_call(tool_call),
                            "role": "tool",
                        }
                    )
                # Reasoning content gets its own message
                elif content_item.kind == "reasoning":
                    # Flush any accumulated text first
                    if current_text:
                        messages.append({"content": current_text, "role": "assistant"})
                        current_text = ""
                    # If the reasoning attribute is present, use it
                    if content_item.reasoning:
                        reasoning_text = content_item.reasoning
                        messages.append({"content": reasoning_text, "role": "reasoning"})
                    else:
                        # Try to populate both summary and content
                        reasoning_message = ""
                        if content_item.summary:
                            reasoning_message += "\n\nSummary:\n" + "\n".join(content_item.summary)
                        if content_item.content:
                            reasoning_message += "\n\nContent:\n" + "\n".join(content_item.content)
                        # It's possible that the reasoning object has no information whatsoever
                        # (empty reasoning object),
                        # so we won't send a message if there's no information.
                        if reasoning_message:
                            messages.append({"content": reasoning_message, "role": "reasoning"})

            # Flush any remaining text
            if current_text:
                messages.append({"content": current_text, "role": "assistant"})

        # Handle simple string response
        elif isinstance(response, str):
            messages.append({"content": response, "role": "assistant"})
        # Handle any other response type
        else:
            messages.append({"content": str(response), "role": "assistant"})

        # If no messages were created, return a default message
        if not messages:
            messages.append({"content": "", "role": "assistant"})
        return messages

    @asynccontextmanager
    async def trace_llm(  # noqa: C901, PLR0912, PLR0915
        self,
        name: str,
        inputs: dict[str, Any],
        user_context: UserContext,
        metadata: dict[str, Any] | None = None,
    ) -> AsyncGenerator[Any | None, None]:
        """Context manager to trace LLM operations with LangSmith using OpenTelemetry.

        Args:
            name: Name of the operation
            inputs: Input values for the operation
            user_context: User context for the operation
            metadata: Additional metadata for the trace

        Yields:
            A dictionary to store span data, or None if tracing is disabled
        """
        # Create a dictionary to store span data that we'll need after yield
        span_data = {}

        logger.debug(f"Starting LLM trace '{name}'")
        span_manager = self.server_context.start_span(
            name,
            attributes={
                "langsmith.span.kind": "llm",
                "langsmith.trace.name": metadata.get("trace_name") if metadata else None,
            },
        )

        with span_manager as span:
            # Set LangSmith span kind attribute
            span.set_attribute("langsmith.span.kind", "llm")

            # Set trace name if provided in metadata
            if metadata and "trace_name" in metadata:
                span.set_attribute("langsmith.trace.name", metadata["trace_name"])

            # Add user information as metadata
            span.set_attribute(
                "langsmith.metadata.user_id",
                user_context.user.cr_user_id
                if user_context.user.cr_user_id
                # Fallback to internal sub if cr_user_id is not set
                else user_context.user.sub,
            )

            # Process inputs - for LLM we need to check if it's a chat format
            if "messages" in inputs:
                # Handle chat format messages
                messages = inputs["messages"]

                # First, set the raw messages value on the span for LangSmith
                span.set_attribute("input.messages", str(messages))

                # If it's a JSON string, try to parse it
                if isinstance(messages, str):
                    try:
                        parsed_messages = json.loads(messages)
                        if isinstance(parsed_messages, list):
                            messages = parsed_messages
                    except json.JSONDecodeError:
                        pass

                # Process individual messages
                if isinstance(messages, list):
                    # Filter out empty user messages
                    filtered_messages = []
                    for msg in messages:
                        if isinstance(msg, dict):
                            # Skip empty user messages
                            if msg.get("role") == "user" and not msg.get("content"):
                                continue
                            filtered_messages.append(msg)
                        else:
                            filtered_messages.append(msg)

                    # Process the filtered messages and expand tool calls
                    attr_index = 0
                    for message in filtered_messages:
                        if isinstance(message, dict):
                            # Set role attribute if available
                            if "role" in message:
                                span.set_attribute(
                                    f"gen_ai.prompt.{attr_index}.role", str(message["role"])
                                )

                            # Set content attribute if available
                            if "content" in message:
                                content_value = message["content"]
                                span.set_attribute(
                                    f"gen_ai.prompt.{attr_index}.content", str(content_value)
                                )

                            # Handle tool calls - create separate messages for each tool call
                            if "tool_calls" in message and message["role"] == "assistant":
                                # Parse tool calls and create separate messages
                                tool_calls_str = message["tool_calls"]
                                if isinstance(tool_calls_str, str):
                                    tool_calls = json.loads(tool_calls_str)
                                else:
                                    tool_calls = tool_calls_str

                                # Create a separate message for each individual tool call
                                if isinstance(tool_calls, list) and tool_calls:
                                    for tool_call in tool_calls:
                                        # Increment message index for each tool call message
                                        attr_index += 1

                                        # Set role as tool for each tool call message
                                        span.set_attribute(
                                            f"gen_ai.prompt.{attr_index}.role", "tool"
                                        )

                                        # Format the tool call using the extracted function
                                        tool_call_content = self._format_tool_call(tool_call)
                                        span.set_attribute(
                                            f"gen_ai.prompt.{attr_index}.content",
                                            tool_call_content,
                                        )

                            # Increment message index for the next message
                            attr_index += 1

            # Add system information if available
            if metadata and "provider" in metadata:
                span.set_attribute("gen_ai.system", metadata["provider"])

            # Add model information if available
            if metadata and "model" in metadata:
                span.set_attribute("gen_ai.request.model", metadata["model"])

            # Add additional metadata
            if metadata:
                for key, value in metadata.items():
                    if key not in ["trace_name", "provider", "model"]:
                        span.set_attribute(f"langsmith.metadata.{key}", str(value))

            try:
                span_data["span"] = span
                yield span_data
                span.set_status(Status(StatusCode.OK))

                # Add output information if it was added to span_data
                if "output" in span_data:
                    output = span_data["output"]
                    # We know that output is a list of messages
                    for idx, message in enumerate(output):
                        if isinstance(message, dict):
                            if "content" in message:
                                span.set_attribute(
                                    f"gen_ai.completion.{idx}.content", str(message["content"])
                                )
                            if "role" in message:
                                span.set_attribute(f"gen_ai.completion.{idx}.role", message["role"])

                # Add usage information if available
                if "usage" in span_data:
                    usage = span_data["usage"]
                    if isinstance(usage, dict):
                        if "input_tokens" in usage:
                            span.set_attribute("gen_ai.usage.input_tokens", usage["input_tokens"])
                        if "output_tokens" in usage:
                            span.set_attribute("gen_ai.usage.output_tokens", usage["output_tokens"])
                        if "total_tokens" in usage:
                            span.set_attribute("gen_ai.usage.total_tokens", usage["total_tokens"])

            except Exception as e:
                span.set_status(Status(StatusCode.ERROR))
                span.record_exception(e)
                span.set_attribute("error", str(e))
                raise

    async def _yield_none(self) -> AsyncGenerator[None, None]:
        """Helper method to yield None in an async context."""
        yield None

    def _format_tool_call(self, tool_call: dict[str, Any]) -> str:
        """Format a tool call for LangSmith tracing.

        Args:
            tool_call: The tool call dictionary in OpenAI format

        Returns:
            JSON string representation of the formatted tool call.
            If arguments contain invalid JSON, they are kept as-is and logged.
        """
        formatted_tool_call = {
            "id": tool_call.get("id"),
            "type": tool_call.get("type"),
        }

        # Handle function details with parsed arguments
        if "function" in tool_call:
            function_data = tool_call["function"]
            formatted_function = {"name": function_data.get("name")}

            # Parse arguments from JSON string to object
            if "arguments" in function_data:
                args_str = function_data["arguments"]
                if isinstance(args_str, str):
                    try:
                        formatted_function["arguments"] = json.loads(args_str)
                    except json.JSONDecodeError as e:
                        logger.warning(
                            "Failed to parse tool call arguments as JSON for tool %s: %s. "
                            "Keeping arguments as string.",
                            function_data.get("name", "unknown"),
                            str(e),
                        )
                        formatted_function["arguments"] = args_str
                else:
                    formatted_function["arguments"] = args_str

            formatted_tool_call["function"] = formatted_function

        return json.dumps(formatted_tool_call)


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
        agent_id: str | None = None,
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
            agent_id: Optional agent ID for this context
        """
        if not all([user_context, http]):
            raise ValueError("All context resources must be provided")

        # Store the HTTP and user context
        self.http = http
        self.user_context = user_context
        self.agent_id = agent_id

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
        self.langsmith = LangSmithContext(self, observability_config)

        # Register LangSmith configuration if provided and we have an agent_id
        if not agent_id:
            logger.debug("No agent_id provided, skipping LangSmith registration")
            return

        if not (observability_config and observability_config.api_key):
            logger.debug(f"No LangSmith config provided for agent: {agent_id}")
            return

        # Since we already set up the processor in server/telemetry.py
        # and added the processor to the global tracer provider,
        # we can just get the instance here and add the config.
        processor = ConditionalLangSmithProcessor.get_instance()
        success = processor.add_or_update_config(agent_id, observability_config)
        msg = (
            f"Registered LangSmith config for agent: {agent_id}"
            if success
            else f"Failed to register LangSmith config for agent: {agent_id}"
        )
        logger.info(msg) if success else logger.warning(msg)

    @classmethod
    def from_request(  # noqa: PLR0913
        cls,
        request: Request | WebSocket,
        user: User,
        profile: dict[str, Any] | None = None,
        observability_config: ObservabilityConfig | None = None,
        version: str | None = None,
        agent_id: str | None = None,
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
            agent_id: Optional agent ID for this context

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
            agent_id=agent_id,
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
        # Prepare all attributes before span creation
        all_attributes = {}

        # Add provided attributes first
        if attributes:
            all_attributes.update(attributes)

        # Automatically add agent_id if available
        if self.agent_id:
            all_attributes["agent_id"] = self.agent_id

        # Add common attributes
        all_attributes["user_id"] = self.user_context.user.cr_user_id or self.user_context.user.sub

        # Create span with all attributes at once
        with self.tracer.start_as_current_span(name, attributes=all_attributes) as span:
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
        ctx: dict[str, Any] = {
            "trace_id": current_span.get_span_context().trace_id,
            "span_id": current_span.get_span_context().span_id,
        }
        ctx["user_id"] = self.user_context.user.cr_user_id or self.user_context.user.sub

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
        labels.update({"user_id": self.user_context.user.cr_user_id or self.user_context.user.sub})

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
                "user_id": self.user_context.user.cr_user_id
                if self.user_context.user.cr_user_id
                else self.user_context.user.sub,
            }
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
        # Use regular span tracing
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
