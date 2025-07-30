from dataclasses import dataclass, field

from agent_platform.core.configurations import Configuration
from agent_platform.core.configurations.base import FieldMetadata
from agent_platform.core.platforms.base import PlatformConfigs, PlatformModelMap


@dataclass(frozen=True)
class GroqModelMap(PlatformModelMap):
    """A map of our model names to Groq model IDs."""

    model_aliases: dict[str, str] = field(
        default_factory=lambda: {
            "llama-3.3": "llama-3.3-70b-versatile",
            "groq/meta/llama-3-3-instruct-70b": "llama-3.3-70b-versatile",
            "groq/meta/llama-4-scout": "llama-4-scout-17b-16e-instruct",
            "groq/meta/llama-4-maverick": "llama-4-maverick-17b-128e-instruct",
            "groq/moonshotai/kimi-k2": "moonshotai/kimi-k2-instruct",
        },
        metadata=FieldMetadata(
            description=("A mapping between our model names and Groq model IDs."),
        ),
    )

    models_to_type: dict[str, str] = field(
        default_factory=lambda: {
            "llama-3.3": "llm",
            "llama-4-scout": "llm",
            "llama-4-maverick": "llm",
            "moonshotai/kimi-k2": "llm",
        },
        metadata=FieldMetadata(
            description=("A mapping between our model names and model types."),
        ),
    )

    models_to_input_modalities: dict[str, list[str]] = field(
        default_factory=lambda: {
            # TODO vet this
            "llama-3.3": ["text", "tools"],
            "llama-4-scout": ["text", "tools"],
            "llama-4-maverick": ["text", "tools"],
            "moonshotai/kimi-k2": ["text", "tools"],
        },
        metadata=FieldMetadata(
            description=("A mapping between our model names and input modalities."),
        ),
    )

    models_to_output_modalities: dict[str, list[str]] = field(
        default_factory=lambda: {
            # TODO confirm these
            "llama-3.3": ["text"],
            "llama-4-scout": ["text"],
            "llama-4-maverick": ["text"],
            "moonshotai/kimi-k2": ["text"],
        },
        metadata=FieldMetadata(
            description=("A mapping between our model names and output modalities."),
        ),
    )

    model_families: dict[str, str] = field(
        default_factory=lambda: {
            "llama-3.3": "llama",
            "llama-4-scout": "llama",
            "llama-4-maverick": "llama",
            "moonshotai/kimi-k2": "llama",
        },
        metadata=FieldMetadata(
            description=("A mapping between our model names and model families."),
        ),
    )

    model_context_windows: dict[str, int | None] = field(
        default_factory=lambda: {
            "llama-3.3": 128_000,
            "llama-4-scout": 128_000,
            "llama-4-maverick": 128_000,
            "moonshotai/kimi-k2": 128_000,
        },
        metadata=FieldMetadata(
            description=("The maximum context window in tokens for each model."),
        ),
    )


@dataclass(frozen=True)
class GroqRoleMap(Configuration):
    """A map of Groq role names to our role names."""

    role_map: dict[str, str] = field(
        default_factory=lambda: {
            "user": "user",
            "assistant": "agent",
        },
        metadata=FieldMetadata(
            description=("A mapping between Groq role names and our role names."),
        ),
    )


@dataclass(frozen=True)
class GroqDefaultModel(Configuration):
    """The default model to use for the Groq platform."""

    default_model: str = field(
        default="llama-3.3",
        metadata=FieldMetadata(
            description="The default model to use for the Groq platform.",
        ),
    )


@dataclass(frozen=True)
class GroqPlatformConfigs(PlatformConfigs):
    """The configs for the Groq platform."""

    default_platform_provider: dict[str, str] = field(
        default_factory=lambda: {
            "llm": "groq",
            "embedding": "groq",
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
            "groq": GroqModelMap.supported_models(),
        },
        metadata={"description": "The supported models by provider."},
    )
    """The supported models by provider."""
