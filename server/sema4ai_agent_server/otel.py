import os
from typing import Optional

import structlog
from opentelemetry import metrics
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource

from sema4ai_agent_server.server import VERSION

logger = structlog.get_logger(__name__)


def get_otel_collector_url() -> Optional[str]:
    return os.getenv("OTEL_COLLECTOR_URL")


def otel_is_enabled() -> bool:
    return get_otel_collector_url() is not None


def setup_otel() -> None:
    if not otel_is_enabled():
        logger.info("OTEL is not enabled. Skipping setup.")
        return

    logger.info("Setting up OTEL")

    otel_collector_url = get_otel_collector_url()
    resource = Resource(
        attributes={"service.name": "agent-server", "service.version": VERSION}
    )
    otlp_exporter = OTLPMetricExporter(endpoint=f"{otel_collector_url}/v1/metrics")
    reader = PeriodicExportingMetricReader(
        exporter=otlp_exporter, export_interval_millis=15000
    )
    meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
    metrics.set_meter_provider(meter_provider)

    logger.info("OTEL setup complete")
