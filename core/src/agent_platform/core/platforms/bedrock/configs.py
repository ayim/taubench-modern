from dataclasses import dataclass, field
from typing import ClassVar

from agent_platform.core.configurations import Configuration, MapConfiguration
from agent_platform.core.platforms.base import PlatformConfigs


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

    mapping: ClassVar[dict[str, str]] = {
        # LLM models
        "claude-3-5-sonnet": "us.anthropic.claude-3-5-sonnet-20241022-v2:0",
        "claude-3-5-haiku": "us.anthropic.claude-3-haiku-20240307-v1:0",
        # Embedding models
        "titan-embed-text-v2": "amazon.titan-embed-text-v2:0",
        "titan-embed-text-v1": "amazon.titan-embed-text-v1",
        "cohere-embed-english-v3": "cohere.embed-english-v3",
        "cohere-embed-multilingual-v3": "cohere.embed-multilingual-v3",
    }

    @classmethod
    def supported_models(cls) -> list[str]:
        """Get list of supported model names."""
        return list(cls.class_keys())


@dataclass(frozen=True)
class BedrockRoleMap(MapConfiguration):
    """A map of Bedrock role names to our role names."""

    mapping: ClassVar[dict[str, str]] = {
        "user": "user",
        "assistant": "agent",
    }


@dataclass(frozen=True)
class BedrockDefaultModel(Configuration):
    """The default model to use for the Bedrock platform."""

    DEFAULT_MODEL: str = field(
        default="claude-3-5-sonnet",
    )


@dataclass(frozen=True)
class BedrockMimeTypeMap(MapConfiguration):
    """A map of Bedrock format types to MIME types supported by the platform."""

    mapping: ClassVar[dict[str, str]] = {
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
    }

    @classmethod
    def supported_format_types(cls) -> list[str]:
        """Get list of supported format types."""
        return list(cls.class_keys())


@dataclass(frozen=True)
class BedrockPlatformConfigs(PlatformConfigs):
    """The configs for the Bedrock platform."""

    default_platform_provider: dict[str, str] = field(
        default_factory=lambda: {
            "llm": "anthropic",
            "embedding": "amazon",
        },
        metadata={
            "description": "The default platform provider by model type.",
        },
    )
    """The default platform provider by model type."""

    default_model_type: str = field(
        default="llm",
        metadata={"description": "The default model type."},
    )
    """The default model type."""

    default_quality_tier: dict[str, str] = field(
        default_factory=lambda: {
            "llm": "balanced",
            "embedding": "balanced",
        },
        metadata={
            "description": "The default quality tier by model type.",
        },
    )
    """The default quality tier by model type."""

    supported_models_by_provider: dict[str, list[str]] = field(
        default_factory=lambda: {
            "anthropic": [
                "claude-3-5-sonnet",
                "claude-3-5-haiku",
            ],
            "amazon": [
                "titan-embed-text-v2",
                "titan-embed-text-v1",
            ],
            "cohere": [
                "cohere-embed-english-v3",
                "cohere-embed-multilingual-v3",
            ],
        },
        metadata={"description": "The supported models by provider."},
    )
    """The supported models by provider."""
