from dataclasses import dataclass, field

from agent_platform.core.configurations import Configuration
from agent_platform.core.configurations.base import FieldMetadata
from agent_platform.core.platforms.base import PlatformConfigs, PlatformModelMap


@dataclass(frozen=True)
class BedrockContentLimits(Configuration):
    """Content limits and associated global configurations for the Bedrock platform."""

    max_image_count: int = field(
        default=20,
        metadata=FieldMetadata(
            description="The maximum number of images that can be included in a request.",
        ),
    )
    max_image_size: int = field(
        default=3_750_000,
        metadata=FieldMetadata(
            description="The maximum size of an image in bytes.",
        ),
    )
    max_image_height: int = field(
        default=8_000,
        metadata=FieldMetadata(
            description="The maximum height of an image in pixels.",
        ),
    )
    max_image_width: int = field(
        default=8_000,
        metadata=FieldMetadata(
            description="The maximum width of an image in pixels.",
        ),
    )
    max_document_count: int = field(
        default=5,
        metadata=FieldMetadata(
            description="The maximum number of documents that can be included in a request.",
        ),
    )
    max_document_size: int = field(
        default=4_500_000,
        metadata=FieldMetadata(
            description="The maximum size of a document in bytes.",
        ),
    )


@dataclass(frozen=True)
class BedrockModelMap(PlatformModelMap):
    """A set of mappings between our model names and Bedrock model IDs.

    All mappings keys should be the model name used in the Agent Server.
    """

    model_aliases: dict[str, str] = field(
        default_factory=lambda: {
            # Anthropic
            # We don't have on-demand access for 3.7-sonnet?
            # "claude-3-7-sonnet": "anthropic.claude-3-7-sonnet-20250219-v1:0",
            "claude-3-5-sonnet": "us.anthropic.claude-3-5-sonnet-20241022-v2:0",
            "claude-3-5-haiku": "us.anthropic.claude-3-haiku-20240307-v1:0",
            # Amazon
            "titan-embed-text-v2": "amazon.titan-embed-text-v2:0",
            "titan-embed-text-v1": "amazon.titan-embed-text-v1",
            # Cohere
            # And no access to command-r-plus?
            # "cohere-command-r-plus": "cohere.command-r-plus-v1:0",
            "cohere-embed-english-v3": "cohere.embed-english-v3",
            "cohere-embed-multilingual-v3": "cohere.embed-multilingual-v3",
        },
        metadata=FieldMetadata(
            description=("A mapping between our model names and Bedrock model IDs."),
        ),
    )

    models_to_type: dict[str, str] = field(
        default_factory=lambda: {
            # Anthropic
            "claude-3-7-sonnet": "llm",
            "claude-3-5-sonnet": "llm",
            "claude-3-5-haiku": "llm",
            # Amazon
            "titan-embed-text-v2": "embedding",
            "titan-embed-text-v1": "embedding",
            # Cohere (LLM)
            "cohere-command-r-plus": "llm",
            # Cohere (Embedding)
            "cohere-embed-english-v3": "embedding",
            "cohere-embed-multilingual-v3": "embedding",
        },
        metadata=FieldMetadata(
            description=("A mapping between our model names and model types."),
        ),
    )

    models_to_input_modalities: dict[str, list[str]] = field(
        default_factory=lambda: {
            # Anthropic
            "claude-3-7-sonnet": ["text", "tools", "images"],
            "claude-3-5-sonnet": ["text", "tools", "images"],
            "claude-3-5-haiku": ["text", "tools", "images"],
            # Amazon
            "titan-embed-text-v2": ["text"],
            "titan-embed-text-v1": ["text"],
            # Cohere (LLM)
            "cohere-command-r-plus": ["text", "tools"],
            # Cohere (Embedding)
            "cohere-embed-english-v3": ["text"],
            "cohere-embed-multilingual-v3": ["text"],
        },
        metadata=FieldMetadata(
            description=("A mapping between our model names and input modalities."),
        ),
    )

    models_to_output_modalities: dict[str, list[str]] = field(
        default_factory=lambda: {
            # Anthropic
            "claude-3-7-sonnet": ["text"],
            "claude-3-5-sonnet": ["text"],
            "claude-3-5-haiku": ["text"],
            # Amazon
            "titan-embed-text-v2": ["embedding"],
            "titan-embed-text-v1": ["embedding"],
            # Cohere (LLM)
            "cohere-command-r-plus": ["text"],
            # Cohere (Embedding)
            "cohere-embed-english-v3": ["embedding"],
            "cohere-embed-multilingual-v3": ["embedding"],
        },
        metadata=FieldMetadata(
            description=("A mapping between our model names and output modalities."),
        ),
    )

    model_families: dict[str, str] = field(
        default_factory=lambda: {
            # Anthropic
            "claude-3-7-sonnet": "claude",
            "claude-3-5-sonnet": "claude",
            "claude-3-5-haiku": "claude",
            # Amazon
            "titan-embed-text-v2": "embedding",
            "titan-embed-text-v1": "embedding",
            # Cohere (LLM)
            "cohere-command-r-plus": "cohere",
            # Cohere (Embedding)
            "cohere-embed-english-v3": "embedding",
            "cohere-embed-multilingual-v3": "embedding",
        },
        metadata=FieldMetadata(
            description="A mapping between our model names and model families.",
        ),
    )

    model_context_windows: dict[str, int | None] = field(
        default_factory=lambda: {
            # Anthropic
            "claude-3-7-sonnet": 200_000,
            "claude-3-5-sonnet": 200_000,
            "claude-3-5-haiku": 200_000,
            # Amazon
            "titan-embed-text-v2": 8_192,
            "titan-embed-text-v1": 8_192,
            # Cohere (LLM)
            "cohere-command-r-plus": 128_000,
            # Cohere (Embedding)
            "cohere-embed-english-v3": 512,
            "cohere-embed-multilingual-v3": 512,
        },
        metadata=FieldMetadata(
            description=("The maximum context window in tokens for each model."),
        ),
    )


