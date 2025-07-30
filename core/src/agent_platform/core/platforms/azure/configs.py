from dataclasses import dataclass, field
from typing import ClassVar

from agent_platform.core.configurations import Configuration
from agent_platform.core.configurations.base import FieldMetadata
from agent_platform.core.platforms.base import PlatformConfigs, PlatformModelMap


@dataclass(frozen=True)
class AzureOpenAIModelMap(PlatformModelMap):
    """A set of mappings between our model names and Azure OpenAI deployment IDs.

    All mappings keys should be the model name used in the Agent Server.
    """

    model_aliases: dict[str, str] = field(
        default_factory=lambda: {
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
            # These are all going away (these config files)
            "azure/openai/gpt-4-1": "gpt-4.1",
            "azure/openai/gpt-4-1-mini": "gpt-4.1-mini",
            "azure/openai/gpt-4o": "gpt-4o",
            "azure/openai/gpt-4o-mini": "gpt-4o-mini",
            "azure/openai/gpt-4o-chatgpt": "chatgpt-4o-latest",
            "azure/openai/o3-high": "o3",
            "azure/openai/o3-low": "o3",
            "azure/openai/o4-mini-high": "o4-mini",
            "azure/openai/o4-mini-low": "o4-mini",
            "azure/openai/text-embedding-3-small": "text-embedding-3-small",
            "azure/openai/text-embedding-3-large": "text-embedding-3-large",
        },
        metadata=FieldMetadata(
            description=("A mapping between our model names and Azure OpenAI deployment IDs."),
        ),
    )
    # TODO: Add mappings for model types, input modalities, and output modalities

    model_families: dict[str, str] = field(
        default_factory=lambda: {
            "gpt-4o": "gpt",
            "gpt-4o-mini": "gpt",
            "gpt-4-turbo": "gpt",
            "gpt-3.5-turbo": "gpt",
            "o3-mini-high": "o",
            "o3-mini-low": "o",
            "o1-mini-high": "o",
            "o1-mini-low": "o",
            "o1-pro-high": "o",
            "o1-pro-low": "o",
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

    model_context_windows: dict[str, int | None] = field(
        default_factory=lambda: {
            "gpt-4o": 128_000,
            "gpt-4o-mini": 128_000,
            "gpt-4-turbo": 128_000,
            "gpt-3.5-turbo": 16_385,
            "o3-mini-high": 200_000,
            "o3-mini-low": 200_000,
            "o1-mini-high": 128_000,
            "o1-mini-low": 128_000,
            "o1-pro-high": 200_000,
            "o1-pro-low": 200_000,
            "o1-high": 200_000,
            "o1-low": 200_000,
            # Embedding models
            "text-embedding-3-small": 8_192,
            "text-embedding-3-large": 8_192,
            "text-embedding-ada-002": 8_192,
        },
        metadata=FieldMetadata(
            description=("The maximum context window in tokens for each model."),
        ),
    )


@dataclass(frozen=True)
class AzureOpenAIRoleMap(Configuration):
    """A mapping between Azure Open AI message role names and Agent Server
    message role names keyed with the Azure Open AI role name.
    """

    role_map: dict[str, str] = field(
        default_factory=lambda: {
            "user": "user",
            "assistant": "agent",
        },
        metadata=FieldMetadata(
            description=(
                "A mapping between Azure Open AI message role names and Agent Server "
                "message role names keyed with the Azure Open AI role name."
            ),
        ),
    )


@dataclass(frozen=True)
class AzureOpenAIDefaultModel(Configuration):
    """The default model to use for the Azure OpenAI platform."""

    default_model: str = field(
        default="gpt-4o",
        metadata=FieldMetadata(
            description=("The default model to use for the Azure OpenAI platform."),
        ),
    )


@dataclass(frozen=True)
class AzureOpenAIPlatformConfigs(PlatformConfigs):
    """The configs for the Azure OpenAI platform."""

    depends_on: ClassVar[list[type[Configuration]]] = [AzureOpenAIModelMap]

    default_platform_provider: dict[str, str] = field(
        default_factory=lambda: {
            "llm": "azure",
            "embedding": "azure",
        },
        metadata=FieldMetadata(
            description="The default platform provider by model type.",
        ),
    )
    """The default platform provider by model type."""

    default_model_type: str = field(
        default="llm",
        metadata=FieldMetadata(
            description="The default model type.",
        ),
    )
    """The default model type."""

    default_quality_tier: dict[str, str] = field(
        default_factory=lambda: {
            "llm": "balanced",
            "embedding": "balanced",
        },
        metadata=FieldMetadata(
            description="The default quality tier by model type.",
        ),
    )
    """The default quality tier by model type."""

    supported_models_by_provider: dict[str, list[str]] = field(
        default_factory=lambda: {
            "azure": AzureOpenAIModelMap.supported_models(),
        },
        metadata=FieldMetadata(
            description="The supported models by provider.",
        ),
    )
    """The supported models by provider."""
