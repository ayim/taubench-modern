"""Tests for thread_span_context and create_thread_trace_context helpers."""

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider

from agent_platform.core.telemetry.helpers import (
    create_thread_trace_context,
    thread_span_context,
)
from agent_platform.core.thread.thread import Thread


@pytest.fixture(autouse=True)
def setup_tracer_provider():
    """Set up a real tracer provider so spans are recorded."""
    provider = TracerProvider()
    trace.set_tracer_provider(provider)
    yield
    # Reset to default after test
    trace.set_tracer_provider(TracerProvider())


class TestCreateThreadTraceContext:
    """Tests for create_thread_trace_context function."""

    def test_creates_valid_trace_and_span_ids(self):
        """Should return valid 32-char trace_id and 16-char span_id."""
        trace_id, span_id = create_thread_trace_context(
            thread_name="Test Thread",
            thread_id="test-thread-123",
            agent_id="test-agent-456",
            user_id="test-user-789",
        )

        assert len(trace_id) == 32
        assert len(span_id) == 16
        # Should be valid hex strings
        int(trace_id, 16)
        int(span_id, 16)

    def test_creates_unique_ids_each_call(self):
        """Each call should generate unique trace and span IDs."""
        ids1 = create_thread_trace_context(
            thread_name="Thread 1",
            thread_id="thread-1",
            agent_id="agent-1",
            user_id="user-1",
        )
        ids2 = create_thread_trace_context(
            thread_name="Thread 2",
            thread_id="thread-2",
            agent_id="agent-2",
            user_id="user-2",
        )

        assert ids1[0] != ids2[0]  # Different trace IDs
        assert ids1[1] != ids2[1]  # Different span IDs


class TestThreadSpanContext:
    """Tests for thread_span_context async context manager."""

    @pytest.mark.asyncio
    async def test_restores_non_recording_span_with_correct_context(self):
        """Should restore NonRecordingSpan matching stored hex values."""
        trace_id = "1a2b3c4d5e6f7890abcdef1234567890"
        span_id = "abcdef1234567890"

        thread = Thread(
            thread_id="test-thread",
            name="Test Thread",
            agent_id="test-agent",
            user_id="test-user",
            parent_trace_id=trace_id,
            parent_span_id=span_id,
        )

        async with thread_span_context(thread_state=thread) as span:
            assert span is not None
            assert not span.is_recording()  # NonRecordingSpan
            ctx = span.get_span_context()
            assert format(ctx.trace_id, "032x") == trace_id
            assert format(ctx.span_id, "016x") == span_id

    @pytest.mark.asyncio
    async def test_invalid_stored_context_raises(self):
        """Invalid stored trace context should raise ValueError."""
        thread = Thread(
            thread_id="test-thread",
            name="Test Thread",
            agent_id="test-agent",
            user_id="test-user",
            parent_trace_id="invalid",
            parent_span_id="also_invalid",
        )

        with pytest.raises(ValueError, match="Invalid trace context"):
            async with thread_span_context(thread_state=thread):
                pass

    @pytest.mark.asyncio
    async def test_creates_fallback_span_when_trace_context_missing(self):
        """Should create a new span when trace context is missing."""
        thread = Thread(
            thread_id="test-thread",
            name="Test Thread",
            agent_id="test-agent",
            user_id="test-user",
            parent_trace_id=None,
            parent_span_id=None,
        )

        async with thread_span_context(thread_state=thread) as span:
            assert span is not None
            assert span.is_recording()  # New recording span
            ctx = span.get_span_context()
            assert ctx.trace_id != 0
            assert ctx.span_id != 0
