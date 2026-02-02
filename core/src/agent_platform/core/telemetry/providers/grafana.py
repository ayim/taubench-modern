"""Grafana Cloud OTEL provider implementation."""

import base64
from typing import TYPE_CHECKING

from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

from agent_platform.core.telemetry.providers.base import OtelProvider

if TYPE_CHECKING:
    from agent_platform.core.integrations.observability.models import GrafanaObservabilitySettings


class GrafanaProvider(OtelProvider):
    """OTEL provider for Grafana Cloud.

    Creates and manages BatchSpanProcessor for exporting traces to Grafana Cloud
    using OTLP over HTTP with Basic Auth.

    Supports: TRACES
    """

    def __init__(self, settings: "GrafanaObservabilitySettings") -> None:
        """Initialize Grafana provider.

        Args:
            settings: GrafanaObservabilitySettings with endpoint and credentials
        """
        super().__init__()
        self._settings = settings

    def _build_auth_headers(self) -> dict[str, str]:
        """Build authentication headers for Grafana Cloud.

        Constructs Basic Auth header from grafana_instance_id and api_token,
        then merges any additional_headers from settings.

        Returns:
            Headers dict with Basic Auth and any additional headers
        """
        from agent_platform.core.utils import SecretString

        api_key = (
            self._settings.api_token.get_secret_value()
            if isinstance(self._settings.api_token, SecretString)
            else self._settings.api_token
        )
        basic_auth_value = base64.b64encode(f"{self._settings.grafana_instance_id}:{api_key}".encode()).decode()
        headers = {"Authorization": f"Basic {basic_auth_value}"}

        if self._settings.additional_headers:
            headers.update(self._settings.additional_headers)

        return headers

    def _create_trace_exporter(self) -> OTLPSpanExporter:
        """Create an OTLPSpanExporter for Grafana traces.

        Returns:
            Configured OTLPSpanExporter ready for use
        """
        from agent_platform.core.network.utils import build_network_session

        endpoint = self._settings.url.rstrip("/")
        if not endpoint.endswith("/v1/traces"):
            endpoint = f"{endpoint}/v1/traces"

        return OTLPSpanExporter(
            endpoint=endpoint,
            headers=self._build_auth_headers(),
            session=build_network_session(),
        )

    @property
    def provider_kind(self) -> str:
        """Return the provider kind identifier."""
        return "grafana"
