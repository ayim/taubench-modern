"""OTEL trace orchestrator for multiple observability providers."""

import logging
import threading

from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import SpanProcessor
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from agent_platform.core.integrations.observability.integration import ObservabilityIntegration
from agent_platform.core.telemetry.helpers import (
    build_routing_map,
    compute_config_hash,
    extract_agent_id,
    shutdown_processors,
)

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
                    logger.warning(f"Error shutting down orchestrator during reset: {e}")
                cls._instance = None
                logger.debug("Reset OtelOrchestrator singleton instance")

    def __init__(self):
        """Initialize orchestrator."""

        # Complete map: agent_id → processors (global + agent-specific)
        self._agent_id_to_processors: dict[str, set[BatchSpanProcessor]] = {}

        # Global processors - used as fallback when agent_id not in map
        self._global_processors: set[BatchSpanProcessor] = set()

        # Collector processor - used to export spans to the OTEL collector
        # (defined using environment variables SEMA4AI_AGENT_SERVER_OTEL_COLLECTOR_URL)
        # This is the legacy way of defining the collector processor.
        # It should go away once we add support for adding a custom OTLP endpoint-based
        # observability integration.
        self._collector_processor: BatchSpanProcessor | None = None
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

    def _get_or_create_processor(
        self,
        integration: ObservabilityIntegration,
        hash_to_processor: dict[str, BatchSpanProcessor],
    ) -> BatchSpanProcessor | None:
        """Get existing processor for config hash, or create new one."""
        config_hash = compute_config_hash(integration)

        if config_hash in hash_to_processor:
            logger.debug(f"Integration {integration.id} shares processor {config_hash}")
            return hash_to_processor[config_hash]

        try:
            processor = self._create_processor(integration)
            hash_to_processor[config_hash] = processor
            logger.info(f"Created processor for {integration.id}: hash {config_hash}")
            return processor
        except Exception as e:
            logger.error(f"Failed to create processor for {integration.id}: {e}")
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

    async def reload_from_storage(self, storage) -> None:
        """Rebuild agent-to-processors map from storage.

        Builds complete map: each agent_id -> (global processors + agent-specific processors).
        This pre-computes everything so the hot path is a simple dict lookup.

        Args:
            storage: Storage instance to query integrations, scopes, and agents
        """
        # Query all agents and enabled integrations
        agents = await storage.list_all_agents()
        agent_ids = [agent.agent_id for agent in agents]
        integrations = await storage.list_enabled_observability_integrations()

        # For each integration, query scopes and create processors (deduped by hash)
        temp_hash_to_processor: dict[str, BatchSpanProcessor] = {}
        integration_id_to_processor: dict[str, BatchSpanProcessor] = {}
        integration_scopes: dict[str, list] = {}

        for integration in integrations:
            try:
                scopes = await storage.list_integration_scopes(integration.id)
            except Exception as e:
                logger.error(f"Error loading scopes for {integration.id}: {e}", exc_info=True)
                continue

            if not scopes:
                continue

            processor = self._get_or_create_processor(integration, temp_hash_to_processor)
            if processor:
                integration_scopes[integration.id] = scopes
                integration_id_to_processor[integration.id] = processor

        # Build routing map and swap
        new_map, new_global = build_routing_map(
            agent_ids, integration_id_to_processor, integration_scopes
        )

        with self._lock:
            # Collect all old processors (global + per-agent, deduplicated)
            old_processors: set[BatchSpanProcessor] = set(self._global_processors)
            for processors in self._agent_id_to_processors.values():
                old_processors.update(processors)
            # Swap in new maps
            self._agent_id_to_processors = new_map
            self._global_processors = new_global

        # Shutdown old processors (may still flush pending spans)
        # Note: Can't use _get_all_processors() here because it includes collector
        shutdown_processors(list(old_processors))

        logger.info(
            f"Reloaded: {len(agent_ids)} agents, {len(integrations)} integrations, "
            f"{len(temp_hash_to_processor)} unique processors, {len(new_global)} global"
        )

    def on_start(self, span, parent_context=None):
        """Route span start to deduplicated processors based on agent_id."""
        for processor in self._get_processors_for_agent(extract_agent_id(span)):
            try:
                processor.on_start(span, parent_context)
            except Exception as e:
                logger.error(f"Error in processor on_start: {e}")

    def on_end(self, span):
        """Route span end to deduplicated processors based on agent_id."""
        for processor in self._get_processors_for_agent(extract_agent_id(span)):
            try:
                processor.on_end(span)
            except Exception as e:
                logger.error(f"Error in processor on_end: {e}")

    def shutdown(self):
        """Shutdown collector + all processors.

        WARNING: Not thread-safe with active span processing!
        If spans are actively flowing through on_start/on_end, calling this
        may cause errors as processors are shut down mid-use.

        Only call during application shutdown or in tests (via reset_instance).
        """
        logger.debug("Shutting down OtelOrchestrator")
        shutdown_processors(self._get_all_processors())
        with self._lock:
            self._agent_id_to_processors.clear()

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        """Force flush collector + all processors."""
        logger.debug("Force flushing OtelOrchestrator")

        results = []
        for processor in self._get_all_processors():
            try:
                results.append(processor.force_flush(timeout_millis))
            except Exception as e:
                logger.error(f"Error flushing processor: {e}")
                results.append(False)

        overall_result = all(results) if results else True
        logger.debug(f"OtelOrchestrator force flush overall result: {overall_result}")
        return overall_result
