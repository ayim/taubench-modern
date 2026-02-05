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
    user_id: str,
) -> AsyncIterator["Span"]:
    """
    Context manager for thread trace grouping.

    Creates or restores a parent span context for thread-level trace grouping.
    All spans created within this context will inherit the thread's trace context,
    allowing multiple runs in the same thread to be grouped under a common trace.

    Args:
        thread_state: The thread state containing thread_id/name/agent_id and any
                      persisted trace context (parent_trace_id, parent_span_id)
        user_id: The user ID for span attributes

    Yields:
        The thread span (either newly created or restored from existing context)

    Example:
        async with thread_span_context(
            thread_state=thread, user_id=user_id
        ) as thread_span:
            # Child spans created here will inherit the thread's trace context
            with tracer.start_span("child_operation"):
                ...
    """
    from opentelemetry import trace

    from agent_platform.server.storage import StorageService

    tracer = trace.get_tracer("sema4ai.agent_server")
    storage = StorageService.get_instance()

    # If thread already has trace context, restore it using a NonRecordingSpan.
    # NonRecordingSpan is an OTEL API class for context propagation - it carries
    # trace_id/span_id so child spans inherit the context.
    if thread_state.parent_trace_id is not None and thread_state.parent_span_id is not None:
        logger.debug(
            "Restoring thread trace context",
            thread_id=thread_state.thread_id,
            parent_trace_id=thread_state.parent_trace_id,
            parent_span_id=thread_state.parent_span_id,
        )
        parent_span = _restore_span_context(
            thread_state.parent_trace_id,
            thread_state.parent_span_id,
        )
        with trace.use_span(parent_span):
            yield parent_span
        return

    # First run on this thread: create a new span and persist the trace context
    logger.debug(
        "Creating new thread trace context",
        thread_id=thread_state.thread_id,
        agent_id=thread_state.agent_id,
    )
    with tracer.start_as_current_span(
        thread_state.name,
        attributes={
            "thread_id": thread_state.thread_id,
            "agent_id": thread_state.agent_id,
            "user_id": user_id,
        },
    ) as span:
        ctx = span.get_span_context()
        new_trace_id = format(ctx.trace_id, "032x")
        new_span_id = format(ctx.span_id, "016x")

        # Persist trace context for future runs on this thread
        await storage.set_thread_trace_context(
            user_id,
            thread_state.thread_id,
            parent_trace_id=new_trace_id,
            parent_span_id=new_span_id,
        )

        yield span
