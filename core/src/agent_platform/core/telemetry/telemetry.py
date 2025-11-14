"""OpenTelemetry configuration."""

from dataclasses import dataclass, field

from agent_platform.core.configurations import Configuration, FieldMetadata


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
