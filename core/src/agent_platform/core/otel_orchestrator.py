"""OTEL trace orchestrator for multiple observability providers."""

import logging
import threading

from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import SpanProcessor
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from agent_platform.core.integrations.observability.integration import ObservabilityIntegration

logger = logging.getLogger(__name__)


class OtelOrchestrator(SpanProcessor):
    """Orchestrates OTEL traces to multiple observability providers.

    Routes spans to:
    1. OTEL Collector (if configured via env vars) - internal telemetry
    2. Observability integrations (LangSmith, Grafana, etc.) - external backends

    Thread-safe singleton that supports hot-reload of integrations.
    """

    _instance: "OtelOrchestrator | None" = None
    _instance_lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "OtelOrchestrator":
        """Get singleton instance."""
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls()
                logger.debug("Created OtelOrchestrator singleton instance")
            return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton instance (primarily for testing)."""
        with cls._instance_lock:
            if cls._instance is not None:
                try:
                    cls._instance.shutdown()
                except Exception as e:
                    logger.warning(f"Error shutting down orchestrator during reset: {e}")
                cls._instance = None
                logger.debug("Reset OtelOrchestrator singleton instance")

    def __init__(self):
        """Initialize orchestrator with empty maps and load collector from env."""
        self._runtime_map: dict[str, BatchSpanProcessor] = {}  # integration_id → processor
        self._meta_map: dict[str, ObservabilityIntegration] = {}  # integration_id → integration
        self._collector_processor: BatchSpanProcessor | None = None  # OTEL collector
        self._lock = threading.Lock()

        # Load OTEL collector from environment variables
        self._load_collector_from_env()

    def _load_collector_from_env(self):
        """Load OTEL collector processor from environment variables.

        Checks OTELConfig for collector_url and creates a processor if configured.
        This is separate from observability integrations (internal vs external telemetry).
        """
        from agent_platform.core.telemetry.telemetry import OTELConfig

        if not OTELConfig.is_enabled:
            logger.debug("OTEL is not enabled, skipping collector processor")
            return

        collector_url = OTELConfig.collector_url
        if not collector_url or not collector_url.strip():
            logger.debug("OTEL collector URL not configured, skipping collector processor")
            return

        # Ensure URL has proper scheme
        if not collector_url.startswith(("http://", "https://")):
            collector_url = f"http://{collector_url}"

        try:
            endpoint = f"{collector_url}/v1/traces"
            exporter = OTLPSpanExporter(endpoint=endpoint)
            self._collector_processor = BatchSpanProcessor(exporter)
            logger.info(f"Loaded OTEL collector processor: {endpoint}")
        except Exception as e:
            logger.error(f"Failed to create OTEL collector processor: {e}")

    def _create_processor(self, integration: ObservabilityIntegration) -> BatchSpanProcessor:
        """Create a BatchSpanProcessor for an observability integration.
        Delegates to the integration's settings to create the OTLPSpanExporter.

        Args:
            integration: ObservabilityIntegration with kind='observability'

        Returns:
            BatchSpanProcessor configured for the provider

        Raises:
            ValueError: If provider unsupported
        """
        # Create OTEL exporter
        exporter = integration.settings.provider_settings.make_exporter()
        logger.debug(f"Created OTEL exporter for {integration.settings.provider_kind}")

        # Wrap in BatchSpanProcessor
        return BatchSpanProcessor(exporter)

    def load_integrations(self, integrations: list[ObservabilityIntegration]):
        """Load multiple integrations on startup.

        Args:
            integrations: List of Integration objects from database
        """
        for integration in integrations:
            self.reload_integration(integration)
        logger.info(f"Loaded {len(integrations)} observability integration(s)")

    def reload_integration(self, integration: ObservabilityIntegration):
        """Hot-reload a single integration.

        Updates both runtime_map and meta_map. Compares with existing meta_map
        entry to avoid unnecessary processor rebuilds.

        Args:
            integration: Integration object from database
        """
        integration_id = integration.id

        # Check if enabled
        if not integration.settings.is_enabled:
            # The integration is disabled, so we remove it from the orchestrator
            # no-op at startup when the orchestrator has not loaded anything yet.
            self.remove_integration(integration_id)
            return

        with self._lock:
            # Check if unchanged (compare against meta_map)
            existing = self._meta_map.get(integration_id)
            if existing and existing.settings == integration.settings:
                logger.debug(f"Integration {integration_id} unchanged, skipping reload")
                return

            # Shutdown old processor if exists
            if integration_id in self._runtime_map:
                old_processor = self._runtime_map[integration_id]
                try:
                    old_processor.shutdown()
                    logger.debug(f"Shutdown old processor for {integration_id}")
                except Exception as e:
                    logger.warning(f"Error shutting down old processor for {integration_id}: {e}")

            # Create new processor
            try:
                new_processor = self._create_processor(integration)

                # Update BOTH maps (same keys, different values)
                self._runtime_map[integration_id] = new_processor
                self._meta_map[integration_id] = integration

                logger.info(
                    f"Reloaded integration {integration_id} ({integration.settings.provider_kind})"
                )
            except Exception as e:
                logger.error(f"Failed to create processor for {integration_id}: {e}")
                # Remove from maps if creation failed
                self._runtime_map.pop(integration_id, None)
                self._meta_map.pop(integration_id, None)

    def remove_integration(self, integration_id: str):
        """Remove an integration.

        Removes from both runtime_map and meta_map.

        Args:
            integration_id: Integration ID to remove
        """
        with self._lock:
            processor = self._runtime_map.pop(integration_id, None)
            self._meta_map.pop(integration_id, None)

            if processor:
                try:
                    processor.shutdown()
                    logger.info(f"Removed integration {integration_id}")
                except Exception as e:
                    logger.error(f"Error shutting down processor for {integration_id}: {e}")

    def on_start(self, span, parent_context=None):
        """Route span start to collector + all integration processors."""
        # Build list of all processors
        processors = []
        if self._collector_processor:
            processors.append(self._collector_processor)

        with self._lock:
            processors.extend(self._runtime_map.values())

        # Route to all processors
        for processor in processors:
            try:
                processor.on_start(span, parent_context)
            except Exception as e:
                logger.error(f"Error in processor on_start: {e}")

    def on_end(self, span):
        """Route span end to collector + all integration processors."""
        # Build list of all processors
        processors = []
        if self._collector_processor:
            processors.append(self._collector_processor)

        with self._lock:
            processors.extend(self._runtime_map.values())

        # Route to all processors
        for processor in processors:
            try:
                processor.on_end(span)
            except Exception as e:
                logger.error(f"Error in processor on_end: {e}")

    def shutdown(self):
        """Shutdown collector + all integration processors."""
        logger.debug("Shutting down OtelOrchestrator")

        # Build list of all processors
        processors = []
        if self._collector_processor:
            processors.append(self._collector_processor)

        with self._lock:
            processors.extend(self._runtime_map.values())

        # Shutdown all processors
        for processor in processors:
            try:
                processor.shutdown()
            except Exception as e:
                logger.error(f"Error shutting down processor: {e}")

        # Clear maps
        with self._lock:
            self._runtime_map.clear()
            self._meta_map.clear()

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        """Force flush collector + all integration processors."""
        logger.debug("Force flushing OtelOrchestrator")

        # Build list of all processors
        processors = []
        if self._collector_processor:
            processors.append(self._collector_processor)

        with self._lock:
            processors.extend(self._runtime_map.values())

        # Flush all processors
        results = []
        for processor in processors:
            try:
                result = processor.force_flush(timeout_millis)
                results.append(result)
            except Exception as e:
                logger.error(f"Error flushing processor: {e}")
                results.append(False)

        overall_result = all(results) if results else True
        logger.debug(f"OtelOrchestrator force flush overall result: {overall_result}")
        return overall_result
