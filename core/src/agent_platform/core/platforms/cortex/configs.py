from dataclasses import dataclass, field
from typing import ClassVar

from agent_platform.core.configurations import Configuration, MapConfiguration
from agent_platform.core.platforms.base import PlatformConfigs


@dataclass(frozen=True)
class CortexModelMap(MapConfiguration):
    """A map of our model names to Cortex model IDs."""

    mapping: ClassVar[dict[str, str]] = {
        # LLM models
        "claude-3-5-sonnet": "claude-3-5-sonnet",
        "deepseek-r1": "deepseek-r1",
        "llama-3-1-8b": "llama3.1-8b",
        "llama-3-1-70b": "llama3.1-70b",
        "snowflake-llama-3-3-70b": "snowflake-llama-3.3-70b",
        # Embedding models
        "snowflake-arctic-embed-m": "snowflake-arctic-embed-m-v1.5",
        "snowflake-arctic-embed-l": "snowflake-arctic-embed-l-v2.0",
        "voyage-multilingual": "voyage-multilingual-2",
    }

    @classmethod
    def supported_models(cls) -> list[str]:
        """Get list of supported model names."""
        return list(cls.class_keys())


@dataclass(frozen=True)
class CortexRoleMap(MapConfiguration):
    """A map of Cortex role names to our role names."""

    mapping: ClassVar[dict[str, str]] = {
        "user": "user",
        "assistant": "agent",
    }


@dataclass(frozen=True)
class CortexDefaultModel(Configuration):
    """The default model to use for the Cortex platform."""

    DEFAULT_MODEL: str = field(
        default="claude-3-5-sonnet",
    )


@dataclass(frozen=True)
class CortexPlatformConfigs(PlatformConfigs):
    """The configs for the Cortex platform."""

    default_platform_provider: dict[str, str] = field(
        default_factory=lambda: {
            "llm": "anthropic",
            "embedding": "snowflake",
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
        # TODO: does this need model type refinement?
        # provider + type -> model
        default_factory=lambda: {
            "anthropic": [
                "claude-3-5-sonnet",
            ],
            "snowflake": [
                "snowflake-llama-3-3-70b",
                "snowflake-arctic-embed-m",
                "snowflake-arctic-embed-l",
            ],
            "voyage": [
                "voyage-multilingual",
            ],
            "meta": [
                "llama-3-1-8b",
            ],
            "deepseek": [
                "deepseek-r1",
            ],
        },
        metadata={"description": "The supported models by provider."},
    )
    """The supported models by provider."""
