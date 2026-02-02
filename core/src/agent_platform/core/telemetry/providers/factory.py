"""Factory for creating OTEL providers from settings."""

from typing import TYPE_CHECKING

import structlog

from agent_platform.core.telemetry.providers.base import OtelProvider
from agent_platform.core.telemetry.providers.grafana import GrafanaProvider
from agent_platform.core.telemetry.providers.langsmith import LangSmithProvider
from agent_platform.core.telemetry.providers.otlp_basic_auth import OtlpBasicAuthProvider
from agent_platform.core.telemetry.providers.otlp_custom_headers import OtlpCustomHeadersProvider

if TYPE_CHECKING:
    from agent_platform.core.integrations.observability.models import ObservabilitySettings

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# Provider registry mapping kind strings to provider classes.
# To add a new provider:
# 1. Create a new provider class in this package (e.g., my_provider.py)
# 2. Add an import and registry entry here
# 3. Add corresponding settings class to models.PROVIDER_SETTINGS
_PROVIDER_REGISTRY: dict[str, type[OtelProvider]] = {
    "grafana": GrafanaProvider,
    "langsmith": LangSmithProvider,
    "otlp_basic_auth": OtlpBasicAuthProvider,
    "otlp_custom_headers": OtlpCustomHeadersProvider,
}


class OtelProviderFactory:
    """Factory for creating OtelProvider instances from observability settings.

    Uses a registry pattern to map provider kinds to their implementation classes.
    """

    @staticmethod
    def create(settings: "ObservabilitySettings") -> OtelProvider:
        """Create an OtelProvider from observability settings.

        Args:
            settings: ObservabilitySettings containing provider configuration

        Returns:
            OtelProvider instance configured for the specified backend

        Raises:
            ValueError: If the provider kind is not supported
        """
        provider_kind = settings.kind

        if provider_kind not in _PROVIDER_REGISTRY:
            raise ValueError(f"Unsupported provider kind: {provider_kind}")

        provider_class = _PROVIDER_REGISTRY[provider_kind]
        logger.debug("Creating provider", provider_kind=provider_kind)
        # Type ignore: provider_class expects its specific settings type, but we've validated
        # the kind matches the settings type above via the registry lookup
        return provider_class(settings.provider_settings)  # type: ignore[arg-type]
