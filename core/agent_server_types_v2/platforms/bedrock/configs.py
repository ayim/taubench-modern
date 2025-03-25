from dataclasses import dataclass, field

from agent_server_types_v2.configurations import Configuration, MapConfiguration
from agent_server_types_v2.platforms.base import PlatformConfigs


@dataclass(frozen=True)
class BedrockContentLimits(Configuration):
    """Content limits and associated global configurations for the Bedrock platform."""

    MAX_IMAGE_COUNT: int = 20
    MAX_IMAGE_SIZE: int = 3_750_000  # 3.75MB
    MAX_IMAGE_HEIGHT: int = 8_000
    MAX_IMAGE_WIDTH: int = 8_000
    MAX_DOCUMENT_COUNT: int = 5
    MAX_DOCUMENT_SIZE: int = 4_500_000  # 4.5MB


@dataclass(frozen=True)
class BedrockModelMap(MapConfiguration):
    """A map of our model names to Bedrock model IDs."""

    mapping: dict[str, str] = field(
        default_factory=lambda: {
            "claude-3-5-sonnet": "us.anthropic.claude-3-5-sonnet-20241022-v2:0",
            "claude-3-5-haiku": "us.anthropic.claude-3-haiku-20240307-v1:0",
        },
    )

    @classmethod
    def supported_models(cls) -> list[str]:
        """Get list of supported model names."""
        return list(super().__class_getitem__("MODEL_MAP").keys())


@dataclass(frozen=True)
class BedrockRoleMap(MapConfiguration):
    """A map of Bedrock role names to our role names."""

    mapping: dict[str, str] = field(
        default_factory=lambda: {"user": "user", "assistant": "agent"},
    )


@dataclass(frozen=True)
class BedrockDefaultModel(Configuration):
    """The default model to use for the Bedrock platform."""

    DEFAULT_MODEL: str = field(
        default="claude-3-5-sonnet",
    )


@dataclass(frozen=True)
class BedrockMimeTypeMap(MapConfiguration):
    """A map of Bedrock format types to MIME types supported by the platform."""

    mapping: dict[str, str] = field(
        default_factory=lambda: {
            "jpeg": "image/jpeg",
            "png": "image/png",
            "gif": "image/gif",
            "webp": "image/webp",
            "pdf": "application/pdf",
            "txt": "text/plain",
            "csv": "text/csv",
            "md": "text/markdown",
            "html": "text/html",
            "xls": "application/vnd.ms-excel",
            "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "doc": "application/msword",
            "docx": "application/"
            "vnd.openxmlformats-officedocument.wordprocessingml.document",
        },
    )

    @classmethod
    def supported_format_types(cls) -> list[str]:
        """Get list of supported format types."""
        return list(super().__class_getitem__("mapping").keys())


@dataclass(frozen=True)
class BedrockPlatformConfigs(PlatformConfigs):
    """The configs for the Bedrock platform."""

    default_platform_provider: str = field(
        default="anthropic",
        metadata={"description": "The default platform provider."},
    )
    """The default platform provider."""

    default_model_type: str = field(
        default="llm",
        metadata={"description": "The default model type."},
    )
    """The default model type."""

    default_quality_tier: str = field(
        default="balanced",
        metadata={"description": "The default quality tier."},
    )
    """The default quality tier."""

    supported_models_by_provider: dict[str, list[str]] = field(
        default_factory=lambda: {
            "anthropic": [
                "claude-3-5-sonnet",
                "claude-3-5-haiku",
            ],
        },
        metadata={"description": "The supported models by provider."},
    )
    """The supported models by provider."""
