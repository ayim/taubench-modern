import os
from dataclasses import dataclass, field

import structlog
from opentelemetry import metrics
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from traceloop.sdk import Traceloop

from agent_platform.core.configurations import Configuration, FieldMetadata

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class OTELConfig(Configuration):
    """Configuration for OpenTelemetry."""

    collector_url: str = field(
        default="",
        metadata=FieldMetadata(
            description="The URL of the OpenTelemetry collector.",
            env_vars=["SEMA4AI_AGENT_SERVER_OTEL_COLLECTOR_URL", "OTEL_COLLECTOR_URL"],
        ),
    )
    is_enabled: bool = field(
        default=False,
        metadata=FieldMetadata(
            description="Whether to enable OpenTelemetry.",
            env_vars=["SEMA4AI_AGENT_SERVER_OTEL_ENABLED", "OTEL_ENABLED"],
        ),
    )


def setup_otel() -> None:
    if not OTELConfig.is_enabled:
        logger.info("OTEL is not enabled. Skipping setup.")
        return

    from agent_platform.server import __version__

    logger.info("Setting up OTEL")

    otel_collector_url = OTELConfig.collector_url

    # OpenLLMetry setup
    if otel_collector_url:
        os.environ["TRACELOOP_BASE_URL"] = otel_collector_url

    Traceloop.init()

    resource = Resource(
        attributes={"service.name": "agent-server", "service.version": __version__},
    )
    otlp_exporter = OTLPMetricExporter(endpoint=f"{otel_collector_url}/v1/metrics")
    reader = PeriodicExportingMetricReader(
        exporter=otlp_exporter,
        export_interval_millis=15000,
    )
    meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
    metrics.set_meter_provider(meter_provider)
    logger.info("OTEL setup complete")
