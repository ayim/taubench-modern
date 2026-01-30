"""OTEL trace orchestrator for multiple observability providers."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

import structlog
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import SpanProcessor
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from agent_platform.core.telemetry.helpers import (
    build_routing_map,
    compute_config_hash,
    extract_agent_id,
)

if TYPE_CHECKING:
    from agent_platform.core.integrations.observability.integration import ObservabilityIntegration
    from agent_platform.core.telemetry.providers.base import OtelProvider

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class OtelOrchestrator(SpanProcessor):
    """Orchestrates OTEL traces to multiple observability providers.

    Routes spans to:
    1. OTEL Collector (if configured via env vars) - internal telemetry
    2. Observability integrations (LangSmith, Grafana, etc.) - external backends

    Thread-safe singleton that supports hot-reload of integrations.

    Uses OtelProvider abstraction for backend-specific logic. Each provider
    manages its own handlers (BatchSpanProcessor) for trace export.
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
        # Complete map: agent_id → processors (global + agent-specific)
        self._agent_id_to_processors: dict[str, set[BatchSpanProcessor]] = {}

        # Global processors - used as fallback when agent_id not in map
        self._global_processors: set[BatchSpanProcessor] = set()

        # Providers keyed by config hash - for lifecycle management
        self._hash_to_provider: dict[str, OtelProvider] = {}

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
            logger.info("Loaded OTEL collector processor", endpoint=endpoint)
        except Exception as e:
            logger.error("Failed to create OTEL collector processor", error=str(e))

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

        with self._lock:
            # Collect old providers for shutdown
            old_providers = list(self._hash_to_provider.values())

            # Swap in new maps
            self._agent_id_to_processors = new_map
            self._global_processors = new_global
            self._hash_to_provider = temp_hash_to_provider

        # Shutdown old providers (may still flush pending spans)
        self._shutdown_providers(old_providers)

        logger.info(
            "Reloaded observability integrations",
            agent_count=len(agent_ids),
            integration_count=len(integrations),
            unique_provider_count=len(temp_hash_to_provider),
            global_processor_count=len(new_global),
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

    def shutdown(self):
        """Shutdown collector + all providers.

        WARNING: Not thread-safe with active span processing!
        If spans are actively flowing through on_start/on_end, calling this
        may cause errors as processors are shut down mid-use.

        Only call during application shutdown or in tests (via reset_instance).
        """
        logger.debug("Shutting down OtelOrchestrator")

        # Shutdown collector processor directly (not managed by provider)
        if self._collector_processor:
            try:
                self._collector_processor.shutdown()
            except Exception as e:
                logger.error("Error shutting down collector processor", error=str(e))

        # Shutdown all providers
        with self._lock:
            providers = list(self._hash_to_provider.values())
            self._hash_to_provider.clear()
            self._agent_id_to_processors.clear()
            self._global_processors.clear()

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
