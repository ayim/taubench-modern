from asyncio import Semaphore, create_task
from collections import deque
from collections.abc import Generator
from contextlib import contextmanager
from logging import getLogger

from opentelemetry.trace import NoOpTracer, SpanContext, Tracer

from agent_platform.core.kernel_interfaces.otel import (
    OTelArtifact,
    OTelInterface,
    WrappedSpan,
)
from agent_platform.server.kernel.kernel_mixin import UsesKernelMixin


class AgentServerOTelInterface(OTelInterface, UsesKernelMixin):
    def __init__(self, tracer: Tracer | None = None):
        # Use noop tracer if none is provided
        # TODO: warn if noop tracer is used?
        self.span_stack: list[WrappedSpan] = []
        self.tracer = (
            tracer if tracer is not None else NoOpTracer()
        )
        # Queue for artifact creation
        self._artifact_queue = deque()
        self._artifact_semaphore = Semaphore(10)  # Limit concurrent uploads
        self._artifact_tasks = set()
        self._logger = getLogger(__name__)

    @contextmanager
    def span(
        self,
        name: str,
        attributes: dict | None = None,
    ) -> Generator[WrappedSpan, None, None]:
        span = self.tracer.start_span(name, attributes=attributes)
        wrapped_span = WrappedSpan(self, span)
        self.span_stack.append(wrapped_span)
        try:
            yield wrapped_span
        except Exception as e:
            span.record_exception(e)
            raise
        finally:
            span.end()
            self.span_stack.pop()

    @property
    def active_span(self) -> WrappedSpan:
        if len(self.span_stack) == 0:
            raise RuntimeError("No active span")
        return self.span_stack[-1]

    @property
    def context(self) -> SpanContext:
        return self.active_span.get_span_context()

    @property
    def trace_id(self) -> str:
        return self.context.trace_id

    async def create_artifact(
        self,
        name: str,
        mime_type: str,
        content: str | bytes,
        artifact_id: str | None = None,
    ) -> OTelArtifact:
        if artifact_id is None:
            from uuid import uuid4

            artifact_id = str(uuid4())

        artifact = OTelArtifact(
            name=name,
            mime_type=mime_type,
            content=(
                content.encode("utf-8")
                if isinstance(content, str)
                else content
            ),
            artifact_id=artifact_id,
            trace_id=self.trace_id,
            correlated_user_id=self.kernel.user.user_id,
            correlated_agent_id=self.kernel.agent.agent_id,
            correlated_thread_id=self.kernel.thread.thread_id,
            correlated_run_id=self.kernel.run.run_id,
            correlated_message_id=self.kernel.thread_state.active_message_id,
        )

        await self.kernel.storage.create_otel_artifact(artifact)
        return artifact

    def enqueue_artifact_creation(
        self,
        name: str,
        mime_type: str,
        content: str | bytes,
        artifact_id: str,
    ) -> None:
        """Add an artifact creation task to the queue."""
        task = create_task(self._process_artifact_creation(
            name, mime_type, content, artifact_id,
        ))
        self._artifact_tasks.add(task)
        task.add_done_callback(self._artifact_tasks.discard)

    async def _process_artifact_creation(
        self,
        name: str,
        mime_type: str,
        content: str | bytes,
        artifact_id: str,
    ) -> None:
        """Process artifact creation with rate limiting and error handling."""
        async with self._artifact_semaphore:
            try:
                await self.create_artifact(
                    name, mime_type, content, artifact_id,
                )
            except Exception as e:
                self._logger.error(f"Failed to create artifact {name}: {e}")
                # Could implement retry logic here if needed
