"""Abstract base class for OTEL providers."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class OtelProvider(ABC):
    """Abstract base class for observability providers.

    Providers encapsulate backend-specific logic for creating OTEL exporters.
    Each provider knows how to create exporters for its backend and what signals
    it supports.

    Subclasses must implement:
    - _create_trace_exporter(): Create the backend-specific SpanExporter
    - provider_kind: Return the provider identifier string

    The base class provides default implementations for:
    - Lazy initialization of BatchSpanProcessor
    - get_trace_processor(), get_metrics_exporter(), get_logs_processor()
    - shutdown() and force_flush() lifecycle methods
    """

    def __init__(self) -> None:
        """Initialize provider state."""
        self._trace_processor: BatchSpanProcessor | None = None
        self._initialized = False

    def _ensure_initialized(self) -> None:
        """Lazily initialize the trace processor on first access.

        Note: Not thread-safe. Caller (OtelOrchestrator) serializes access
        via reload lock, so concurrent calls are not possible in practice.
        """
        if self._initialized:
            return

        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        exporter = self._create_trace_exporter()
        self._trace_processor = BatchSpanProcessor(exporter)
        self._initialized = True
        logger.debug("Initialized trace processor", provider=self.provider_kind)

    @abstractmethod
    def _create_trace_exporter(self) -> "SpanExporter":
        """Create a raw trace exporter for this provider.

        Internal method for creating a trace exporter.
        Invoked by get_trace_processor.

        Returns:
            SpanExporter configured for this provider's backend
        """

    @property
    @abstractmethod
    def provider_kind(self) -> str:
        """Return the provider kind identifier (e.g., 'grafana', 'langsmith')."""

    def get_trace_processor(self) -> "BatchSpanProcessor | None":
        """Return trace processor.

        Returns:
            BatchSpanProcessor for trace export
        """
        self._ensure_initialized()
        return self._trace_processor

    def get_metrics_exporter(self):
        """Return metrics exporter, or None if metrics not supported.

        Returns:
            None - metrics not yet implemented for this provider
        """
        return None

    def get_logs_processor(self):
        """Return logs processor, or None if logs not supported.

        Returns:
            None - logs not yet implemented for this provider
        """
        return None

    def shutdown(self) -> None:
        """Shutdown the trace processor."""
        if self._trace_processor is not None:
            try:
                self._trace_processor.shutdown()
                logger.debug("Shutdown trace processor", provider=self.provider_kind)
            except Exception as e:
                logger.error("Error shutting down trace processor", provider=self.provider_kind, error=str(e))
            finally:
                self._trace_processor = None
                self._initialized = False

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        """Force flush the trace processor.

        Args:
            timeout_millis: Maximum time to wait for flush

        Returns:
            True if flush succeeded, False otherwise
        """
        if self._trace_processor is None:
            return True

        try:
            result = self._trace_processor.force_flush(timeout_millis)
            logger.debug("Trace processor flush completed", provider=self.provider_kind, result=result)
            return result
        except Exception as e:
            logger.error("Error flushing trace processor", provider=self.provider_kind, error=str(e))
            return False
