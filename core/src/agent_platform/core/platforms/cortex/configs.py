from dataclasses import dataclass, field
from typing import ClassVar

from agent_platform.core.configurations import Configuration, MapConfiguration
from agent_platform.core.platforms.base import PlatformConfigs


@dataclass(frozen=True)
class CortexModelMap(MapConfiguration):
    """A map of our model names to Cortex model IDs."""

    mapping: ClassVar[dict[str, str]] = {
        # Anthropic
        "claude-3-5-sonnet": "claude-3-5-sonnet",
        # DeepSeek
        "deepseek-r1": "deepseek-r1",
        # Meta
        "llama-3-1-8b": "llama3.1-8b",
        "llama-3-1-70b": "llama3.1-70b",
        # Snowflake (LLM)
        "snowflake-llama-3-3-70b": "snowflake-llama-3.3-70b",
        # Snowflake (Embedding)
        "snowflake-arctic-embed-m": "snowflake-arctic-embed-m-v1.5",
        "snowflake-arctic-embed-l": "snowflake-arctic-embed-l-v2.0",
        # Voyage
        "voyage-multilingual": "voyage-multilingual-2",
    }

    models_to_type: ClassVar[dict[str, str]] = {
        # Anthropic
        "claude-3-5-sonnet": "llm",
        # DeepSeek
        "deepseek-r1": "llm",
        # Meta
        "llama-3-1-8b": "llm",
        "llama-3-1-70b": "llm",
        # Snowflake (LLM)
        "snowflake-llama-3-3-70b": "llm",
        # Snowflake (Embedding)
        "snowflake-arctic-embed-m": "embedding",
        "snowflake-arctic-embed-l": "embedding",
        # Voyage
        "voyage-multilingual": "embedding",
    }

    models_to_input_modalities: ClassVar[dict[str, list[str]]] = {
        # Anthropic
        "claude-3-5-sonnet": ["text", "tools"],  # Images?
        # DeepSeek
        "deepseek-r1": ["text"],
        # Meta
        "llama-3-1-8b": ["text"],
        "llama-3-1-70b": ["text"],
        # Snowflake (LLM)
        "snowflake-llama-3-3-70b": ["text"],
        # Snowflake (Embedding)
        "snowflake-arctic-embed-m": ["text"],
        "snowflake-arctic-embed-l": ["text"],
        # Voyage
        "voyage-multilingual": ["text"],
    }

    models_to_output_modalities: ClassVar[dict[str, list[str]]] = {
        # Anthropic
        "claude-3-5-sonnet": ["text"],
        # DeepSeek
        "deepseek-r1": ["text"],
        # Meta
        "llama-3-1-8b": ["text"],
        "llama-3-1-70b": ["text"],
        # Snowflake (LLM)
        "snowflake-llama-3-3-70b": ["text"],
        # Snowflake (Embedding)
        "snowflake-arctic-embed-m": ["embedding"],
        "snowflake-arctic-embed-l": ["embedding"],
        # Voyage
        "voyage-multilingual": ["embedding"],
    }

    @classmethod
    def supported_models(cls) -> list[str]:
        """Get list of supported model names."""
        return list(cls.class_keys())

    @classmethod
    def distinct_llm_model_ids(cls) -> list[str]:
        """Get list of distinct LLM model IDs."""
        return [
            model
            for model in cls.class_keys()
            if cls.models_to_type[model] == "llm"
        ]

    @classmethod
    def distinct_llm_model_ids_with_tool_input(cls) -> list[str]:
        """Get list of distinct LLM model IDs that support tool calling."""
        return [
            model
            for model in cls.class_keys()
            if cls.models_to_type[model] == "llm"
            and "tools" in cls.models_to_input_modalities[model]
        ]

    @classmethod
    def distinct_embedding_model_ids(cls) -> list[str]:
        """Get list of distinct embedding model IDs."""
        return [
            model
            for model in cls.class_keys()
            if cls.models_to_type[model] == "embedding"
        ]

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
