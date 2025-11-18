from pathlib import Path

import structlog
from agent_platform import server

logger = structlog.get_logger(__name__)


def setup_telemetry(agent_trace_dir: Path | None = None):  # noqa: PLR0915
    """Set up OpenTelemetry for the server

    This function configures and returns the global tracer and meter providers
    that will be used by AgentServerContext.
    """
    from opentelemetry import metrics, trace
    from opentelemetry.sdk.trace import TracerProvider

    from agent_platform.core.telemetry.telemetry import OTELConfig
    from agent_platform.server.telemetry.config_local_tracer import config_local_tracer_provider

    collector_url = OTELConfig.collector_url
    otel_enabled = OTELConfig.is_enabled
    collector_url_set = True

    if not otel_enabled:
        logger.info("OTEL v2 is not enabled. Using no-op providers.")
        # We still need to use the global providers, but they'll be no-ops
        tracer_provider = TracerProvider()
        if agent_trace_dir is not None:
            config_local_tracer_provider(tracer_provider, output_dir=Path(agent_trace_dir))
            logger.info(f"Added local agent tracer provider. Directory: {agent_trace_dir}")

        trace.set_tracer_provider(tracer_provider)

        meter_provider = metrics.get_meter_provider()
        return tracer_provider, meter_provider

    from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import Resource

    from agent_platform.core.conditional_langsmith_processor import ConditionalLangSmithProcessor
    from agent_platform.core.otel_orchestrator import OtelOrchestrator

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
    resource = Resource.create(
        attributes={
            "service.name": "sema4ai.agent_server",
            "service.version": server.__version__,
        }
    )

    # Create and configure trace provider
    tracer_provider = TracerProvider(resource=resource)

    # Initialize and add the OtelOrchestrator
    # (handles collector and global observability integrations from DB)
    orchestrator = OtelOrchestrator.get_instance()
    tracer_provider.add_span_processor(orchestrator)
    logger.info("Added OtelOrchestrator to global trace provider")

    # Initialize and add ConditionalLangSmithProcessor for backward compatibility
    # (handles per-agent observability_configs until fully migrated to orchestrator)
    langsmith_processor = ConditionalLangSmithProcessor.get_instance()
    tracer_provider.add_span_processor(langsmith_processor)
    logger.debug("Added ConditionalLangSmithProcessor for per-agent configs")

    if agent_trace_dir is not None:
        config_local_tracer_provider(tracer_provider, output_dir=Path(agent_trace_dir))
        logger.info(f"Added local agent tracer provider. Directory: {agent_trace_dir}")

    # Important: Set as the global tracer provider so AgentServerContext can use it
    trace.set_tracer_provider(tracer_provider)

    # Create and configure meter provider
    try:
        if collector_url_set:
            otlp_metric_exporter = OTLPMetricExporter(endpoint=f"{collector_url}/v1/metrics")
            reader = PeriodicExportingMetricReader(
                exporter=otlp_metric_exporter,
                export_interval_millis=15000,
            )
            meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
            logger.info(f"Successfully configured metric exporter for {collector_url}/v1/metrics")
        else:
            logger.warning("Collector URL is not set. Skipping metric exporter configuration.")
            meter_provider = MeterProvider(resource=resource)
    except Exception as e:
        logger.error(f"Failed to create metric exporter for {collector_url}/v1/metrics: {e}")
        # Use basic meter provider without OTLP export if metrics export fails
        meter_provider = MeterProvider(resource=resource)

    # Important: Set as the global meter provider so AgentServerContext can use it
    metrics.set_meter_provider(meter_provider)

    logger.info("OTEL v2 setup complete")
    return tracer_provider, meter_provider
