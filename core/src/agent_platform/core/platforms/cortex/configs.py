from dataclasses import dataclass, field

from agent_platform.core.configurations import Configuration
from agent_platform.core.configurations.base import FieldMetadata
from agent_platform.core.platforms.base import PlatformConfigs, PlatformModelMap


@dataclass(frozen=True)
class CortexModelMap(PlatformModelMap):
    """A set of mappings between our model names and Cortex model IDs.

    All mappings keys should be the model name used in the Agent Server.
    """

    model_aliases: dict[str, str] = field(
        default_factory=lambda: {
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
        },
        metadata=FieldMetadata(
            description=("A mapping between our model names and Cortex model IDs."),
        ),
    )

    models_to_type: dict[str, str] = field(
        default_factory=lambda: {
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
        },
        metadata=FieldMetadata(
            description=("A mapping between our model names and model types."),
        ),
    )

    models_to_input_modalities: dict[str, list[str]] = field(
        default_factory=lambda: {
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
        },
        metadata=FieldMetadata(
            description=("A mapping between our model names and input modalities."),
        ),
    )

    models_to_output_modalities: dict[str, list[str]] = field(
        default_factory=lambda: {
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
        },
        metadata=FieldMetadata(
            description=("A mapping between our model names and output modalities."),
        ),
    )

    model_families: dict[str, str] = field(
        default_factory=lambda: {
            # Anthropic
            "claude-3-5-sonnet": "claude",
            # DeepSeek
            "deepseek-r1": "deepseek",
            # Meta
            "llama-3-1-8b": "llama",
            "llama-3-1-70b": "llama",
            # Snowflake (LLM)
            "snowflake-llama-3-3-70b": "llamma",
            # Snowflake (Embedding)
            "snowflake-arctic-embed-m": "embedding",
            "snowflake-arctic-embed-l": "embedding",
            # Voyage
            "voyage-multilingual": "voyage",
        },
    )

    model_context_windows: dict[str, int | None] = field(
        default_factory=lambda: {
            # Anthropic
            "claude-3-5-sonnet": 200_000,
            # DeepSeek
            "deepseek-r1": 128_000,
            # Meta
            "llama-3-1-8b": 128_000,
            "llama-3-1-70b": 128_000,
            # Snowflake (LLM)
            "snowflake-llama-3-3-70b": 128_000,
            # Snowflake (Embedding)
            "snowflake-arctic-embed-m": 512,
            "snowflake-arctic-embed-l": 2_048,
            # Voyage
            "voyage-multilingual": 32_000,
        },
        metadata=FieldMetadata(
            description=("The context window size for each model."),
        ),
    )


@dataclass(frozen=True)
class CortexRoleMap(Configuration):
    """A map of Cortex role names to our role names."""

    role_map: dict[str, str] = field(
        default_factory=lambda: {
            "user": "user",
            "assistant": "agent",
        },
        metadata=FieldMetadata(
            description=("A map of Cortex role names to our role names."),
        ),
    )


@dataclass(frozen=True)
class CortexDefaultModel(Configuration):
    """The default model to use for the Cortex platform."""

    default_model: str = field(
        default="claude-3-5-sonnet",
        metadata=FieldMetadata(
            description="The default model to use for the Cortex platform.",
        ),
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
