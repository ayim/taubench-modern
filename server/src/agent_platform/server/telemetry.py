from dataclasses import dataclass, field

import structlog
from agent_platform import server
from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from agent_platform.core.conditional_langsmith_processor import ConditionalLangSmithProcessor
from agent_platform.core.configurations import Configuration, FieldMetadata

logger = structlog.get_logger(__name__)

# Global variables to store providers
_tracer_provider = None
_meter_provider = None


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


# TODO: Make this more configurable (export interval, etc.). Make sure we're using the
# appropriate OTEL implementation classes.
def setup_telemetry():
    """Set up OpenTelemetry for the server

    This function configures and returns the global tracer and meter providers
    that will be used by AgentServerContext.
    """
    collector_url = OTELConfig.collector_url
    otel_enabled = OTELConfig.is_enabled
    collector_url_set = True

    if not otel_enabled:
        logger.info("OTEL v2 is not enabled. Using no-op providers.")
        # We still need to use the global providers, but they'll be no-ops
        _tracer_provider = trace.get_tracer_provider()
        _meter_provider = metrics.get_meter_provider()
        return _tracer_provider, _meter_provider

    # Validate collector URL before proceeding
    if not collector_url or not collector_url.strip():
        logger.warning("OTEL is enabled but collector_url is empty.")
        collector_url_set = False

    # Ensure collector_url has proper scheme
    if collector_url_set and not collector_url.startswith(("http://", "https://")):
        logger.warning(f"Collector URL '{collector_url}' missing scheme. Adding http://")
        collector_url = f"http://{collector_url}"

    logger.info("Setting up OTEL v2")
    logger.info(f"Collector URL: {collector_url}")
    # Set up resource with service info
    logger.info(f"Service version: {server.__version__}")
    resource = Resource(
        attributes={
            "service.name": "sema4ai.agent_server",
            "service.version": server.__version__,
        }
    )

    # Create and configure trace provider
    _tracer_provider = TracerProvider(resource=resource)

    try:
        if collector_url_set:
            otlp_trace_exporter = OTLPSpanExporter(endpoint=f"{collector_url}/v1/traces")
            span_processor = BatchSpanProcessor(otlp_trace_exporter)
            _tracer_provider.add_span_processor(span_processor)
            logger.info(f"Successfully configured trace exporter for {collector_url}/v1/traces")
        else:
            logger.warning("Collector URL is not set. Skipping trace exporter configuration.")
    except Exception as e:
        logger.error(f"Failed to create trace exporter for {collector_url}/v1/traces: {e}")

    # Initialize and add the conditional LangSmith processor
    langsmith_processor = ConditionalLangSmithProcessor.get_instance()
    _tracer_provider.add_span_processor(langsmith_processor)
    logger.debug("Added ConditionalLangSmithProcessor to global trace provider")

    # Important: Set as the global tracer provider so AgentServerContext can use it
    trace.set_tracer_provider(_tracer_provider)

    # Create and configure meter provider
    try:
        if collector_url_set:
            otlp_metric_exporter = OTLPMetricExporter(endpoint=f"{collector_url}/v1/metrics")
            reader = PeriodicExportingMetricReader(
                exporter=otlp_metric_exporter,
                export_interval_millis=15000,
            )
            _meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
            logger.info(f"Successfully configured metric exporter for {collector_url}/v1/metrics")
        else:
            logger.warning("Collector URL is not set. Skipping metric exporter configuration.")
            _meter_provider = MeterProvider(resource=resource)
    except Exception as e:
        logger.error(f"Failed to create metric exporter for {collector_url}/v1/metrics: {e}")
        # Use basic meter provider without OTLP export if metrics export fails
        _meter_provider = MeterProvider(resource=resource)

    # Important: Set as the global meter provider so AgentServerContext can use it
    metrics.set_meter_provider(_meter_provider)

    logger.info("OTEL v2 setup complete")
    return _tracer_provider, _meter_provider
