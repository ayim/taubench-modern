"""OTEL telemetry orchestrator for multiple observability providers."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

import structlog
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics.export import MetricExporter, MetricExportResult
from opentelemetry.sdk.trace import SpanProcessor
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from agent_platform.core.telemetry.helpers import (
    build_routing_map,
    compute_config_hash,
    extract_agent_id,
)

if TYPE_CHECKING:
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import MetricsData
    from opentelemetry.sdk.resources import Resource

    from agent_platform.core.integrations.observability.integration import ObservabilityIntegration
    from agent_platform.core.telemetry.providers.base import OtelProvider

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class OtelOrchestrator(SpanProcessor, MetricExporter):
    """Orchestrates OTEL telemetry to multiple observability providers.

    Routes telemetry signals to:
    1. OTEL Collector (if configured via env vars) - internal telemetry
    2. Observability integrations (LangSmith, Grafana, etc.) - external backends

    Implements:
    - SpanProcessor: Routes traces via on_start()/on_end() based on agent_id
    - MetricExporter: Broadcasts metrics via export() to all metric-capable providers

    Thread-safe singleton that supports hot-reload of integrations.

    Uses OtelProvider abstraction for backend-specific logic. Each provider
    manages its own handlers (BatchSpanProcessor, MetricExporter) for export.
    """

    _instance: OtelOrchestrator | None = None
    _instance_lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> OtelOrchestrator:
        """Get singleton instance."""
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls()
                logger.debug("Created OtelOrchestrator singleton instance", instance_id=id(cls._instance))
            return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton instance.

        WARNING: Not thread-safe with active span processing!
        If spans are actively flowing through on_start/on_end, calling this
        may cause errors as processors are shut down mid-use.

        Only call during application shutdown or in tests.
        """
        with cls._instance_lock:
            if cls._instance is not None:
                try:
                    cls._instance.shutdown()
                except Exception as e:
                    logger.warning("Error shutting down orchestrator during reset", error=str(e))
                cls._instance = None
                logger.debug("Reset OtelOrchestrator singleton instance")

    def __init__(self):
        """Initialize orchestrator."""
        # Be sure to initialize the state in the MetricExporter base class.
        MetricExporter.__init__(self)

        # Complete map: agent_id → processors (global + agent-specific)
        self._agent_id_to_processors: dict[str, set[BatchSpanProcessor]] = {}

        # Global processors - used as fallback when agent_id not in map
        self._global_processors: set[BatchSpanProcessor] = set()

        # Global metric exporters - metrics are not agent-scoped
        self._metric_exporters: list[MetricExporter] = []

        # Providers keyed by config hash - for lifecycle management
        self._hash_to_provider: dict[str, OtelProvider] = {}

        # Collector processor and metric exporter - used to export telemetry to the OTEL collector
        # (defined using environment variables SEMA4AI_AGENT_SERVER_OTEL_COLLECTOR_URL)
        # This is the legacy way of defining the collector.
        # It should go away once we add support for adding a custom OTLP endpoint-based
        # observability integration.
        self._collector_processor: BatchSpanProcessor | None = None
        self._collector_metric_exporter: MetricExporter | None = None
        self._lock = threading.Lock()

        # Track shutdown state to ensure idempotency (shutdown may be called multiple
        # times since we implement both SpanProcessor and MetricExporter interfaces)
        self._is_shutdown = False

        # Load OTEL collector from environment variables
        self._load_collector_from_env()

    def _load_collector_from_env(self):
        """Load OTEL collector processor and metric exporter from environment variables.

        Checks OTELConfig for collector_url and creates processors if configured.
        This is separate from observability integrations (internal vs external telemetry).
        """
        from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter

        from agent_platform.core.telemetry.telemetry import OTELConfig

        collector_url = OTELConfig.collector_url
        if not collector_url or not collector_url.strip():
            logger.debug("OTEL collector URL not configured, skipping collector")
            return

        # Ensure URL has proper scheme
        if not collector_url.startswith(("http://", "https://")):
            collector_url = f"http://{collector_url}"

        # Create trace processor
        try:
            trace_endpoint = f"{collector_url}/v1/traces"
            exporter = OTLPSpanExporter(endpoint=trace_endpoint)
            self._collector_processor = BatchSpanProcessor(exporter)
            logger.info("Loaded OTEL collector trace processor", endpoint=trace_endpoint)
        except Exception as e:
            logger.error("Failed to create OTEL collector trace processor", error=str(e))

        # Create metric exporter
        try:
            metric_endpoint = f"{collector_url}/v1/metrics"
            self._collector_metric_exporter = OTLPMetricExporter(endpoint=metric_endpoint)
            logger.info("Loaded OTEL collector metric exporter", endpoint=metric_endpoint)
        except Exception as e:
            logger.error("Failed to create OTEL collector metric exporter", error=str(e))

    def create_meter_provider(
        self,
        resource: Resource,
        export_interval_millis: int = 15000,
    ) -> MeterProvider:
        """Create a MeterProvider configured to export metrics through this orchestrator.

        Encapsulates the setup of PeriodicExportingMetricReader so callers don't need
        to know the internal details of how metrics export is configured.

        Args:
            resource: OpenTelemetry Resource with service info
            export_interval_millis: How often to export metrics (default: 15000ms)

        Returns:
            Configured MeterProvider ready to be set as the global meter provider
        """
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader

        reader = PeriodicExportingMetricReader(
            exporter=self,
            export_interval_millis=export_interval_millis,
        )
        logger.info("Created MeterProvider with OtelOrchestrator", export_interval_millis=export_interval_millis)
        return MeterProvider(resource=resource, metric_readers=[reader])

    def _get_or_create_provider(
        self,
        integration: ObservabilityIntegration,
        hash_to_provider: dict[str, OtelProvider],
    ) -> OtelProvider | None:
        """Get existing provider for config hash, or create new one.

        Providers are deduplicated by config hash - multiple integrations with
        identical settings share a single provider instance. Each provider manages
        its own trace processor internally.

        Args:
            integration: ObservabilityIntegration to create provider for
            hash_to_provider: Cache of config hash -> provider (for deduplication and lifecycle)

        Returns:
            OtelProvider for the integration, or None if creation failed
        """
        from agent_platform.core.telemetry.providers.factory import OtelProviderFactory

        config_hash = compute_config_hash(integration)

        if config_hash in hash_to_provider:
            logger.debug("Integration shares existing provider", integration_id=integration.id, config_hash=config_hash)
            return hash_to_provider[config_hash]

        try:
            provider = OtelProviderFactory.create(integration.settings.settings)
            hash_to_provider[config_hash] = provider
            logger.info(
                "Created provider for integration",
                provider_kind=provider.provider_kind,
                integration_id=integration.id,
                config_hash=config_hash,
            )
            return provider
        except Exception as e:
            logger.error("Failed to create provider for integration", integration_id=integration.id, error=str(e))
            return None

    def _get_processors_for_agent(self, agent_id: str | None) -> list[BatchSpanProcessor]:
        """Get processors for routing spans to a specific agent.

        Args:
            agent_id: Agent ID for direct lookup.
                      If None or not in map, falls back to global processors.
        """
        with self._lock:
            if agent_id is None:
                # No agent context - use global processors as fallback
                result = list(self._global_processors)
            elif agent_id in self._agent_id_to_processors:
                # Direct lookup - map contains global + agent-specific combined
                result = list(self._agent_id_to_processors[agent_id])
            else:
                # Agent not in map - fall back to global processors
                # This might happen in a race condition
                # when a new agent is created but not yet added to the map.
                result = list(self._global_processors)

        if self._collector_processor:
            result.insert(0, self._collector_processor)

        return result

    def _get_all_processors(self) -> list[BatchSpanProcessor]:
        """Get ALL unique processors for shutdown/flush operations."""
        with self._lock:
            processors: set[BatchSpanProcessor] = set()
            processors.update(self._global_processors)
            for procs in self._agent_id_to_processors.values():
                processors.update(procs)
            result = list(processors)

        if self._collector_processor:
            result.insert(0, self._collector_processor)

        return result

    def _shutdown_providers(self, providers: list[OtelProvider]) -> None:
        """Shutdown providers, logging any errors.

        Args:
            providers: List of providers to shutdown
        """
        for provider in providers:
            try:
                provider.shutdown()
            except Exception as e:
                logger.error("Error shutting down provider", provider_kind=provider.provider_kind, error=str(e))

    def _collect_metric_exporters(
        self,
        hash_to_provider: dict[str, OtelProvider],
    ) -> list[MetricExporter]:
        """Collect metric exporters from all providers that support metrics.

        Unlike traces (which are routed per-agent), metrics are broadcast to ALL
        backends that support metrics. The agent_id attribute on metrics enables
        filtering at the dashboard/query level.

        Args:
            hash_to_provider: Map of config hash to provider

        Returns:
            List of MetricExporter instances from all metric-capable providers
        """
        metric_exporters: list[MetricExporter] = []
        seen_exporters: set[int] = set()  # Track by id to avoid duplicates

        for provider in hash_to_provider.values():
            exporter = provider.get_metrics_exporter()
            if exporter is not None and id(exporter) not in seen_exporters:
                metric_exporters.append(exporter)
                seen_exporters.add(id(exporter))
                logger.debug("Collected metric exporter", provider_kind=provider.provider_kind)

        return metric_exporters

    def export(
        self,
        metrics_data: MetricsData,
        timeout_millis: float = 10000,
        **kwargs,
    ) -> MetricExportResult:
        """Export metrics to collector and all metric-capable providers.

        Implements MetricExporter.export() to route metrics to:
        1. OTEL Collector (if configured) - internal telemetry
        2. Observability integrations (Grafana, etc.) - external backends

        Unlike traces (which are routed per-agent), metrics are broadcast to ALL
        destinations. The agent_id attribute enables filtering at the dashboard level.

        Args:
            metrics_data: The metrics data to export
            timeout_millis: Export timeout in milliseconds
            **kwargs: Additional arguments (ignored)

        Returns:
            MetricExportResult.SUCCESS if all exports succeeded, FAILURE otherwise
        """
        with self._lock:
            exporters = list(self._metric_exporters)

        # Add collector metric exporter if configured
        if self._collector_metric_exporter:
            exporters.append(self._collector_metric_exporter)

        if not exporters:
            return MetricExportResult.SUCCESS

        results = []
        for exporter in exporters:
            try:
                result = exporter.export(metrics_data, timeout_millis=timeout_millis)
                results.append(result == MetricExportResult.SUCCESS)
            except Exception as e:
                logger.error("Error exporting metrics", exporter_type=type(exporter).__name__, error=str(e))
                results.append(False)

        return MetricExportResult.SUCCESS if all(results) else MetricExportResult.FAILURE

    async def reload_from_storage(self, storage) -> None:
        """Rebuild agent-to-processors map from storage.

        Builds complete map: each agent_id -> (global processors + agent-specific processors).
        This pre-computes everything so the hot path is a simple dict lookup.

        Uses OtelProviderFactory to create providers from integration settings,
        then extracts trace handlers from providers for routing.

        Args:
            storage: Storage instance to query integrations, scopes, and agents
        """
        # Query all agents and enabled integrations
        agents = await storage.list_all_agents()
        agent_ids = [agent.agent_id for agent in agents]
        integrations = await storage.list_enabled_observability_integrations()

        # For each integration, query scopes and create providers (deduped by config hash).
        # Providers manage their own trace processors internally.
        temp_hash_to_provider: dict[str, OtelProvider] = {}
        integration_id_to_processor: dict[str, BatchSpanProcessor] = {}
        integration_scopes: dict[str, list] = {}

        for integration in integrations:
            try:
                scopes = await storage.list_integration_scopes(integration.id)
            except Exception as e:
                logger.error(
                    "Error loading scopes for integration", integration_id=integration.id, error=str(e), exc_info=True
                )
                continue

            if not scopes:
                continue

            provider = self._get_or_create_provider(integration, temp_hash_to_provider)
            if provider:
                # Get trace processor from provider (providers manage their own processors)
                processor = provider.get_trace_processor()
                if processor:
                    integration_scopes[integration.id] = scopes
                    integration_id_to_processor[integration.id] = processor
                else:
                    logger.warning("Provider does not support traces", provider_kind=provider.provider_kind)

        # Build routing map and swap
        new_map, new_global = build_routing_map(agent_ids, integration_id_to_processor, integration_scopes)

        # Collect metric exporters from all metric-capable providers
        new_metric_exporters = self._collect_metric_exporters(temp_hash_to_provider)

        with self._lock:
            # Collect old providers for shutdown
            old_providers = list(self._hash_to_provider.values())

            # Swap in new maps
            self._agent_id_to_processors = new_map
            self._global_processors = new_global
            self._hash_to_provider = temp_hash_to_provider
            self._metric_exporters = new_metric_exporters

        # Shutdown old providers (may still flush pending spans)
        self._shutdown_providers(old_providers)

        logger.info(
            "Reloaded observability integrations",
            agent_count=len(agent_ids),
            integration_count=len(integrations),
            unique_provider_count=len(temp_hash_to_provider),
            global_processor_count=len(new_global),
            metric_exporter_count=len(new_metric_exporters),
        )

    def on_start(self, span, parent_context=None):
        """Route span start to deduplicated processors based on agent_id."""
        for processor in self._get_processors_for_agent(extract_agent_id(span)):
            try:
                processor.on_start(span, parent_context)
            except Exception as e:
                logger.error("Error in processor on_start", error=str(e))

    def on_end(self, span):
        """Route span end to deduplicated processors based on agent_id."""
        for processor in self._get_processors_for_agent(extract_agent_id(span)):
            try:
                processor.on_end(span)
            except Exception as e:
                logger.error("Error in processor on_end", error=str(e))

    def shutdown(self, **kwargs) -> None:
        """Shutdown collector + all providers.

        This class implements both SpanProcessor and MetricExporter interfaces,
        so shutdown() may be called twice (once by TracerProvider, once by MeterProvider).
        We track state to ensure idempotency.

        Note: **kwargs accepts `timeout` param from PeriodicExportingMetricReader
        (the SDK passes `timeout=` not `timeout_millis=`).

        WARNING: Not thread-safe with active span processing!
        If spans are actively flowing through on_start/on_end, calling this
        may cause errors as processors are shut down mid-use.

        Only call during application shutdown or in tests (via reset_instance).

        Args:
            **kwargs: Accepts timeout/timeout_millis for interface compatibility (unused)
        """
        if self._is_shutdown:
            logger.debug("OtelOrchestrator already shutdown, skipping")
            return

        logger.debug("Shutting down OtelOrchestrator")
        self._is_shutdown = True

        # Shutdown collector processor directly (not managed by provider)
        if self._collector_processor:
            try:
                self._collector_processor.shutdown()
            except Exception as e:
                logger.error("Error shutting down collector trace processor", error=str(e))

        # Shutdown collector metric exporter directly (not managed by provider)
        if self._collector_metric_exporter:
            try:
                self._collector_metric_exporter.shutdown()
            except Exception as e:
                logger.error("Error shutting down collector metric exporter", error=str(e))

        # Shutdown all providers
        with self._lock:
            providers = list(self._hash_to_provider.values())
            self._hash_to_provider.clear()
            self._agent_id_to_processors.clear()
            self._global_processors.clear()
            self._metric_exporters.clear()

        self._shutdown_providers(providers)

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        """Force flush collector + all providers."""
        logger.debug("Force flushing OtelOrchestrator")

        results = []

        # Flush collector processor
        if self._collector_processor:
            try:
                results.append(self._collector_processor.force_flush(timeout_millis))
            except Exception as e:
                logger.error("Error flushing collector processor", error=str(e))
                results.append(False)

        # Flush all providers
        with self._lock:
            providers = list(self._hash_to_provider.values())

        for provider in providers:
            try:
                results.append(provider.force_flush(timeout_millis))
            except Exception as e:
                logger.error("Error flushing provider", provider_kind=provider.provider_kind, error=str(e))
                results.append(False)

        overall_result = all(results) if results else True
        logger.debug("OtelOrchestrator force flush completed", overall_result=overall_result)
        return overall_result
