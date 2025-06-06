from dataclasses import dataclass, field

from agent_platform.core.configurations import Configuration
from agent_platform.core.configurations.base import FieldMetadata
from agent_platform.core.platforms.base import PlatformConfigs, PlatformModelMap


@dataclass(frozen=True)
class GoogleModelMap(PlatformModelMap):
    """A set of mappings between our model names and Google model IDs.

    All mappings keys should be the model name used in the Agent Server.
    """

    model_aliases: dict[str, str] = field(
        default_factory=lambda: {
            # Gemini models (LLM)
            # "gemini-2.5-pro-preview": "gemini-2.5-pro-preview-05-06",
            "gemini-2.0-flash": "gemini-2.0-flash",
            "gemini-2.0-flash-lite": "gemini-2.0-flash-lite",
            "gemini-1.5-pro": "gemini-1.5-pro",
            "gemini-2.5-flash-preview-04-17-high": "gemini-2.5-flash-preview-04-17",
            "gemini-2.5-flash-preview-04-17-low": "gemini-2.5-flash-preview-04-17",
            # Gemini models (embedding)
            "gemini-embedding-exp-03-07": "gemini-embedding-exp-03-07",
            "models/text-embedding-004": "models/text-embedding-004",
            "models/embedding-001": "models/embedding-001",
        },
        metadata=FieldMetadata(
            description=("A mapping between our model names and Google model IDs."),
        ),
    )

    models_to_type: dict[str, str] = field(
        default_factory=lambda: {
            # Gemini models (LLM)
            "gemini-2.5-pro-preview": "llm",
            "gemini-2.5-flash-preview-04-17-high": "llm",
            "gemini-2.5-flash-preview-04-17-low": "llm",
            "gemini-2.0-flash": "llm",
            "gemini-2.0-flash-lite": "llm",
            "gemini-1.5-flash": "llm",
            "gemini-1.5-flash-8b": "llm",
            "gemini-1.5-pro": "llm",
            # Gemini models (embedding)
            "gemini-embedding-exp-03-07": "embedding",
            "models/text-embedding-004": "embedding",
            "models/embedding-001": "embedding",
            # Imagen models (image generation)
            "imagen-3.0-generate-002": "image",
            # Video models (video generation)
            "veo-2.0-generate-001": "video",
        },
        metadata=FieldMetadata(
            description=("A mapping between our model names and model types."),
        ),
    )

    models_to_input_modalities: dict[str, list[str]] = field(
        default_factory=lambda: {
            # Gemini models (LLM)
            # "gemini-2.5-pro-preview": [
            #     "text",
            #     "audio",
            #     "images",
            #     "video",
            #     "tools",
            # ],
            "gemini-2.5-flash-preview-04-17-high": [
                "text",
                "audio",
                "images",
                "video",
                "tools",
            ],
            "gemini-2.5-flash-preview-04-17-low": [
                "text",
                "audio",
                "images",
                "video",
                "tools",
            ],
            "gemini-2.0-flash": ["text", "audio", "images", "video", "tools"],
            "gemini-2.0-flash-lite": ["text", "audio", "images", "video", "tools"],
            "gemini-1.5-flash": ["text", "audio", "images", "video", "tools"],
            "gemini-1.5-flash-8b": ["text", "audio", "images", "video", "tools"],
            "gemini-1.5-pro": ["text", "audio", "images", "video", "tools"],
            "gemini-2.5-flash-preview-04-17": [
                "text",
                "audio",
                "video",
                "images",
                "tools",
            ],
            # Gemini models (embedding)
            "gemini-embedding-exp-03-07": ["text"],
            "models/text-embedding-004": ["text"],
            "models/embedding-001": ["text"],
            # Imagen models (image generation)
            "imagen-3.0-generate-002": ["text"],
            # Video models (video generation)
            "veo-2.0-generate-001": ["text", "images"],
        },
        metadata=FieldMetadata(
            description=("A mapping between our model names and input modalities."),
        ),
    )

    models_to_output_modalities: dict[str, list[str]] = field(
        default_factory=lambda: {
            # Gemini models (LLM)
            # "gemini-2.5-pro-preview": ["text"],
            "gemini-2.5-flash-preview-04-17-high": ["text"],
            "gemini-2.5-flash-preview-04-17-low": ["text"],
            # 2.0 Flash lists image output as experimental.
            # Hence, we don't include it (for now)
            "gemini-2.0-flash": ["text"],
            "gemini-2.0-flash-lite": ["text"],
            "gemini-1.5-flash": ["text"],
            "gemini-1.5-flash-8b": ["text"],
            "gemini-1.5-pro": ["text"],
            "gemini-2.5-flash-preview-04-17": ["text"],
            # Gemini models (embedding)
            "gemini-embedding-exp-03-07": ["embedding"],
            "models/text-embedding-004": ["embedding"],
            "models/embedding-001": ["embedding"],
            # Imagen models (image generation)
            "imagen-3.0-generate-002": ["image"],
            # Video models (video generation)
            "veo-2.0-generate-001": ["video"],
        },
        metadata=FieldMetadata(
            description=("A mapping between our model names and output modalities."),
        ),
    )

    model_families: dict[str, str] = field(
        default_factory=lambda: {
            # Gemini models (LLM)
            # "gemini-2.5-pro-preview": "gemini",
            "gemini-2.0-flash": "gemini",
            "gemini-2.0-flash-lite": "gemini",
            "gemini-1.5-pro": "gemini",
            "gemini-2.5-flash-preview-04-17-high": "gemini",
            "gemini-2.5-flash-preview-04-17-low": "gemini",
            # Gemini models (embedding)
            "gemini-embedding-exp-03-07": "embedding",
            "models/text-embedding-004": "embedding",
            "models/embedding-001": "embedding",
        },
        metadata=FieldMetadata(
            description=("A mapping between our model names and model families."),
        ),
    )

    model_context_windows: dict[str, int | None] = field(
        default_factory=lambda: {
            # Gemini models (LLM)
            # "gemini-2.5-pro-preview": 1_048_576,
            "gemini-2.0-flash": 1_048_576,
            "gemini-2.0-flash-lite": 1_048_576,
            "gemini-1.5-pro": 2_097_152,
            "gemini-2.5-flash-preview-04-17-high": 1_048_576,
            "gemini-2.5-flash-preview-04-17-low": 1_048_576,
            # Gemini models (embedding)
            "gemini-embedding-exp-03-07": 8_192,
            "models/text-embedding-004": 2_048,
            "models/embedding-001": 2_048,
        },
        metadata=FieldMetadata(
            description=("The context window size for each model."),
        ),
    )


@dataclass(frozen=True)
class GoogleRoleMap(Configuration):
    """A map of Google role names to our role names."""

    role_map: dict[str, str] = field(
        default_factory=lambda: {
            "user": "user",
            "model": "agent",
        },
        metadata=FieldMetadata(
            description="A map of Google role names to our role names.",
        ),
    )


@dataclass(frozen=True)
class GoogleDefaultModel(Configuration):
    """The default model to use for the Google platform."""

    default_model: str = field(
        default="gemini-1.5-pro",
        metadata=FieldMetadata(
            description="The default model to use for the Google platform.",
        ),
    )


@dataclass(frozen=True)
class GooglePlatformConfigs(PlatformConfigs):
    """The configs for the Google platform."""

    default_platform_provider: dict[str, str] = field(
        default_factory=lambda: {
            "llm": "google",
            "embedding": "google",
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
            "google": GoogleModelMap.supported_models(),
        },
        metadata=FieldMetadata(
            description="The supported models by provider.",
        ),
    )
    """The supported models by provider."""
