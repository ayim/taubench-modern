"""Helper functions for OTEL orchestrator."""

from typing import TYPE_CHECKING

import structlog
from opentelemetry.sdk.trace.export import BatchSpanProcessor

if TYPE_CHECKING:
    from agent_platform.core.integrations.integration_scope import IntegrationScope
    from agent_platform.core.integrations.observability.integration import ObservabilityIntegration

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
