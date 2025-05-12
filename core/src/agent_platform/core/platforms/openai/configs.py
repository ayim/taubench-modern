from dataclasses import dataclass, field

from agent_platform.core.configurations import Configuration
from agent_platform.core.configurations.base import FieldMetadata
from agent_platform.core.platforms.base import PlatformConfigs, PlatformModelMap


@dataclass(frozen=True)
class OpenAIModelMap(PlatformModelMap):
    """A set of mappings between our model names and OpenAI model IDs.

    All mappings keys should be the model name used in the Agent Server.
    """

    model_aliases: dict[str, str] = field(
        default_factory=lambda: {
            # 4.5 series
            "gpt-4.5": "gpt-4.5-preview-2025-02-27",
            # 4.1 series
            "gpt-4.1": "gpt-4.1-2025-04-14",
            "gpt-4.1-mini": "gpt-4.1-mini-2025-04-14",
            "gpt-4.1-nano": "gpt-4.1-nano-2025-04-14",
            # 4o series
            "chatgpt-4o-latest": "chatgpt-4o-latest",
            "gpt-4o": "gpt-4o-2024-08-06",
            "gpt-4o-audio": "gpt-4o-audio-preview-2024-12-17",
            # 4o mini series
            "gpt-4o-mini": "gpt-4o-mini-2024-07-18",
            "gpt-4o-audio-mini": "gpt-4o-mini-audio-preview-2024-12-17",
            # 4-turbo series
            "gpt-4-turbo": "gpt-4-turbo-2024-04-09",
            # 3.5-turbo series (legacy)
            "gpt-3.5-turbo": "gpt-3.5-turbo-0125",
            # o3-mini series
            "o3-mini-high": "o3-mini-2025-01-31",
            "o3-mini-low": "o3-mini-2025-01-31",
            # o1-mini series
            "o1-mini-high": "o1-mini-2024-09-12",
            "o1-mini-low": "o1-mini-2024-09-12",
            # o1 series
            "o1-high": "o1-2024-12-17",
            "o1-low": "o1-2024-12-17",
            # Embedding models
            "text-embedding-3-small": "text-embedding-3-small",
            "text-embedding-3-large": "text-embedding-3-large",
            "text-embedding-ada-002": "text-embedding-ada-002",
        },
        metadata=FieldMetadata(
            description=("A mapping between our model names and OpenAI model IDs."),
        ),
    )

    models_to_type: dict[str, str] = field(
        default_factory=lambda: {
            # 4.5 series
            "gpt-4.5": "llm",
            # 4.1 series
            "gpt-4.1": "llm",
            "gpt-4.1-mini": "llm",
            "gpt-4.1-nano": "llm",
            # 4o series
            "chatgpt-4o-latest": "llm",
            "gpt-4o": "llm",
            "gpt-4o-audio": "llm",
            # 4o mini series
            "gpt-4o-mini": "llm",
            "gpt-4o-audio-mini": "llm",
            # 4-turbo series
            "gpt-4-turbo": "llm",
            # 3.5-turbo series (legacy)
            "gpt-3.5-turbo": "llm",
            # o3-mini series
            "o3-mini-high": "llm",
            "o3-mini-low": "llm",
            # o1-mini series
            "o1-mini-high": "llm",
            "o1-mini-low": "llm",
            # o1 series
            "o1-high": "llm",
            "o1-low": "llm",
            # Embedding models
            "text-embedding-3-small": "embedding",
            "text-embedding-3-large": "embedding",
            "text-embedding-ada-002": "embedding",
        },
        metadata=FieldMetadata(
            description=("A mapping between our model names and model types."),
        ),
    )

    models_to_input_modalities: dict[str, list[str]] = field(
        default_factory=lambda: {
            # 4.5 series
            "gpt-4.5": ["text", "tools", "images"],
            # 4.1 series
            "gpt-4.1": ["text", "tools", "images"],
            "gpt-4.1-mini": ["text", "tools", "images"],
            "gpt-4.1-nano": ["text", "tools", "images"],
            # 4o series
            "chatgpt-4o-latest": ["text", "images"],
            "gpt-4o": ["text", "tools", "images"],
            "gpt-4o-audio": ["text", "tools", "audio"],
            # 4o mini series
            "gpt-4o-mini": ["text", "tools", "images"],
            "gpt-4o-audio-mini": ["text", "tools", "audio"],
            # 4-turbo series
            "gpt-4-turbo": ["text", "tools"],
            # 3.5-turbo series (legacy)
            "gpt-3.5-turbo": ["text", "tools"],
            # o3-mini series
            "o3-mini-high": ["text", "tools"],
            "o3-mini-low": ["text", "tools"],
            # o1-mini series
            "o1-mini-high": ["text"],
            "o1-mini-low": ["text"],
            # o1 series
            "o1-high": ["text", "tools", "images"],
            "o1-low": ["text", "tools", "images"],
            # Embedding models
            "text-embedding-3-small": ["text"],
            "text-embedding-3-large": ["text"],
            "text-embedding-ada-002": ["text"],
        },
        metadata=FieldMetadata(
            description=("A mapping between our model names and input modalities."),
        ),
    )

    models_to_output_modalities: dict[str, list[str]] = field(
        default_factory=lambda: {
            # 4.5 series
            "gpt-4.5": ["text"],
            # 4.1 series
            "gpt-4.1": ["text"],
            "gpt-4.1-mini": ["text"],
            "gpt-4.1-nano": ["text"],
            # 4o series
            "chatgpt-4o-latest": ["text"],
            "gpt-4o": ["text"],
            "gpt-4o-audio": ["text", "audio"],
            # 4o mini series
            "gpt-4o-mini": ["text"],
            "gpt-4o-audio-mini": ["text", "audio"],
            # 4-turbo series
            "gpt-4-turbo": ["text"],
            # 3.5-turbo series (legacy)
            "gpt-3.5-turbo": ["text"],
            # o3-mini series
            "o3-mini-high": ["text"],
            "o3-mini-low": ["text"],
            # o1-mini series
            "o1-mini-high": ["text"],
            "o1-mini-low": ["text"],
            # o1 series
            "o1-high": ["text"],
            "o1-low": ["text"],
            # Embedding models
            "text-embedding-3-small": ["embedding"],
            "text-embedding-3-large": ["embedding"],
            "text-embedding-ada-002": ["embedding"],
        },
        metadata=FieldMetadata(
            description=("A mapping between our model names and output modalities."),
        ),
    )

    model_families: dict[str, str] = field(
        default_factory=lambda: {
            # 4.5 series
            "gpt-4.5": "gpt",
            # 4.1 series
            "gpt-4.1": "gpt",
            "gpt-4.1-mini": "gpt",
            "gpt-4.1-nano": "gpt",
            # 4o series
            "chatgpt-4o-latest": "gpt",
            "gpt-4o": "gpt",
            "gpt-4o-audio": "gpt",
            # 4o mini series
            "gpt-4o-mini": "gpt",
            "gpt-4o-audio-mini": "gpt",
            # 4-turbo series
            "gpt-4-turbo": "gpt",
            # 3.5-turbo series (legacy)
            "gpt-3.5-turbo": "gpt",
            # o3-mini series
            "o3-mini-high": "o",
            "o3-mini-low": "o",
            # o1-mini series
            "o1-mini-high": "o",
            "o1-mini-low": "o",
            # o1 series
            "o1-high": "o",
            "o1-low": "o",
            # Embedding models
            "text-embedding-3-small": "embedding",
            "text-embedding-3-large": "embedding",
            "text-embedding-ada-002": "embedding",
        },
        metadata=FieldMetadata(
            description=("A mapping between our model names and model families."),
        ),
    )


@dataclass(frozen=True)
class OpenAIRoleMap(Configuration):
    """A map of OpenAI role names to our role names."""

    role_map: dict[str, str] = field(
        default_factory=lambda: {
            "user": "user",
            "assistant": "agent",
        },
        metadata=FieldMetadata(
            description="A map of OpenAI role names to our role names.",
        ),
    )


@dataclass(frozen=True)
class OpenAIDefaultModel(Configuration):
    """The default model to use for the OpenAI platform."""

    default_model: str = field(
        default="gpt-4o",
        metadata=FieldMetadata(
            description="The default model to use for the OpenAI platform.",
        ),
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
