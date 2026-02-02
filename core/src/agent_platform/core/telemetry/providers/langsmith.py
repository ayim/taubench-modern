"""LangSmith OTEL provider implementation."""

from typing import TYPE_CHECKING

from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

from agent_platform.core.telemetry.providers.base import OtelProvider

if TYPE_CHECKING:
    from agent_platform.core.integrations.observability.models import LangSmithObservabilitySettings


class LangSmithProvider(OtelProvider):
    """OTEL provider for LangSmith.

    Creates and manages BatchSpanProcessor for exporting traces to LangSmith
    using OTLP over HTTP.

    Supports: TRACES
    """

    def __init__(self, settings: "LangSmithObservabilitySettings") -> None:
        """Initialize LangSmith provider.

        Args:
            settings: LangSmithObservabilitySettings with endpoint and credentials
        """
        super().__init__()
        self._settings = settings

    def _create_trace_exporter(self) -> OTLPSpanExporter:
        """Create an OTLPSpanExporter for LangSmith traces.

        Returns:
            Configured OTLPSpanExporter ready for use
        """
        from agent_platform.core.network.utils import build_network_session
        from agent_platform.core.utils import SecretString

        endpoint = self._settings.url.rstrip("/")
        if not endpoint.endswith("/otel/v1/traces"):
            endpoint = f"{endpoint}/otel/v1/traces"

        api_key = (
            self._settings.api_key.get_secret_value()
            if isinstance(self._settings.api_key, SecretString)
            else self._settings.api_key
        )
        headers = {
            "x-api-key": api_key,
            "Langsmith-Project": self._settings.project_name,
        }

        return OTLPSpanExporter(
            endpoint=endpoint,
            headers=headers,
            session=build_network_session(),
        )

    @property
    def provider_kind(self) -> str:
        """Return the provider kind identifier."""
        return "langsmith"
