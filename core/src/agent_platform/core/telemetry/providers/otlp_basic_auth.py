"""OTLP Basic Auth provider implementation."""

import base64
from typing import TYPE_CHECKING

from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

from agent_platform.core.telemetry.providers.base import OtelProvider

if TYPE_CHECKING:
    from agent_platform.core.integrations.observability.models import OtlpBasicAuthObservabilitySettings


class OtlpBasicAuthProvider(OtelProvider):
    """OTEL provider for generic OTLP endpoints with Basic Authentication.

    Creates and manages BatchSpanProcessor for exporting traces to any
    OTLP-compatible endpoint using HTTP Basic Auth.

    Supports: TRACES
    """

    def __init__(self, settings: "OtlpBasicAuthObservabilitySettings") -> None:
        """Initialize OTLP Basic Auth provider.

        Args:
            settings: OtlpBasicAuthObservabilitySettings with endpoint and credentials
        """
        super().__init__()
        self._settings = settings

    def _build_auth_headers(self) -> dict[str, str]:
        """Build Basic Auth headers.

        Constructs Basic Auth header from username and password.

        Returns:
            Headers dict with Basic Auth
        """
        from agent_platform.core.utils import SecretString

        password = (
            self._settings.password.get_secret_value()
            if isinstance(self._settings.password, SecretString)
            else self._settings.password
        )
        basic_auth_value = base64.b64encode(f"{self._settings.username}:{password}".encode()).decode()
        return {"Authorization": f"Basic {basic_auth_value}"}

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
            headers=self._build_auth_headers(),
            session=build_network_session(),
        )

    @property
    def provider_kind(self) -> str:
        """Return the provider kind identifier."""
        return "otlp_basic_auth"
