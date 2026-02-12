"""Helper functions for OTEL orchestrator."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import structlog
from opentelemetry.sdk.trace.export import BatchSpanProcessor

if TYPE_CHECKING:
    from opentelemetry.trace import Span

    from agent_platform.core.integrations.integration_scope import IntegrationScope
    from agent_platform.core.integrations.observability.integration import ObservabilityIntegration
    from agent_platform.core.thread import Thread

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def compute_config_hash(integration: "ObservabilityIntegration") -> str:
    """Compute MD5 hash of integration config for deduplication.

    Include: provider_kind, provider_settings (url, api_key, tokens, etc.)

    Args:
        integration: ObservabilityIntegration to hash

    Returns:
        32-character MD5 hex digest
    """
    import hashlib
    import json

    hashable_data = {
        "kind": integration.settings.provider_kind,
        "settings": integration.settings.provider_settings.model_dump(redact_secret=False),
    }
    serialized = json.dumps(hashable_data, sort_keys=True)
    return hashlib.md5(serialized.encode()).hexdigest()


def build_routing_map(
    agent_ids: list[str],
    integration_id_to_processor: dict[str, BatchSpanProcessor],
    integration_scopes: dict[str, list["IntegrationScope"]],
) -> tuple[dict[str, set[BatchSpanProcessor]], set[BatchSpanProcessor]]:
    """Build complete agent_id → processors routing map.

    For each agent, combines global processors + agent-specific processors.
    This pre-computes the full set.

    Args:
        agent_ids: List of all agent IDs in the system
        integration_id_to_processor: Map of integration ID to processor
        integration_scopes: Map of integration ID to list of scopes

    Returns:
        Tuple of:
        - Map of agent_id → set of processors (global + agent-specific)
        - Set of global processors (for fallback when agent not in map)
    """
    # First, collect global processors and agent-specific processors separately
    global_processors: set[BatchSpanProcessor] = set()
    agent_specific: dict[str, set[BatchSpanProcessor]] = {}

    for integration_id, processor in integration_id_to_processor.items():
        for scope in integration_scopes[integration_id]:
            if scope.scope == "global":
                global_processors.add(processor)
            elif scope.scope == "agent" and scope.agent_id:
                if scope.agent_id not in agent_specific:
                    agent_specific[scope.agent_id] = set()
                agent_specific[scope.agent_id].add(processor)

    # Build complete map: each agent gets global + their specific processors
    new_map: dict[str, set[BatchSpanProcessor]] = {}
    for agent_id in agent_ids:
        # Makes a shallow copy of the global processors set
        new_map[agent_id] = global_processors.copy()
        if agent_id in agent_specific:
            new_map[agent_id] |= agent_specific[agent_id]

    return new_map, global_processors


def shutdown_processors(processors: list[BatchSpanProcessor]) -> None:
    """Shutdown processors, logging any errors."""
    for processor in processors:
        try:
            processor.shutdown()
        except Exception as e:
            logger.error("Error shutting down processor", error=str(e))


def extract_agent_id(span) -> str | None:
    """Extract agent_id from span attributes."""
    if hasattr(span, "attributes") and span.attributes:
        agent_id = span.attributes.get("agent_id")
        if agent_id is not None:
            return str(agent_id)
    return None


def create_thread_trace_context(
    thread_name: str,
    thread_id: str,
    agent_id: str,
    user_id: str,
) -> tuple[str, str]:
    """Create and export a thread-level span at thread creation time.

    This creates an actual recording span that gets exported to the observability
    backend immediately. The returned trace_id and span_id should be persisted
    on the Thread so that future runs can use them as parent context via
    NonRecordingSpan.

    Args:
        thread_name: Display name for the span.
        thread_id: The thread's unique identifier.
        agent_id: The agent's unique identifier.
        user_id: The user's unique identifier.

    Returns:
        Tuple of (trace_id, span_id) as 32-char and 16-char hex strings.
    """
    from opentelemetry import trace

    tracer = trace.get_tracer("sema4ai.agent_server")

    with tracer.start_as_current_span(
        thread_name,
        attributes={
            "thread_id": thread_id,
            "agent_id": agent_id,
            "user_id": user_id,
            "span_type": "thread_creation",
        },
    ) as span:
        ctx = span.get_span_context()
        trace_id = format(ctx.trace_id, "032x")
        span_id = format(ctx.span_id, "016x")

        logger.debug(
            "Created thread trace context",
            thread_id=thread_id,
            trace_id=trace_id,
            span_id=span_id,
        )

        return trace_id, span_id


def _restore_span_context(
    parent_trace_id: str,
    parent_span_id: str,
) -> "Span":
    """Restore a span context from stored hex IDs.

    Args:
        parent_trace_id: 32-character hex trace ID.
        parent_span_id: 16-character hex span ID.

    Returns:
        A NonRecordingSpan with the restored context.

    Raises:
        ValueError: If the hex strings are invalid.
    """
    from opentelemetry.trace import NonRecordingSpan, SpanContext, TraceFlags

    try:
        trace_id = int(parent_trace_id, 16)
        span_id = int(parent_span_id, 16)
    except ValueError as e:
        raise ValueError(
            f"Invalid trace context: parent_trace_id={parent_trace_id!r}, parent_span_id={parent_span_id!r}"
        ) from e

    parent_span_context = SpanContext(
        trace_id=trace_id,
        span_id=span_id,
        is_remote=False,
        trace_flags=TraceFlags(0x01),
    )
    return NonRecordingSpan(parent_span_context)


@asynccontextmanager
async def thread_span_context(
    *,
    thread_state: "Thread",
) -> AsyncIterator["Span"]:
    """
    Context manager for thread trace grouping.

    Restores the thread's trace context using a NonRecordingSpan so that all
    child spans created within this context inherit the thread's trace_id.

    The thread's trace context must be set before calling this function.
    For new threads, use `create_thread_trace_context()` at creation time.
    For legacy threads, the caller should check and backfill before calling.

    If trace context is missing, a new span is created as a fallback
    so callers always receive a valid Span.

    Args:
        thread_state: The thread state containing parent_trace_id and parent_span_id.
            These must be set before calling (at thread creation or handled by run handler).

    Yields:
        A Span with the thread's trace context for propagation.

    Example:
        async with thread_span_context(thread_state=thread) as thread_span:
            # Child spans created here will inherit the thread's trace context
            with tracer.start_span("run_operation"):
                ...
    """
    from opentelemetry import trace

    logger.debug(
        "Using thread trace context",
        thread_id=thread_state.thread_id,
        parent_trace_id=thread_state.parent_trace_id,
        parent_span_id=thread_state.parent_span_id,
    )

    # If trace context is missing, create a new span as fallback.
    # We want this span to be pushed to the backend
    # instead of creating a NonRecordingSpan.
    if thread_state.parent_trace_id is None or thread_state.parent_span_id is None:
        logger.warning(
            "Thread missing trace context, creating new span",
            thread_id=thread_state.thread_id,
        )
        tracer = trace.get_tracer("sema4ai.agent_server")
        with tracer.start_as_current_span(
            thread_state.name,
            attributes={
                "thread_id": thread_state.thread_id,
                "agent_id": thread_state.agent_id,
                "user_id": thread_state.user_id,
                "span_type": "thread_fallback",
            },
        ) as span:
            yield span
        return

    parent_span = _restore_span_context(
        thread_state.parent_trace_id,
        thread_state.parent_span_id,
    )

    with trace.use_span(parent_span):
        yield parent_span
