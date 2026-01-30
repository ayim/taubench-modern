"""OTLP Custom Headers provider implementation."""

from typing import TYPE_CHECKING

from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

from agent_platform.core.telemetry.providers.base import OtelProvider

if TYPE_CHECKING:
    from agent_platform.core.integrations.observability.models import OtlpCustomHeadersObservabilitySettings


class OtlpCustomHeadersProvider(OtelProvider):
    """OTEL provider for generic OTLP endpoints with custom headers.

    Creates and manages BatchSpanProcessor for exporting traces to any
    OTLP-compatible endpoint using custom HTTP headers for authentication.

    Supports: TRACES
    """

    def __init__(self, settings: "OtlpCustomHeadersObservabilitySettings") -> None:
        """Initialize OTLP Custom Headers provider.

        Args:
            settings: OtlpCustomHeadersObservabilitySettings with endpoint and headers
        """
        super().__init__()
        self._settings = settings

    def _create_trace_exporter(self) -> OTLPSpanExporter:
        """Create an OTLPSpanExporter for traces.

        Returns:
            Configured OTLPSpanExporter ready for use
        """
        from agent_platform.core.network.utils import build_network_session

        endpoint = self._settings.url.rstrip("/")
        if not endpoint.endswith("/v1/traces"):
            endpoint = f"{endpoint}/v1/traces"

        return OTLPSpanExporter(
            endpoint=endpoint,
            headers=self._settings.headers,
            session=build_network_session(),
        )

    @property
    def provider_kind(self) -> str:
        """Return the provider kind identifier."""
        return "otlp_custom_headers"
