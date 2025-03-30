import os

import structlog
from opentelemetry import metrics
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from traceloop.sdk import Traceloop

from agent_platform.server.env_vars import OTEL_COLLECTOR_URL

logger = structlog.get_logger(__name__)


def get_otel_collector_url() -> str | None:
    return OTEL_COLLECTOR_URL


def otel_is_enabled() -> bool:
    return get_otel_collector_url() is not None


def setup_otel() -> None:
    if not otel_is_enabled():
        logger.info("OTEL is not enabled. Skipping setup.")
        return

    from agent_platform.server import __version__

    logger.info("Setting up OTEL")

    otel_collector_url = get_otel_collector_url()

    # OpenLLMetry setup
    if otel_collector_url:
        os.environ["TRACELOOP_BASE_URL"] = otel_collector_url

    Traceloop.init()

    resource = Resource(
        attributes={"service.name": "agent-server", "service.version": __version__},
    )
    otlp_exporter = OTLPMetricExporter(endpoint=f"{otel_collector_url}/v1/metrics")
    reader = PeriodicExportingMetricReader(
        exporter=otlp_exporter, export_interval_millis=15000,
    )
    meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
    metrics.set_meter_provider(meter_provider)
    logger.info("OTEL setup complete")
