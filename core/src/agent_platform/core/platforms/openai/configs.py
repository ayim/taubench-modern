from dataclasses import dataclass, field
from typing import ClassVar

from agent_platform.core.configurations import Configuration, MapConfiguration
from agent_platform.core.platforms.base import PlatformConfigs


# TODO: Verify content limits
@dataclass(frozen=True)
class OpenAIContentLimits(Configuration):
    """Content limits and associated global configurations for the OpenAI platform."""

    MAX_IMAGE_COUNT: int = 20
    MAX_IMAGE_SIZE: int = 3_750_000  # 3.75MB
    MAX_IMAGE_HEIGHT: int = 8_000
    MAX_IMAGE_WIDTH: int = 8_000
    MAX_DOCUMENT_COUNT: int = 5
    MAX_DOCUMENT_SIZE: int = 4_500_000  # 4.5MB


@dataclass(frozen=True)
class OpenAIModelMap(MapConfiguration):
    """A map of our model names to OpenAI model configurations."""

    mapping: ClassVar[dict[str, str]] = {
        # LLM models
        "gpt-4": "gpt-4",
        "gpt-4-turbo": "gpt-4-turbo",
        "gpt-3.5-turbo": "gpt-3.5-turbo",
        # Embedding models
        "text-embedding-ada-002": "text-embedding-ada-002",
        "text-embedding-ada-002-v2": "text-embedding-ada-002-v2",
        "text-embedding-ada-002-v3": "text-embedding-ada-002-v3",
    }

    @classmethod
    def supported_models(cls) -> list[str]:
        """Get list of supported model names."""
        return list(cls.class_keys())


@dataclass(frozen=True)
class OpenAIRoleMap(MapConfiguration):
    """A map of OpenAI role names to our role names."""

    mapping: ClassVar[dict[str, str]] = {
        "user": "user",
        "assistant": "agent",
    }


@dataclass(frozen=True)
class OpenAIDefaultModel(Configuration):
    """The default model to use for the OpenAI platform."""

    DEFAULT_MODEL: str = "gpt-4-turbo"


# TODO: Verify mime type map
@dataclass(frozen=True)
class OpenAIMimeTypeMap(MapConfiguration):
    """A map of OpenAI format types to MIME types supported by the platform."""

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

    @classmethod
    def reverse_mapping(cls) -> dict[str, str]:
        """Get reverse mapping of MIME types to format types."""
        return {v: k for k, v in cls.mapping.items()}


@dataclass(frozen=True)
class OpenAIPlatformConfigs(PlatformConfigs):
    """The configs for the OpenAI platform."""

    default_platform_provider: dict[str, str] = field(
        default_factory=lambda: {
            "llm": "openai",
            "embedding": "openai",
        },
        metadata={"description": "The default platform provider by model type."},
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
        metadata={"description": "The default quality tier by model type."},
    )
    """The default quality tier by model type."""

    supported_models_by_provider: dict[str, list[str]] = field(
        default_factory=lambda: {
            "openai": [
                "gpt-4",
                "gpt-4-turbo",
                "gpt-3.5-turbo",
            ],
        },
        metadata={"description": "The supported models by provider."},
    )
    """The supported models by provider."""
