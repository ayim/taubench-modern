from dataclasses import dataclass, field

from agent_platform.core.configurations import Configuration
from agent_platform.core.configurations.base import FieldMetadata
from agent_platform.core.platforms.base import PlatformConfigs, PlatformModelMap


@dataclass(frozen=True)
class GroqModelMap(PlatformModelMap):
    """A map of our model names to Groq model IDs."""

    model_aliases: dict[str, str] = field(
        default_factory=lambda: {
            "gemma2": "gemma2-9b-it",
            "llama-3.3": "llama-3.3-70b-versatile",
            "llama-3.1": "llama-3.1-8b-instant",
            "llama-guard": "llama-guard-3-8b",
            "llama3-70b": "llama3-70b-8192",
            "llama3-8b": "llama3-8b-8192",
            "whisper": "whisper-large-v3",
            "whisper-turbo": "whisper-large-v3-turbo",
            "distil-whisper": "distil-whisper-large-v3-en",
        },
        metadata=FieldMetadata(
            description=("A mapping between our model names and Groq model IDs."),
        ),
    )

    models_to_type: dict[str, str] = field(
        default_factory=lambda: {
            "gemma2": "llm",
            "llama-3.3": "llm",
            "llama-3.1": "llm",
            "llama-guard": "llm",
            "llama3-70b": "llm",
            "llama3-8b": "llm",
            "whisper": "llm",
            "whisper-turbo": "llm",
            "distil-whisper": "llm",
        },
        metadata=FieldMetadata(
            description=("A mapping between our model names and model types."),
        ),
    )

    models_to_input_modalities: dict[str, list[str]] = field(
        default_factory=lambda: {
            # TODO vet this
            "gemma2": ["text", "tools", "images"],
            "llama-3.3": ["text", "tools"],
            "llama-3.1": ["text", "tools"],
            "llama-guard": ["text"],
            "llama3-70b": ["text"],
            "llama3-8b": ["text"],
            "whisper": ["text"],
            "whisper-turbo": ["text"],
            "distil-whisper": ["text"],
        },
        metadata=FieldMetadata(
            description=("A mapping between our model names and input modalities."),
        ),
    )

    models_to_output_modalities: dict[str, list[str]] = field(
        default_factory=lambda: {
            # TODO confirm these
            "gemma2": ["text", "images"],
            "llama-3.3": ["text"],
            "llama-3.1": ["text"],
            "llama-guard": ["text"],
            "llama3-70b": ["text"],
            "llama3-8b": ["text"],
            "whisper": ["text"],
            "whisper-turbo": ["text"],
            "distil-whisper": ["text"],
        },
        metadata=FieldMetadata(
            description=("A mapping between our model names and output modalities."),
        ),
    )

    model_families: dict[str, str] = field(
        default_factory=lambda: {
            "gemma2": "gemma",
            "llama-3.3": "llama",
            "llama-3.1": "llama",
            "llama-guard": "llama",
            "llama3-70b": "llama",
            "llama3-8b": "llama",
            "whisper": "whisper",
            "whisper-turbo": "whisper",
            "distil-whisper": "whisper",
        },
        metadata=FieldMetadata(
            description=("A mapping between our model names and model families."),
        ),
    )

    model_context_windows: dict[str, int | None] = field(
        default_factory=lambda: {
            "gemma2": 8_192,
            "llama-3.3": 128_000,
            "llama-3.1": 128_000,
            "llama-guard": 131_072,
            "llama3-70b": 8_192,
            "llama3-8b": 8_192,
            "whisper": None,  # TODO: update when known
            "whisper-turbo": None,  # TODO: update when known
            "distil-whisper": None,  # TODO: update when known
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
