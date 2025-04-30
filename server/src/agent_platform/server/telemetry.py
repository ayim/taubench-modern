import os

import structlog
from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

logger = structlog.get_logger(__name__)

# Global variables to store providers
_tracer_provider = None
_meter_provider = None


# TODO: Make this more configurable (export interval, etc.). Make sure we're using the
# appropriate OTEL implementation classes.
def setup_telemetry():
    """Set up OpenTelemetry for the server

    This function configures and returns the global tracer and meter providers
    that will be used by AgentServerContext.
    """

    otel_enabled = os.environ.get("OTEL_V2_ENABLED", "").lower() == "true"
    collector_url = os.environ.get("OTEL_V2_COLLECTOR_URL", "http://localhost:4318")

    if not otel_enabled:
        logger.info("OTEL v2 is not enabled. Using no-op providers.")
        # We still need to use the global providers, but they'll be no-ops
        _tracer_provider = trace.get_tracer_provider()
        _meter_provider = metrics.get_meter_provider()
        return _tracer_provider, _meter_provider

    logger.info("Setting up OTEL v2")

    # Set up resource with service info
    # TODO: pull version from versionbump controlled constant
    resource = Resource(
        attributes={"service.name": "agent-server-v2", "service.version": "2.0.0"}
    )

    # Create and configure trace provider
    _tracer_provider = TracerProvider(resource=resource)
    otlp_trace_exporter = OTLPSpanExporter(endpoint=f"{collector_url}/v1/traces")
    span_processor = BatchSpanProcessor(otlp_trace_exporter)
    _tracer_provider.add_span_processor(span_processor)

    # Important: Set as the global tracer provider so AgentServerContext can use it
    trace.set_tracer_provider(_tracer_provider)

    # Create and configure meter provider
    otlp_metric_exporter = OTLPMetricExporter(endpoint=f"{collector_url}/v1/metrics")
    reader = PeriodicExportingMetricReader(
        exporter=otlp_metric_exporter,
        export_interval_millis=15000,
    )
    _meter_provider = MeterProvider(resource=resource, metric_readers=[reader])

    # Important: Set as the global meter provider so AgentServerContext can use it
    metrics.set_meter_provider(_meter_provider)

    logger.info("OTEL v2 setup complete")
    return _tracer_provider, _meter_provider
