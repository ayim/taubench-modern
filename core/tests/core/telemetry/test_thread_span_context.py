"""Tests for thread_span_context helper."""

from unittest.mock import AsyncMock, patch

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider

from agent_platform.core.telemetry.helpers import (
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


class TestThreadSpanContext:
    """Tests for thread_span_context async context manager."""

    @pytest.mark.asyncio
    async def test_existing_context_restored(self):
        """When thread has trace context, should restore NonRecordingSpan."""
        thread = Thread(
            thread_id="test-thread",
            name="Test Thread",
            agent_id="test-agent",
            user_id="test-user",
            parent_trace_id="0" * 32,
            parent_span_id="0" * 16,
        )

        async with thread_span_context(
            thread_state=thread,
            user_id="test-user",
        ) as span:
            # NonRecordingSpan does not record
            assert not span.is_recording()
            ctx = span.get_span_context()
            assert ctx.trace_id == 0
            assert ctx.span_id == 0

    @pytest.mark.asyncio
    async def test_existing_context_with_real_values(self):
        """Restored context should match stored hex values."""
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

        async with thread_span_context(
            thread_state=thread,
            user_id="test-user",
        ) as span:
            ctx = span.get_span_context()
            assert format(ctx.trace_id, "032x") == trace_id
            assert format(ctx.span_id, "016x") == span_id

    @pytest.mark.asyncio
    async def test_new_context_created_and_persisted(self):
        """When thread has no trace context, should create and persist new span."""
        thread = Thread(
            thread_id="test-thread",
            name="Test Thread",
            agent_id="test-agent",
            user_id="test-user",
            parent_trace_id=None,
            parent_span_id=None,
        )

        mock_storage = AsyncMock()

        with patch(
            "agent_platform.server.storage.StorageService.get_instance",
            return_value=mock_storage,
        ):
            async with thread_span_context(
                thread_state=thread,
                user_id="test-user",
            ) as span:
                # Should be a recording span
                assert span.is_recording()

            # Verify storage was called
            mock_storage.set_thread_trace_context.assert_called_once()
            call_args = mock_storage.set_thread_trace_context.call_args
            assert call_args[0][0] == "test-user"
            assert call_args[0][1] == "test-thread"
            # Trace/span IDs should be hex strings of correct length
            assert len(call_args.kwargs["parent_trace_id"]) == 32
            assert len(call_args.kwargs["parent_span_id"]) == 16

    @pytest.mark.asyncio
    async def test_storage_failure_propagates(self):
        """Storage failure during set_thread_trace_context should propagate."""
        thread = Thread(
            thread_id="test-thread",
            name="Test Thread",
            agent_id="test-agent",
            user_id="test-user",
            parent_trace_id=None,
            parent_span_id=None,
        )

        mock_storage = AsyncMock()
        mock_storage.set_thread_trace_context.side_effect = Exception("DB error")

        with patch(
            "agent_platform.server.storage.StorageService.get_instance",
            return_value=mock_storage,
        ):
            with pytest.raises(Exception, match="DB error"):
                async with thread_span_context(
                    thread_state=thread,
                    user_id="test-user",
                ):
                    pass

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
            async with thread_span_context(
                thread_state=thread,
                user_id="test-user",
            ):
                pass
