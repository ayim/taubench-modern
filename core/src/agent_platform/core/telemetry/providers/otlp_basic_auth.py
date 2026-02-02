"""OTLP Basic Auth provider implementation."""

import base64
from typing import TYPE_CHECKING

import structlog
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

from agent_platform.core.telemetry.providers.base import OtelProvider

if TYPE_CHECKING:
    from opentelemetry.sdk.metrics.export import MetricExporter

    from agent_platform.core.integrations.observability.models import OtlpBasicAuthObservabilitySettings

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class OtlpBasicAuthProvider(OtelProvider):
    """OTEL provider for generic OTLP endpoints with Basic Authentication.

    Creates and manages handlers for exporting telemetry to any
    OTLP-compatible endpoint using HTTP Basic Auth.

    Supports: TRACES, METRICS
    """

    def __init__(self, settings: "OtlpBasicAuthObservabilitySettings") -> None:
        """Initialize OTLP Basic Auth provider.

        Args:
            settings: OtlpBasicAuthObservabilitySettings with endpoint and credentials
        """
        super().__init__()
        self._settings = settings
        self._metric_exporter: MetricExporter | None = None
        self._metric_initialized = False

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

    def _create_metric_exporter(self) -> "MetricExporter":
        """Create an OTLPMetricExporter for metrics.

        Returns:
            Configured OTLPMetricExporter ready for use
        """
        from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter

        from agent_platform.core.network.utils import build_network_session

        endpoint = self._settings.url.rstrip("/")
        if not endpoint.endswith("/v1/metrics"):
            endpoint = f"{endpoint}/v1/metrics"

        return OTLPMetricExporter(
            endpoint=endpoint,
            headers=self._build_auth_headers(),
            session=build_network_session(),
        )

    def _ensure_metric_initialized(self) -> None:
        """Lazily initialize the metric exporter on first access.

        Note: Not thread-safe. Caller (OtelOrchestrator) serializes access
        via reload lock, so concurrent calls are not possible in practice.
        """
        if self._metric_initialized:
            return

        self._metric_exporter = self._create_metric_exporter()
        self._metric_initialized = True
        logger.debug("Initialized OTLP Basic Auth metric exporter", url=self._settings.url)

    def get_metrics_exporter(self) -> "MetricExporter | None":
        """Return metrics handler.

        Returns:
            MetricExporter for metrics export
        """
        self._ensure_metric_initialized()
        return self._metric_exporter

    def shutdown(self) -> None:
        """Shutdown all handlers (trace processor and metric exporter)."""
        # Shutdown trace processor via base class
        super().shutdown()

        # Shutdown metric exporter
        if self._metric_exporter is not None:
            try:
                self._metric_exporter.shutdown()
                logger.debug("Shutdown OTLP Basic Auth metric exporter")
            except Exception as e:
                logger.error("Error shutting down OTLP Basic Auth metric exporter", error=str(e))
            finally:
                self._metric_exporter = None
                self._metric_initialized = False

    @property
    def provider_kind(self) -> str:
        """Return the provider kind identifier."""
        return "otlp_basic_auth"