@dataclass(frozen=True)
class BedrockRoleMap(Configuration):
    """A map of Bedrock role names to our role names."""

    role_map: dict[str, str] = field(
        default_factory=lambda: {
            "user": "user",
            "assistant": "agent",
        },
        metadata=FieldMetadata(
            description=("A map of Bedrock role names to our role names."),
        ),
    )


@dataclass(frozen=True)
class BedrockDefaultModel(Configuration):
    """The default model to use for the Bedrock platform."""

    DEFAULT_MODEL: str = field(
        default="claude-3-5-sonnet",
    )


@dataclass(frozen=True)
class BedrockMimeTypeMap(Configuration):
    """A map of Bedrock format types to MIME types supported by the platform."""

    mime_type_map: dict[str, str] = field(
        default_factory=lambda: {
            "jpeg": "image/jpeg",
            "png": "image/png",
            "gif": "image/gif",
            "webp": "image/webp",
            "pdf": "application/pdf",
            "txt": "text/plain",
            "csv": "text/csv",
            "md": "text/markdown",
            "html": "text/html",
            "xls": "application/vnd.ms-excel",
            "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "doc": "application/msword",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        },
        metadata=FieldMetadata(
            description=("A map of Bedrock format types to MIME types supported by the platform."),
        ),
    )

    @classmethod
    def supported_format_types(cls) -> list[str]:
        """Get list of supported format types."""
        return list(cls.mime_type_map.keys())

    @classmethod
    def reverse_mapping(cls) -> dict[str, str]:
        """Get reverse mapping of MIME types to format types."""
        return {v: k for k, v in cls.mime_type_map.items()}


@dataclass(frozen=True)
class BedrockPlatformConfigs(PlatformConfigs):
    """The configs for the Bedrock platform."""

    default_platform_provider: dict[str, str] = field(
        default_factory=lambda: {
            "llm": "anthropic",
            "embedding": "amazon",
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
            "anthropic": [
                "claude-3-5-sonnet",
                "claude-3-5-haiku",
            ],
            "amazon": [
                "titan-embed-text-v2",
                "titan-embed-text-v1",
            ],
            "cohere": [
                "cohere-embed-english-v3",
                "cohere-embed-multilingual-v3",
            ],
        },
        metadata=FieldMetadata(
            description="The supported models by provider.",
        ),
    )
    """The supported models by provider."""
