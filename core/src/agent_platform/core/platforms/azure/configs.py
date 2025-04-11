from dataclasses import dataclass, field
from typing import ClassVar

from agent_platform.core.configurations import Configuration, MapConfiguration
from agent_platform.core.platforms.base import PlatformConfigs


@dataclass(frozen=True)
class AzureOpenAIModelMap(MapConfiguration):
    """A map of our model names to Azure OpenAI deployment IDs."""

    mapping: ClassVar[dict[str, str]] = {
        "gpt-4o": "gpt-4o",
        "gpt-4o-mini": "gpt-4o-mini",
        "gpt-4-turbo": "gpt-4-turbo",
        "gpt-3.5-turbo": "gpt-35-turbo",
        "o3-mini-high": "o3-mini",
        "o3-mini-low": "o3-mini",
        "o1-mini-high": "o1-mini",
        "o1-mini-low": "o1-mini",
        "o1-pro-high": "o1-pro",
        "o1-pro-low": "o1-pro",
        "o1-high": "o1",
        "o1-low": "o1",
        # Embedding models
        "text-embedding-3-small": "embedding-3-small",
        "text-embedding-3-large": "embedding-3-large",
        "text-embedding-ada-002": "embedding-ada",
    }

    @classmethod
    def supported_models(cls) -> list[str]:
        """Get list of supported model names."""
        return list(cls.class_keys())


@dataclass(frozen=True)
class AzureOpenAIRoleMap(MapConfiguration):
    """A map of OpenAI role names to our role names."""

    mapping: ClassVar[dict[str, str]] = {
        "user": "user",
        "assistant": "agent",
    }


@dataclass(frozen=True)
class AzureOpenAIDefaultModel(Configuration):
    """The default model to use for the Azure OpenAI platform."""

    DEFAULT_MODEL: str = field(
        default="gpt-4o",
    )


@dataclass(frozen=True)
class AzureOpenAIPlatformConfigs(PlatformConfigs):
    """The configs for the Azure OpenAI platform."""

    default_platform_provider: dict[str, str] = field(
        default_factory=lambda: {
            "llm": "azure",
            "embedding": "azure",
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
            "azure": AzureOpenAIModelMap.supported_models(),
        },
        metadata={"description": "The supported models by provider."},
    )
    """The supported models by provider."""
