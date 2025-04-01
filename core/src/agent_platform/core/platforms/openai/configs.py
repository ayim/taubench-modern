from dataclasses import dataclass, field
from typing import ClassVar

from agent_platform.core.configurations import Configuration, MapConfiguration
from agent_platform.core.platforms.base import PlatformConfigs


@dataclass(frozen=True)
class OpenAIModelMap(MapConfiguration):
    """A map of our model names to OpenAI model IDs."""

    mapping: ClassVar[dict[str, str]] = {
        "gpt-4o": "gpt-4o-2024-08-06",
        "gpt-4o-mini": "gpt-4o-mini-2024-07-18",
        "gpt-4-turbo": "gpt-4-turbo-2024-04-09",
        "gpt-3.5-turbo": "gpt-3.5-turbo-0125",
        # Embedding models
        "text-embedding-3-small": "text-embedding-3-small",
        "text-embedding-3-large": "text-embedding-3-large",
        "text-embedding-ada-002": "text-embedding-ada-002",
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

    DEFAULT_MODEL: str = field(
        default="gpt-4o",
    )


@dataclass(frozen=True)
class OpenAIPlatformConfigs(PlatformConfigs):
    """The configs for the OpenAI platform."""

    default_platform_provider: dict[str, str] = field(
        default_factory=lambda: {
            "llm": "openai",
            "embedding": "openai",
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
            "openai": OpenAIModelMap.supported_models(),
        },
        metadata={"description": "The supported models by provider."},
    )
    """The supported models by provider."""
