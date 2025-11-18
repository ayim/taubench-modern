from pathlib import Path


def config_local_tracer_provider(tracer_provider, output_dir: Path) -> None:
    """
    Configure the trace provider to export traces to a local directory.

    Args:
        tracer_provider: The (otel) tracer provider to configure.
        output_dir: The directory to export traces to.
    """
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor

    from agent_platform.server.telemetry.dir_span_exporter import DirSpanExporter

    dir_exporter = DirSpanExporter(output_dir=output_dir)
    tracer_provider.add_span_processor(SimpleSpanProcessor(dir_exporter))
