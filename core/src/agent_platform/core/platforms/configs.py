from dataclasses import dataclass, field
from typing import Literal

from agent_platform.core.configurations import Configuration
from agent_platform.core.configurations.base import FieldMetadata
from agent_platform.core.errors.base import PlatformHTTPError
from agent_platform.core.errors.responses import ErrorCode
from agent_platform.core.platforms.base import PlatformClient
from agent_platform.core.platforms.llms_metadata_loader import llms_metadata_loader
from agent_platform.core.platforms.llms_metadata_models import LLMModelMetadata

ModelType = Literal[
    "llm",
    "embedding",
    "text-to-image",
    "text-to-audio",
    "audio-to-text",
    "document-processor",
]

ModelPrioritization = Literal["intelligence", "speed", "cost"]

EXPERIMENTAL_ARCH_2_0_0 = "agent_platform.architectures.experimental_1==2.0.0"
CONSISTENCY_ARCH_2_0_0 = "agent_platform.architectures.experimental_2==2.0.0"


def _normalize_model_slug_for_lookup(slug: str) -> str:
    """Normalize a model slug for lookup in llms.json.

    Some models have different naming conventions in our configuration vs llms.json.
    This function maps our internal names to the slugs used in llms.json.

    Args:
        slug: The model slug from our configuration

    Returns:
        The normalized slug for lookup in llms.json
    """
    # Handle reasoning model suffixes (o3-high -> o3, o4-mini-low -> o4-mini)
    if (
        slug.endswith("-high")
        or slug.endswith("-medium")
        or slug.endswith("-low")
        or slug.endswith("-minimal")
    ):
        slug = slug.rsplit("-", 1)[0]

    # Handle specific model name differences between our config and llms.json
    slug_mappings = {
        # Claude models: our config uses claude-3-5-sonnet but llms.json has claude-35-sonnet
        "claude-3-5-sonnet": "claude-35-sonnet",
        # Note: claude-3-5-haiku exists as-is in llms.json so no mapping needed
        # Gemini models: our config uses simplified names but llms.json has versioned slugs
        "gemini-2-0-flash-lite": "gemini-2-0-flash-lite-001",
        # llms.json uses "-thinking" suffix for some Claude models and "-reasoning" for others
        # keeping sema4 config naming convention as "thinking", and mapping to llms.json
        "claude-4-5-haiku-thinking": "claude-4-5-haiku-reasoning",
    }

    return slug_mappings.get(slug, slug)


def get_model_metadata_by_generic_id(generic_model_id: str) -> LLMModelMetadata | None:
    """Get model metadata from llms.json for a given generic model ID.

    Args:
        generic_model_id: A model ID in the format "platform/provider/model"
                         (e.g., "openai/openai/gpt-4-1")

    Returns:
        A dictionary containing the model metadata if found, None otherwise.
    """
    # Extract the slug from the generic model ID (the part after the last slash)
    parts = generic_model_id.split("/")
    if len(parts) != "platform/provider/model".count("/") + 1:
        return None

    model_slug = parts[-1]  # Get the last part as the slug
    return get_model_metadata_by_slug(model_slug)


def get_model_metadata_by_slug(slug: str) -> LLMModelMetadata | None:
    """Get model metadata from llms.json for a given model slug.

    Args:
        slug: The model slug (e.g., "gpt-4-1")

    Returns:
        A dictionary containing the model metadata if found, None otherwise.
    """
    # Try to get the model by slug first, normalize it if needed
    model = llms_metadata_loader.get_model_by_slug(slug)
    if model is not None:
        return model

    # Normalize the slug for lookup (handles -high/-low suffixes)
    normalized_slug = _normalize_model_slug_for_lookup(slug)
    return llms_metadata_loader.get_model_by_slug(normalized_slug)


@dataclass(frozen=True)
class PlatformModelConfigs(Configuration):
    """Configuration describing models across all platforms."""

    # PLATFORMS TO DEFAULT MODELS
    # This is a mapping of platforms to their default models.
    platforms_to_default_model: dict[str, str] = field(
        default_factory=lambda: {
            "azure": "azure/openai/gpt-5-medium",
            "bedrock": "bedrock/anthropic/claude-4-sonnet-thinking-medium",
            "cortex": "cortex/anthropic/claude-3-5-sonnet",
            "openai": "openai/openai/gpt-5-medium",
            "google": "google/google/gemini-2-5-pro",
            "groq": "groq/openai/gpt-oss-120b",
            "reducto": "reducto/reducto/reducto-standard-parse",
            "litellm": "litellm/openai/gpt-5-low",
        },
        metadata=FieldMetadata(
            description="A mapping of platforms to their default models.",
        ),
    )

    # PLATFORMS TO DEFAULT EMBEDDING MODELS
    # This is a mapping of platforms to their default embedding models.
    platforms_to_default_embedding_model: dict[str, str] = field(
        default_factory=lambda: {
            "azure": "azure/openai/text-embedding-3-small",
            "bedrock": "bedrock/amazon/titan-embed-text-v2",
            "cortex": "cortex/snowflake/snowflake-arctic-embed-m",
            "openai": "openai/openai/text-embedding-3-small",
            "google": "google/google/text-embedding-004",
        },
        metadata=FieldMetadata(
            description="A mapping of platforms to their default embedding models.",
        ),
    )

    # MODEL CAPABLE OF DRIVING AGENTS
    # This is a list of models we allow for driving agents. More specific
    # models can be used directly, but this is the list of models we allow for
    # the generic task of "backing an agent".
    models_capable_of_driving_agents: list[str] = field(
        # Note: embeddings models never make sense here
        default_factory=lambda: [
            # Azure OpenAI
            "azure/openai/gpt-5-high",
            "azure/openai/gpt-5-medium",
            "azure/openai/gpt-5-low",
            "azure/openai/gpt-5-minimal",
            "azure/openai/gpt-5-mini",
            "azure/openai/gpt-4-1",
            "azure/openai/gpt-4-1-mini",
            "azure/openai/gpt-4o",
            "azure/openai/gpt-4o-chatgpt",
            "azure/openai/o3-high",
            "azure/openai/o3-low",
            "azure/openai/o4-mini-high",
            "azure/openai/o4-mini-low",
            # Amazon Bedrock
            "bedrock/anthropic/claude-4-5-sonnet-thinking-high",
            "bedrock/anthropic/claude-4-5-sonnet-thinking-medium",
            "bedrock/anthropic/claude-4-5-sonnet-thinking-low",
            "bedrock/anthropic/claude-4-5-sonnet",
            "bedrock/anthropic/claude-4-5-haiku-thinking-high",
            "bedrock/anthropic/claude-4-5-haiku-thinking-medium",
            "bedrock/anthropic/claude-4-5-haiku-thinking-low",
            "bedrock/anthropic/claude-4-5-haiku",
            "bedrock/anthropic/claude-4-sonnet-thinking-high",
            "bedrock/anthropic/claude-4-sonnet-thinking-medium",
            "bedrock/anthropic/claude-4-sonnet-thinking-low",
            "bedrock/anthropic/claude-4-sonnet",
            "bedrock/anthropic/claude-4-1-opus-thinking-high",
            "bedrock/anthropic/claude-4-1-opus-thinking-medium",
            "bedrock/anthropic/claude-4-1-opus-thinking-low",
            "bedrock/anthropic/claude-4-1-opus",
            "bedrock/anthropic/claude-4-opus",
            "bedrock/anthropic/claude-3-7-sonnet",
            "bedrock/anthropic/claude-3-5-sonnet",
            # Snowflake Cortex
            "cortex/anthropic/claude-3-5-sonnet",
            "cortex/anthropic/claude-3-7-sonnet",
            "cortex/anthropic/claude-4-opus",
            "cortex/anthropic/claude-4-sonnet",
            "cortex/openai/o4-mini-high",
            "cortex/openai/o4-mini-low",
            "cortex/openai/gpt-4-1",
            # OpenAI
            "openai/openai/gpt-5-high",
            "openai/openai/gpt-5-medium",
            "openai/openai/gpt-5-low",
            "openai/openai/gpt-5-minimal",
            "openai/openai/gpt-5-mini",
            "openai/openai/gpt-4-1",
            "openai/openai/gpt-4-1-mini",
            "openai/openai/gpt-4-1-nano",
            "openai/openai/gpt-4o",
            "openai/openai/o4-mini-high",
            "openai/openai/o4-mini-low",
            "openai/openai/o3-high",
            "openai/openai/o3-low",
            # Google
            "google/google/gemini-2-5-pro",
            "google/google/gemini-2-0-flash",
            "google/google/gemini-2-0-flash-lite",
            # Groq
            "groq/meta/llama-4-scout",
            "groq/meta/llama-4-maverick",
            "groq/moonshotai/kimi-k2",
            "groq/openai/gpt-oss-120b",
            "groq/openai/gpt-oss-20b",
        ],
        metadata=FieldMetadata(
            description="A mapping of model names to their platform IDs.",
        ),
    )

    # MODEL IDS
    # We use "our" generic model IDs across our stack, but we need to map them
    # to the platform-specific IDs so that we can make actual API calls to
    # various platforms with the right IDs.
    models_to_platform_specific_model_ids: dict[str, str] = field(
        default_factory=lambda: {
            # Azure OpenAI (pinning is done at the deployment level, we have no control)
            "azure/openai/gpt-5-high": "gpt-5",
            "azure/openai/gpt-5-medium": "gpt-5",
            "azure/openai/gpt-5-low": "gpt-5",
            "azure/openai/gpt-5-minimal": "gpt-5",
            "azure/openai/gpt-5-mini": "gpt-5-mini",
            "azure/openai/gpt-5-nano": "gpt-5-nano",
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
            # Amazon Bedrock (does have date/version pinning)
            "bedrock/anthropic/claude-4-5-sonnet-thinking-high": (
                "anthropic.claude-sonnet-4-5-20250929-v1:0"
            ),
            "bedrock/anthropic/claude-4-5-sonnet-thinking-medium": (
                "anthropic.claude-sonnet-4-5-20250929-v1:0"
            ),
            "bedrock/anthropic/claude-4-5-sonnet-thinking-low": (
                "anthropic.claude-sonnet-4-5-20250929-v1:0"
            ),
            "bedrock/anthropic/claude-4-5-sonnet": "anthropic.claude-sonnet-4-5-20250929-v1:0",
            "bedrock/anthropic/claude-4-5-haiku-thinking-high": (
                "anthropic.claude-haiku-4-5-20251001-v1:0"
            ),
            "bedrock/anthropic/claude-4-5-haiku-thinking-medium": (
                "anthropic.claude-haiku-4-5-20251001-v1:0"
            ),
            "bedrock/anthropic/claude-4-5-haiku-thinking-low": (
                "anthropic.claude-haiku-4-5-20251001-v1:0"
            ),
            "bedrock/anthropic/claude-4-5-haiku": "anthropic.claude-haiku-4-5-20251001-v1:0",
            "bedrock/anthropic/claude-4-sonnet-thinking-high": (
                "anthropic.claude-sonnet-4-20250514-v1:0"
            ),
            "bedrock/anthropic/claude-4-sonnet-thinking-medium": (
                "anthropic.claude-sonnet-4-20250514-v1:0"
            ),
            "bedrock/anthropic/claude-4-sonnet-thinking-low": (
                "anthropic.claude-sonnet-4-20250514-v1:0"
            ),
            "bedrock/anthropic/claude-4-sonnet": "anthropic.claude-sonnet-4-20250514-v1:0",
            "bedrock/anthropic/claude-4-1-opus-thinking-high": (
                "anthropic.claude-opus-4-1-20250805-v1:0"
            ),
            "bedrock/anthropic/claude-4-1-opus-thinking-medium": (
                "anthropic.claude-opus-4-1-20250805-v1:0"
            ),
            "bedrock/anthropic/claude-4-1-opus-thinking-low": (
                "anthropic.claude-opus-4-1-20250805-v1:0"
            ),
            "bedrock/anthropic/claude-4-1-opus": "anthropic.claude-opus-4-1-20250805-v1:0",
            "bedrock/anthropic/claude-4-opus": "anthropic.claude-opus-4-20250514-v1:0",
            "bedrock/anthropic/claude-3-7-sonnet": "anthropic.claude-3-7-sonnet-20250219-v1:0",
            "bedrock/anthropic/claude-3-5-sonnet": "anthropic.claude-3-5-sonnet-20241022-v2:0",
            "bedrock/anthropic/claude-3-5-haiku": "anthropic.claude-3-haiku-20240307-v1:0",
            "bedrock/meta/llama-4-scout": "meta.llama4-scout-17b-instruct-v1:0",
            "bedrock/meta/llama-4-maverick": "meta.llama4-maverick-17b-instruct-v1:0",
            "bedrock/cohere/command-r-plus": "cohere.command-r-plus-v1:0",
            "bedrock/amazon/titan-embed-text-v2": "amazon.titan-embed-text-v2:0:8k",
            "bedrock/amazon/titan-embed-text-v1": "amazon.titan-embed-text-v1:2:8k",
            "bedrock/cohere/cohere-embed-english-v3": "cohere.embed-english-v3:0:512",
            "bedrock/cohere/cohere-embed-multilingual-v3": "cohere.embed-multilingual-v3:0:512",
            # Snowflake Cortex (has no date/version pinning!?)
            "cortex/anthropic/claude-3-5-sonnet": "claude-3-5-sonnet",
            "cortex/anthropic/claude-3-7-sonnet": "claude-3-7-sonnet",
            "cortex/anthropic/claude-4-opus": "claude-4-opus",
            "cortex/anthropic/claude-4-1-opus": "claude-4-1-opus",
            "cortex/anthropic/claude-4-1-opus-thinking-high": "claude-4-1-opus",
            "cortex/anthropic/claude-4-1-opus-thinking-medium": "claude-4-1-opus",
            "cortex/anthropic/claude-4-1-opus-thinking-low": "claude-4-1-opus",
            "cortex/anthropic/claude-4-sonnet": "claude-4-sonnet",
            "cortex/anthropic/claude-4-sonnet-thinking-high": "claude-4-sonnet",
            "cortex/anthropic/claude-4-sonnet-thinking-medium": "claude-4-sonnet",
            "cortex/anthropic/claude-4-sonnet-thinking-low": "claude-4-sonnet",
            "cortex/anthropic/claude-4-5-sonnet": "claude-4-5-sonnet",
            "cortex/anthropic/claude-4-5-sonnet-thinking-high": "claude-4-5-sonnet",
            "cortex/anthropic/claude-4-5-sonnet-thinking-medium": "claude-4-5-sonnet",
            "cortex/anthropic/claude-4-5-sonnet-thinking-low": "claude-4-5-sonnet",
            "cortex/openai/gpt-5-high": "openai-gpt-5",
            "cortex/openai/gpt-5-medium": "openai-gpt-5",
            "cortex/openai/gpt-5-low": "openai-gpt-5",
            "cortex/openai/gpt-5-minimal": "openai-gpt-5",
            "cortex/openai/gpt-5-mini": "openai-gpt-5-mini",
            "cortex/openai/gpt-5-nano": "openai-gpt-5-nano",
            "cortex/openai/o4-mini-high": "openai-o4-mini",
            "cortex/openai/o4-mini-low": "openai-o4-mini",
            "cortex/openai/gpt-4-1": "openai-gpt-4.1",
            "cortex/meta/llama-4-scout": "llama4-scout",
            "cortex/meta/llama-4-maverick": "llama4-maverick",
            "cortex/snowflake/snowflake-arctic-embed-m": "snowflake-arctic-embed-m",
            "cortex/snowflake/snowflake-arctic-embed-l": "snowflake-arctic-embed-l",
            "cortex/voyage/voyage-multilingual": "voyage-multilingual",
            # OpenAI (does have date-based pinning)
            "openai/openai/gpt-5-high": "gpt-5-2025-08-07",
            "openai/openai/gpt-5-medium": "gpt-5-2025-08-07",
            "openai/openai/gpt-5-low": "gpt-5-2025-08-07",
            "openai/openai/gpt-5-minimal": "gpt-5-2025-08-07",
            "openai/openai/gpt-5-mini": "gpt-5-mini-2025-08-07",
            "openai/openai/gpt-5-nano": "gpt-5-nano-2025-08-07",
            "openai/openai/gpt-4-5": "gpt-4.5-preview-2025-02-27",
            "openai/openai/gpt-4-1": "gpt-4.1-2025-04-14",
            "openai/openai/gpt-4-1-mini": "gpt-4.1-mini-2025-04-14",
            "openai/openai/gpt-4-1-nano": "gpt-4.1-nano-2025-04-14",
            "openai/openai/gpt-4o": "gpt-4o-2024-08-06",
            "openai/openai/gpt-4o-mini": "gpt-4o-mini-2024-07-18",
            "openai/openai/gpt-4o-chatgpt": "chatgpt-4o-latest",
            "openai/openai/o4-mini-high": "o4-mini-2025-04-16",
            "openai/openai/o4-mini-low": "o4-mini-2025-04-16",
            "openai/openai/o3-high": "o3-2025-04-16",
            "openai/openai/o3-low": "o3-2025-04-16",
            "openai/openai/text-embedding-3-small": "text-embedding-3-small",
            "openai/openai/text-embedding-3-large": "text-embedding-3-large",
            # Google (has no date/version pinning!?)
            "google/google/gemini-2-5-pro": "gemini-2.5-pro",
            "google/google/gemini-2-0-flash": "gemini-2.0-flash",
            "google/google/gemini-2-0-flash-lite": "gemini-2.0-flash-lite",
            "google/google/text-embedding-004": "text-embedding-004",
            # Groq (has no date/version pinning!?)
            "groq/meta/llama-4-scout": "meta-llama/llama-4-scout-17b-16e-instruct",
            "groq/meta/llama-4-maverick": "meta-llama/llama-4-maverick-17b-128e-instruct",
            "groq/moonshotai/kimi-k2": "moonshotai/kimi-k2-instruct-0905",
            "groq/openai/gpt-oss-120b": "openai/gpt-oss-120b",
            "groq/openai/gpt-oss-20b": "openai/gpt-oss-20b",
            # Reducto (has no date/version pinning!?)
            "reducto/reducto/reducto-standard-parse": "standard:parse",
            "reducto/reducto/reducto-standard-extract": "standard:extract",
        },
        metadata=FieldMetadata(
            description="A mapping of model names to their provider-specific model IDs.",
        ),
    )

    # MODEL FAMILIES
    # We use model families to specialize prompts (so this is a somewhat coarser
    # granularity thing than model IDs)
    models_to_families: dict[str, str] = field(
        default_factory=lambda: {
            # Azure OpenAI
            "azure/openai/gpt-5-high": "openai-gpt",
            "azure/openai/gpt-5-medium": "openai-gpt",
            "azure/openai/gpt-5-low": "openai-gpt",
            "azure/openai/gpt-5-minimal": "openai-gpt",
            "azure/openai/gpt-5-mini": "openai-gpt",
            "azure/openai/gpt-5-nano": "openai-gpt",
            "azure/openai/gpt-4-1": "openai-gpt",
            "azure/openai/gpt-4-1-mini": "openai-gpt",
            "azure/openai/gpt-4o": "openai-gpt",
            "azure/openai/gpt-4o-mini": "openai-gpt",
            "azure/openai/gpt-4o-chatgpt": "openai-gpt",
            "azure/openai/o3-high": "openai-o-series",
            "azure/openai/o3-low": "openai-o-series",
            "azure/openai/o4-mini-high": "openai-o-series",
            "azure/openai/o4-mini-low": "openai-o-series",
            "azure/openai/text-embedding-3-small": "openai-embeddings",
            "azure/openai/text-embedding-3-large": "openai-embeddings",
            # Amazon Bedrock (does have date/version pinning)
            "bedrock/anthropic/claude-4-5-sonnet-thinking-high": "claude",
            "bedrock/anthropic/claude-4-5-sonnet-thinking-medium": "claude",
            "bedrock/anthropic/claude-4-5-sonnet-thinking-low": "claude",
            "bedrock/anthropic/claude-4-5-sonnet": "claude",
            "bedrock/anthropic/claude-4-5-haiku-thinking-high": "claude",
            "bedrock/anthropic/claude-4-5-haiku-thinking-medium": "claude",
            "bedrock/anthropic/claude-4-5-haiku-thinking-low": "claude",
            "bedrock/anthropic/claude-4-5-haiku": "claude",
            "bedrock/anthropic/claude-4-sonnet-thinking-high": "claude",
            "bedrock/anthropic/claude-4-sonnet-thinking-medium": "claude",
            "bedrock/anthropic/claude-4-sonnet-thinking-low": "claude",
            "bedrock/anthropic/claude-4-sonnet": "claude",
            "bedrock/anthropic/claude-4-1-opus-thinking-high": "claude",
            "bedrock/anthropic/claude-4-1-opus-thinking-medium": "claude",
            "bedrock/anthropic/claude-4-1-opus-thinking-low": "claude",
            "bedrock/anthropic/claude-4-1-opus": "claude",
            "bedrock/anthropic/claude-4-opus": "claude",
            "bedrock/anthropic/claude-3-7-sonnet": "claude",
            "bedrock/anthropic/claude-3-5-sonnet": "claude",
            "bedrock/anthropic/claude-3-5-haiku": "claude",
            "bedrock/meta/llama-4-scout": "llama",
            "bedrock/meta/llama-4-maverick": "llama",
            "bedrock/cohere/command-r-plus": "cohere",
            "bedrock/amazon/titan-embed-text-v2": "amazon-embeddings",
            "bedrock/amazon/titan-embed-text-v1": "amazon-embeddings",
            "bedrock/cohere/cohere-embed-english-v3": "cohere-embeddings",
            "bedrock/cohere/cohere-embed-multilingual-v3": "cohere-embeddings",
            # Snowflake Cortex (has no date/version pinning!?)
            "cortex/anthropic/claude-3-5-sonnet": "claude",
            "cortex/anthropic/claude-3-7-sonnet": "claude",
            "cortex/anthropic/claude-4-opus": "claude",
            "cortex/anthropic/claude-4-1-opus": "claude",
            "cortex/anthropic/claude-4-1-opus-thinking-high": "claude",
            "cortex/anthropic/claude-4-1-opus-thinking-medium": "claude",
            "cortex/anthropic/claude-4-1-opus-thinking-low": "claude",
            "cortex/anthropic/claude-4-sonnet-thinking-high": "claude",
            "cortex/anthropic/claude-4-sonnet-thinking-medium": "claude",
            "cortex/anthropic/claude-4-sonnet-thinking-low": "claude",
            "cortex/anthropic/claude-4-sonnet": "claude",
            "cortex/anthropic/claude-4-5-sonnet": "claude",
            "cortex/anthropic/claude-4-5-sonnet-thinking-high": "claude",
            "cortex/anthropic/claude-4-5-sonnet-thinking-medium": "claude",
            "cortex/anthropic/claude-4-5-sonnet-thinking-low": "claude",
            "cortex/openai/gpt-5-high": "openai-gpt",
            "cortex/openai/gpt-5-medium": "openai-gpt",
            "cortex/openai/gpt-5-low": "openai-gpt",
            "cortex/openai/gpt-5-minimal": "openai-gpt",
            "cortex/openai/gpt-5-mini": "openai-gpt",
            "cortex/openai/gpt-5-nano": "openai-gpt",
            "cortex/openai/o4-mini-high": "openai-o-series",
            "cortex/openai/o4-mini-low": "openai-o-series",
            "cortex/openai/gpt-4-1": "openai-gpt",
            "cortex/meta/llama-4-scout": "llama",
            "cortex/meta/llama-4-maverick": "llama",
            "cortex/snowflake/snowflake-arctic-embed-m": "snowflake-embeddings",
            "cortex/snowflake/snowflake-arctic-embed-l": "snowflake-embeddings",
            "cortex/voyage/voyage-multilingual": "voyage-embeddings",
            # OpenAI (does have date-based pinning)
            "openai/openai/gpt-5-high": "openai-gpt",
            "openai/openai/gpt-5-medium": "openai-gpt",
            "openai/openai/gpt-5-low": "openai-gpt",
            "openai/openai/gpt-5-minimal": "openai-gpt",
            "openai/openai/gpt-5-mini": "openai-gpt",
            "openai/openai/gpt-5-nano": "openai-gpt",
            "openai/openai/gpt-4-5": "openai-gpt",
            "openai/openai/gpt-4-1": "openai-gpt",
            "openai/openai/gpt-4-1-mini": "openai-gpt",
            "openai/openai/gpt-4-1-nano": "openai-gpt",
            "openai/openai/gpt-4o": "openai-gpt",
            "openai/openai/gpt-4o-mini": "openai-gpt",
            "openai/openai/gpt-4o-chatgpt": "openai-gpt",
            "openai/openai/o4-mini-high": "openai-o-series",
            "openai/openai/o4-mini-low": "openai-o-series",
            "openai/openai/o3-high": "openai-o-series",
            "openai/openai/o3-low": "openai-o-series",
            "openai/openai/text-embedding-3-small": "openai-embeddings",
            "openai/openai/text-embedding-3-large": "openai-embeddings",
            # Google (has no date/version pinning!?)
            "google/google/gemini-2-5-pro": "gemini",
            "google/google/gemini-2-0-flash": "gemini",
            "google/google/gemini-2-0-flash-lite": "gemini",
            "google/google/text-embedding-004": "google-embeddings",
            # Groq (has no date/version pinning!?)
            "groq/meta/llama-4-scout": "llama",
            "groq/meta/llama-4-maverick": "llama",
            "groq/moonshotai/kimi-k2": "moonshotai",
            "groq/openai/gpt-oss-120b": "openai",
            "groq/openai/gpt-oss-20b": "openai",
            # Reducto (has no date/version pinning!?)
            "reducto/reducto/reducto-standard-parse": "reducto",
            "reducto/reducto/reducto-standard-extract": "reducto",
        },
        metadata=FieldMetadata(
            description="A mapping of model names to their families.",
        ),
    )

    # MODELS TO MODEL TYPES
    # We use model types to determine the type of model we're using.
    models_to_model_types: dict[str, str] = field(
        default_factory=lambda: {
            # Azure OpenAI
            "azure/openai/gpt-5-high": "llm",
            "azure/openai/gpt-5-medium": "llm",
            "azure/openai/gpt-5-low": "llm",
            "azure/openai/gpt-5-minimal": "llm",
            "azure/openai/gpt-5-mini": "llm",
            "azure/openai/gpt-5-nano": "llm",
            "azure/openai/gpt-4-1": "llm",
            "azure/openai/gpt-4-1-mini": "llm",
            "azure/openai/gpt-4o": "llm",
            "azure/openai/gpt-4o-mini": "llm",
            "azure/openai/gpt-4o-chatgpt": "llm",
            "azure/openai/o3-high": "llm",
            "azure/openai/o3-low": "llm",
            "azure/openai/o4-mini-high": "llm",
            "azure/openai/o4-mini-low": "llm",
            "azure/openai/text-embedding-3-small": "embedding",
            "azure/openai/text-embedding-3-large": "embedding",
            # Amazon Bedrock
            "bedrock/anthropic/claude-4-5-sonnet-thinking-high": "llm",
            "bedrock/anthropic/claude-4-5-sonnet-thinking-medium": "llm",
            "bedrock/anthropic/claude-4-5-sonnet-thinking-low": "llm",
            "bedrock/anthropic/claude-4-5-sonnet": "llm",
            # Claude 4.5 Haiku (missing entries added)
            "bedrock/anthropic/claude-4-5-haiku-thinking-high": "llm",
            "bedrock/anthropic/claude-4-5-haiku-thinking-medium": "llm",
            "bedrock/anthropic/claude-4-5-haiku-thinking-low": "llm",
            "bedrock/anthropic/claude-4-5-haiku": "llm",
            "bedrock/anthropic/claude-4-sonnet-thinking-high": "llm",
            "bedrock/anthropic/claude-4-sonnet-thinking-medium": "llm",
            "bedrock/anthropic/claude-4-sonnet-thinking-low": "llm",
            "bedrock/anthropic/claude-4-sonnet": "llm",
            "bedrock/anthropic/claude-4-1-opus-thinking-high": "llm",
            "bedrock/anthropic/claude-4-1-opus-thinking-medium": "llm",
            "bedrock/anthropic/claude-4-1-opus-thinking-low": "llm",
            "bedrock/anthropic/claude-4-1-opus": "llm",
            "bedrock/anthropic/claude-4-opus": "llm",
            "bedrock/anthropic/claude-3-7-sonnet": "llm",
            "bedrock/anthropic/claude-3-5-sonnet": "llm",
            "bedrock/anthropic/claude-3-5-haiku": "llm",
            "bedrock/meta/llama-4-scout": "llm",
            "bedrock/meta/llama-4-maverick": "llm",
            "bedrock/cohere/command-r-plus": "llm",
            "bedrock/amazon/titan-embed-text-v2": "embedding",
            "bedrock/amazon/titan-embed-text-v1": "embedding",
            "bedrock/cohere/cohere-embed-english-v3": "embedding",
            "bedrock/cohere/cohere-embed-multilingual-v3": "embedding",
            # Snowflake Cortex
            "cortex/anthropic/claude-3-5-sonnet": "llm",
            "cortex/anthropic/claude-3-7-sonnet": "llm",
            "cortex/anthropic/claude-4-opus": "llm",
            "cortex/anthropic/claude-4-1-opus": "llm",
            "cortex/anthropic/claude-4-1-opus-thinking-high": "llm",
            "cortex/anthropic/claude-4-1-opus-thinking-medium": "llm",
            "cortex/anthropic/claude-4-1-opus-thinking-low": "llm",
            "cortex/anthropic/claude-4-sonnet-thinking-high": "llm",
            "cortex/anthropic/claude-4-sonnet-thinking-medium": "llm",
            "cortex/anthropic/claude-4-sonnet-thinking-low": "llm",
            "cortex/anthropic/claude-4-5-sonnet": "llm",
            "cortex/anthropic/claude-4-5-sonnet-thinking-high": "llm",
            "cortex/anthropic/claude-4-5-sonnet-thinking-medium": "llm",
            "cortex/anthropic/claude-4-5-sonnet-thinking-low": "llm",
            "cortex/anthropic/claude-4-sonnet": "llm",
            "cortex/openai/o4-mini-high": "llm",
            "cortex/openai/o4-mini-low": "llm",
            "cortex/openai/gpt-5-high": "llm",
            "cortex/openai/gpt-5-medium": "llm",
            "cortex/openai/gpt-5-low": "llm",
            "cortex/openai/gpt-5-minimal": "llm",
            "cortex/openai/gpt-5-mini": "llm",
            "cortex/openai/gpt-5-nano": "llm",
            "cortex/openai/gpt-4-1": "llm",
            "cortex/meta/llama-4-scout": "llm",
            "cortex/meta/llama-4-maverick": "llm",
            "cortex/snowflake/snowflake-arctic-embed-m": "embedding",
            "cortex/snowflake/snowflake-arctic-embed-l": "embedding",
            "cortex/voyage/voyage-multilingual": "embedding",
            # OpenAI
            "openai/openai/gpt-5-high": "llm",
            "openai/openai/gpt-5-medium": "llm",
            "openai/openai/gpt-5-low": "llm",
            "openai/openai/gpt-5-minimal": "llm",
            "openai/openai/gpt-5-mini": "llm",
            "openai/openai/gpt-5-nano": "llm",
            "openai/openai/gpt-4-5": "llm",
            "openai/openai/gpt-4-1": "llm",
            "openai/openai/gpt-4-1-mini": "llm",
            "openai/openai/gpt-4-1-nano": "llm",
            "openai/openai/gpt-4o": "llm",
            "openai/openai/gpt-4o-mini": "llm",
            "openai/openai/gpt-4o-chatgpt": "llm",
            "openai/openai/o4-mini-high": "llm",
            "openai/openai/o4-mini-low": "llm",
            "openai/openai/o3-high": "llm",
            "openai/openai/o3-low": "llm",
            "openai/openai/text-embedding-3-small": "embedding",
            "openai/openai/text-embedding-3-large": "embedding",
            # Google
            "google/google/gemini-2-5-pro": "llm",
            "google/google/gemini-2-0-flash": "llm",
            "google/google/gemini-2-0-flash-lite": "llm",
            "google/google/text-embedding-004": "embedding",
            # Groq
            "groq/meta/llama-4-scout": "llm",
            "groq/meta/llama-4-maverick": "llm",
            "groq/moonshotai/kimi-k2": "llm",
            "groq/openai/gpt-oss-120b": "llm",
            "groq/openai/gpt-oss-20b": "llm",
            # Reducto
            "reducto/reducto/reducto-standard-parse": "document-processor",
            "reducto/reducto/reducto-standard-extract": "document-processor",
        },
        metadata=FieldMetadata(
            description="A mapping of model names to their types.",
        ),
    )

    # MODELS TO CONTEXT WINDOW SIZES
    # Used to determine how many tokens a model can handle in a single request.
    models_to_context_window_sizes: dict[str, int] = field(
        default_factory=lambda: {
            # Azure OpenAI
            "azure/openai/gpt-5-high": 400_000,
            "azure/openai/gpt-5-medium": 400_000,
            "azure/openai/gpt-5-low": 400_000,
            "azure/openai/gpt-5-minimal": 400_000,
            "azure/openai/gpt-5-mini": 400_000,
            "azure/openai/gpt-5-nano": 400_000,
            "azure/openai/gpt-4-1": 128_000,
            "azure/openai/gpt-4-1-mini": 128_000,
            "azure/openai/gpt-4o": 128_000,
            "azure/openai/gpt-4o-mini": 128_000,
            "azure/openai/gpt-4o-chatgpt": 128_000,
            "azure/openai/o3-high": 200_000,
            "azure/openai/o3-low": 200_000,
            "azure/openai/o4-mini-high": 200_000,
            "azure/openai/o4-mini-low": 200_000,
            "azure/openai/text-embedding-3-small": 8_000,
            "azure/openai/text-embedding-3-large": 8_000,
            # Amazon Bedrock
            # 4.5 and I think 4 both have a 1M context variant... but Anthropic
            # lists that as beta, and perhaps for bedrock they have a different ID
            # for the long context versions? If a customer ever wants to try we
            # can look more into this
            "bedrock/anthropic/claude-4-5-sonnet-thinking-high": 200_000,
            "bedrock/anthropic/claude-4-5-sonnet-thinking-medium": 200_000,
            "bedrock/anthropic/claude-4-5-sonnet-thinking-low": 200_000,
            "bedrock/anthropic/claude-4-5-sonnet": 200_000,
            # Claude 4.5 Haiku (assume same context window as other Bedrock Claude models)
            "bedrock/anthropic/claude-4-5-haiku-thinking-high": 200_000,
            "bedrock/anthropic/claude-4-5-haiku-thinking-medium": 200_000,
            "bedrock/anthropic/claude-4-5-haiku-thinking-low": 200_000,
            "bedrock/anthropic/claude-4-5-haiku": 200_000,
            "bedrock/anthropic/claude-4-sonnet-thinking-high": 200_000,
            "bedrock/anthropic/claude-4-sonnet-thinking-medium": 200_000,
            "bedrock/anthropic/claude-4-sonnet-thinking-low": 200_000,
            "bedrock/anthropic/claude-4-sonnet": 200_000,
            "bedrock/anthropic/claude-4-1-opus-thinking-high": 200_000,
            "bedrock/anthropic/claude-4-1-opus-thinking-medium": 200_000,
            "bedrock/anthropic/claude-4-1-opus-thinking-low": 200_000,
            "bedrock/anthropic/claude-4-1-opus": 200_000,
            "bedrock/anthropic/claude-4-opus": 200_000,
            "bedrock/anthropic/claude-3-7-sonnet": 200_000,
            "bedrock/anthropic/claude-3-5-sonnet": 200_000,
            "bedrock/anthropic/claude-3-5-haiku": 200_000,
            "bedrock/meta/llama-4-scout": 128_000,
            "bedrock/meta/llama-4-maverick": 128_000,
            "bedrock/cohere/command-r-plus": 128_000,
            "bedrock/amazon/titan-embed-text-v2": 8_000,
            "bedrock/amazon/titan-embed-text-v1": 8_000,
            "bedrock/cohere/cohere-embed-english-v3": 8_000,
            "bedrock/cohere/cohere-embed-multilingual-v3": 8_000,
            # Snowflake Cortex
            "cortex/anthropic/claude-3-5-sonnet": 200_000,
            "cortex/anthropic/claude-3-7-sonnet": 200_000,
            "cortex/anthropic/claude-4-opus": 200_000,
            "cortex/anthropic/claude-4-1-opus": 200_000,
            "cortex/anthropic/claude-4-1-opus-thinking-high": 200_000,
            "cortex/anthropic/claude-4-1-opus-thinking-medium": 200_000,
            "cortex/anthropic/claude-4-1-opus-thinking-low": 200_000,
            "cortex/anthropic/claude-4-sonnet-thinking-high": 200_000,
            "cortex/anthropic/claude-4-sonnet-thinking-medium": 200_000,
            "cortex/anthropic/claude-4-sonnet-thinking-low": 200_000,
            "cortex/anthropic/claude-4-5-sonnet": 200_000,
            "cortex/anthropic/claude-4-5-sonnet-thinking-high": 200_000,
            "cortex/anthropic/claude-4-5-sonnet-thinking-medium": 200_000,
            "cortex/anthropic/claude-4-5-sonnet-thinking-low": 200_000,
            "cortex/anthropic/claude-4-sonnet": 200_000,
            "cortex/openai/o4-mini-high": 200_000,
            "cortex/openai/o4-mini-low": 200_000,
            "cortex/openai/gpt-5-high": 200_000,
            "cortex/openai/gpt-5-medium": 200_000,
            "cortex/openai/gpt-5-low": 200_000,
            "cortex/openai/gpt-5-minimal": 200_000,
            "cortex/openai/gpt-5-mini": 200_000,
            "cortex/openai/gpt-5-nano": 200_000,
            "cortex/openai/gpt-4-1": 128_000,
            "cortex/meta/llama-4-scout": 128_000,
            "cortex/meta/llama-4-maverick": 128_000,
            "cortex/snowflake/snowflake-arctic-embed-m": 8_000,
            "cortex/snowflake/snowflake-arctic-embed-l": 8_000,
            "cortex/voyage/voyage-multilingual": 8_000,
            # OpenAI
            "openai/openai/gpt-5-high": 400_000,
            "openai/openai/gpt-5-medium": 400_000,
            "openai/openai/gpt-5-low": 400_000,
            "openai/openai/gpt-5-minimal": 400_000,
            "openai/openai/gpt-5-mini": 400_000,
            "openai/openai/gpt-5-nano": 400_000,
            "openai/openai/gpt-4-5": 128_000,
            "openai/openai/gpt-4-1": 128_000,
            "openai/openai/gpt-4-1-mini": 128_000,
            "openai/openai/gpt-4-1-nano": 32_000,
            "openai/openai/gpt-4o": 128_000,
            "openai/openai/gpt-4o-mini": 128_000,
            "openai/openai/gpt-4o-chatgpt": 128_000,
            "openai/openai/o4-mini-high": 200_000,
            "openai/openai/o4-mini-low": 200_000,
            "openai/openai/o3-high": 200_000,
            "openai/openai/o3-low": 200_000,
            "openai/openai/text-embedding-3-small": 8_000,
            "openai/openai/text-embedding-3-large": 8_000,
            # Google
            "google/google/gemini-2-5-pro": 1_000_000,
            "google/google/gemini-2-0-flash": 1_000_000,
            "google/google/gemini-2-0-flash-lite": 1_000_000,
            "google/google/text-embedding-004": 8_000,
            # Groq
            "groq/meta/llama-4-scout": 128_000,
            "groq/meta/llama-4-maverick": 128_000,
            "groq/moonshotai/kimi-k2": 128_000,
            "groq/openai/gpt-oss-120b": 128_000,
            "groq/openai/gpt-oss-20b": 128_000,
            # Reducto (these are kinda weird... effectively unlimited)
            "reducto/reducto/reducto-standard-parse": 10_000_000,
            "reducto/reducto/reducto-standard-extract": 10_000_000,
        },
        metadata=FieldMetadata(
            description="A mapping of model names to their context window sizes.",
        ),
    )

    # MODEL IDS TO ARCHITECTURE OVERRIDES
    # If a model is in this mapping, an agent created with an incompatible architecture
    # will be overridden to an architecture that supports the model. (If feasible, if
    # there's no compatible architecture, we'll raise an error.)
    models_to_architecture_overrides: dict[str, list[str]] = field(
        default_factory=lambda: {
            # Azure OpenAI
            "azure/openai/gpt-5-high": [EXPERIMENTAL_ARCH_2_0_0, CONSISTENCY_ARCH_2_0_0],
            "azure/openai/gpt-5-medium": [EXPERIMENTAL_ARCH_2_0_0, CONSISTENCY_ARCH_2_0_0],
            "azure/openai/gpt-5-low": [EXPERIMENTAL_ARCH_2_0_0, CONSISTENCY_ARCH_2_0_0],
            "azure/openai/gpt-5-minimal": [EXPERIMENTAL_ARCH_2_0_0, CONSISTENCY_ARCH_2_0_0],
            "azure/openai/gpt-5-mini": [EXPERIMENTAL_ARCH_2_0_0, CONSISTENCY_ARCH_2_0_0],
            "azure/openai/gpt-5-nano": [EXPERIMENTAL_ARCH_2_0_0, CONSISTENCY_ARCH_2_0_0],
            # OpenAI
            "openai/openai/gpt-5-high": [EXPERIMENTAL_ARCH_2_0_0, CONSISTENCY_ARCH_2_0_0],
            "openai/openai/gpt-5-medium": [EXPERIMENTAL_ARCH_2_0_0, CONSISTENCY_ARCH_2_0_0],
            "openai/openai/gpt-5-low": [EXPERIMENTAL_ARCH_2_0_0, CONSISTENCY_ARCH_2_0_0],
            "openai/openai/gpt-5-minimal": [EXPERIMENTAL_ARCH_2_0_0, CONSISTENCY_ARCH_2_0_0],
            "openai/openai/gpt-5-mini": [EXPERIMENTAL_ARCH_2_0_0, CONSISTENCY_ARCH_2_0_0],
            "openai/openai/gpt-5-nano": [EXPERIMENTAL_ARCH_2_0_0, CONSISTENCY_ARCH_2_0_0],
            # Bedrock
            "bedrock/anthropic/claude-4-5-haiku-thinking-high": [
                EXPERIMENTAL_ARCH_2_0_0,
                CONSISTENCY_ARCH_2_0_0,
            ],
            "bedrock/anthropic/claude-4-5-haiku-thinking-medium": [
                EXPERIMENTAL_ARCH_2_0_0,
                CONSISTENCY_ARCH_2_0_0,
            ],
            "bedrock/anthropic/claude-4-5-haiku-thinking-low": [
                EXPERIMENTAL_ARCH_2_0_0,
                CONSISTENCY_ARCH_2_0_0,
            ],
            "bedrock/anthropic/claude-4-5-haiku": [EXPERIMENTAL_ARCH_2_0_0, CONSISTENCY_ARCH_2_0_0],
            "bedrock/anthropic/claude-4-5-sonnet-thinking-high": [
                EXPERIMENTAL_ARCH_2_0_0,
                CONSISTENCY_ARCH_2_0_0,
            ],
            "bedrock/anthropic/claude-4-5-sonnet-thinking-medium": [
                EXPERIMENTAL_ARCH_2_0_0,
                CONSISTENCY_ARCH_2_0_0,
            ],
            "bedrock/anthropic/claude-4-5-sonnet-thinking-low": [
                EXPERIMENTAL_ARCH_2_0_0,
                CONSISTENCY_ARCH_2_0_0,
            ],
            "bedrock/anthropic/claude-4-5-sonnet": [
                EXPERIMENTAL_ARCH_2_0_0,
                CONSISTENCY_ARCH_2_0_0,
            ],
            "bedrock/anthropic/claude-4-sonnet-thinking-high": [
                EXPERIMENTAL_ARCH_2_0_0,
                CONSISTENCY_ARCH_2_0_0,
            ],
            "bedrock/anthropic/claude-4-sonnet-thinking-medium": [
                EXPERIMENTAL_ARCH_2_0_0,
                CONSISTENCY_ARCH_2_0_0,
            ],
            "bedrock/anthropic/claude-4-sonnet-thinking-low": [
                EXPERIMENTAL_ARCH_2_0_0,
                CONSISTENCY_ARCH_2_0_0,
            ],
            "bedrock/anthropic/claude-4-1-opus-thinking-high": [
                EXPERIMENTAL_ARCH_2_0_0,
                CONSISTENCY_ARCH_2_0_0,
            ],
            "bedrock/anthropic/claude-4-1-opus-thinking-medium": [
                EXPERIMENTAL_ARCH_2_0_0,
                CONSISTENCY_ARCH_2_0_0,
            ],
            "bedrock/anthropic/claude-4-1-opus-thinking-low": [
                EXPERIMENTAL_ARCH_2_0_0,
                CONSISTENCY_ARCH_2_0_0,
            ],
            # Cortex
            "cortex/anthropic/claude-4-1-opus": [EXPERIMENTAL_ARCH_2_0_0, CONSISTENCY_ARCH_2_0_0],
            "cortex/anthropic/claude-4-1-opus-thinking-high": [
                EXPERIMENTAL_ARCH_2_0_0,
                CONSISTENCY_ARCH_2_0_0,
            ],
            "cortex/anthropic/claude-4-1-opus-thinking-medium": [
                EXPERIMENTAL_ARCH_2_0_0,
                CONSISTENCY_ARCH_2_0_0,
            ],
            "cortex/anthropic/claude-4-1-opus-thinking-low": [
                EXPERIMENTAL_ARCH_2_0_0,
                CONSISTENCY_ARCH_2_0_0,
            ],
            "cortex/anthropic/claude-4-sonnet-thinking-high": [
                EXPERIMENTAL_ARCH_2_0_0,
                CONSISTENCY_ARCH_2_0_0,
            ],
            "cortex/anthropic/claude-4-sonnet-thinking-medium": [
                EXPERIMENTAL_ARCH_2_0_0,
                CONSISTENCY_ARCH_2_0_0,
            ],
            "cortex/anthropic/claude-4-sonnet-thinking-low": [
                EXPERIMENTAL_ARCH_2_0_0,
                CONSISTENCY_ARCH_2_0_0,
            ],
            "cortex/anthropic/claude-4-5-sonnet": [EXPERIMENTAL_ARCH_2_0_0, CONSISTENCY_ARCH_2_0_0],
            "cortex/anthropic/claude-4-5-sonnet-thinking-high": [
                EXPERIMENTAL_ARCH_2_0_0,
                CONSISTENCY_ARCH_2_0_0,
            ],
            "cortex/anthropic/claude-4-5-sonnet-thinking-medium": [
                EXPERIMENTAL_ARCH_2_0_0,
                CONSISTENCY_ARCH_2_0_0,
            ],
            "cortex/anthropic/claude-4-5-sonnet-thinking-low": [
                EXPERIMENTAL_ARCH_2_0_0,
                CONSISTENCY_ARCH_2_0_0,
            ],
            "cortex/openai/gpt-5-high": [EXPERIMENTAL_ARCH_2_0_0, CONSISTENCY_ARCH_2_0_0],
            "cortex/openai/gpt-5-medium": [EXPERIMENTAL_ARCH_2_0_0, CONSISTENCY_ARCH_2_0_0],
            "cortex/openai/gpt-5-low": [EXPERIMENTAL_ARCH_2_0_0, CONSISTENCY_ARCH_2_0_0],
            "cortex/openai/gpt-5-minimal": [EXPERIMENTAL_ARCH_2_0_0, CONSISTENCY_ARCH_2_0_0],
            "cortex/openai/gpt-5-mini": [EXPERIMENTAL_ARCH_2_0_0, CONSISTENCY_ARCH_2_0_0],
            "cortex/openai/gpt-5-nano": [EXPERIMENTAL_ARCH_2_0_0, CONSISTENCY_ARCH_2_0_0],
            # groq
            "groq/openai/gpt-oss-120b": [EXPERIMENTAL_ARCH_2_0_0, CONSISTENCY_ARCH_2_0_0],
            "groq/openai/gpt-oss-20b": [EXPERIMENTAL_ARCH_2_0_0, CONSISTENCY_ARCH_2_0_0],
            "groq/moonshotai/kimi-k2": [EXPERIMENTAL_ARCH_2_0_0, CONSISTENCY_ARCH_2_0_0],
            "groq/meta/llama-4-scout": [EXPERIMENTAL_ARCH_2_0_0, CONSISTENCY_ARCH_2_0_0],
            "groq/meta/llama-4-maverick": [EXPERIMENTAL_ARCH_2_0_0, CONSISTENCY_ARCH_2_0_0],
        },
        metadata=FieldMetadata(
            description="A mapping of model IDs to the architectures they require to be used with.",
        ),
    )


def resolve_provider_from_model_name(
    model_name: str,
    default_if_no_match: str | None = None,
) -> str:
    """Resolve a model name to a provider.

    If the provider cannot be determined, we'll return the default if given,
    otherwise we'll raise an error.
    """
    # First, collect any generic model id that ends with the given model name
    matching_models = [
        model
        for model in PlatformModelConfigs.models_to_platform_specific_model_ids.keys()
        if model.endswith(f"/{model_name}")
    ]
    # If we have no matches, we'll return the default if provided
    if len(matching_models) == 0:
        if default_if_no_match is None:
            # No default provided, so we'll raise an error
            raise ValueError(f"No matching model found for {model_name}")
        return default_if_no_match
    # If we have multiple matches, we'll return the first one
    first_match = matching_models[0]
    parts = first_match.split("/")
    if len(parts) > 1:
        return parts[1]
    # Malformed generic model id? Should never happen
    raise ValueError(f"No provider found for {model_name}")


async def resolve_generic_model_id_to_platform_specific_model_id(  # noqa: C901, PLR0912
    platform_client: PlatformClient,
    model_id: str,
) -> str:
    """Resolve a generic model ID to a platform-specific model ID.

    First, we see if the model ID is fully qualified and in the
    models_to_platform_specific_model_ids map. If it is, we map
    and return it.

    Next, we see if, for items in the models_to_platform_specific_model_ids map,
    if the platform kind is a prefix of an item in the map and if the model ID
    is a suffix of the item in the map. If it is, we return the item in the map.

    Last option, if we see that the model_id is in the form platform/provider/model,
    then we're going to strip the platform/provider/ prefix and assume that we
    have been given a provider-specific model ID already, we'll make sure
    it's valid and return it if it is.

    If we don't find a match, we raise an error.
    """
    # First, let's get the models that are actually available on the platform
    # this will be a map from provider -> [list of platform-specific model IDs]
    available_models = await platform_client.get_available_models()

    # Next, let's parse the model_id into a platform/provider/model
    platform, provider, model = (platform_client.parameters.kind, None, model_id)
    if model_id.count("/") == 2:  # noqa: PLR2004 (platform/provider/model)
        platform, provider, model = model_id.split("/")
    elif model_id.count("/") == 1:
        platform, model = model_id.split("/")

    def _get_error_data():
        return {
            "generic_model_id": model_id,
            "resolution_platform_kind": platform_client.parameters.kind,
            "available_models_for_platform": available_models,
            "resolved_platform": platform,
            "resolved_provider": provider,
            "resolved_model": model,
        }

    # Make sure the platform matches the platform we're using
    if platform != platform_client.parameters.kind:
        raise PlatformHTTPError(
            error_code=ErrorCode.BAD_REQUEST,
            message=(
                f"Failed to resolve the generic model ID {model_id} to a platform-specific "
                f"model ID, the generic model ID points to a different platform than the "
                f"platform being used to resolve it. (given platform: {platform}, platform "
                f"being used to resolve the generic model ID: {platform_client.parameters.kind})"
            ),
            data=_get_error_data(),
        )

    # If we're missing the provider, let's go and try to find a match
    if provider is None:
        valid_generic_ids = PlatformModelConfigs.models_to_platform_specific_model_ids.keys()
        for fully_qualified_generic_id in valid_generic_ids:
            if not fully_qualified_generic_id.startswith(f"{platform}/"):
                continue
            if not fully_qualified_generic_id.endswith(f"/{model}"):
                continue
            # ASSUMPTION: our fully qualified generic IDs are always in the form
            # platform/provider/model, so we can just split on the / and get the provider
            # We always have exactly two '/' in the fully qualified generic ID
            provider = fully_qualified_generic_id.split("/")[1]
            break

    # If we're still missing the provider, something is wrong
    if provider is None:
        raise PlatformHTTPError(
            error_code=ErrorCode.BAD_REQUEST,
            message=(
                f"Failed to resolve the provider for the generic model ID {model_id}, "
                f"try using a fully qualified model ID (platform/provider/model) instead."
            ),
            data=_get_error_data(),
        )

    # At this point, we should have a platform, provider, and model
    # And this either exists in the map or it doesn't (and we're going
    # to assume that we've _already_ been given a provider-specific model ID)
    qualified_model_id = f"{platform}/{provider}/{model}"
    provider_models = available_models.get(provider)
    if provider_models is None:
        available_providers = available_models.keys()
        raise PlatformHTTPError(
            error_code=ErrorCode.BAD_REQUEST,
            message=(
                f"Failed to resolve the generic model ID {model_id} to a platform-specific "
                f"model ID because provider '{provider}' is not available for the configured "
                f"credentials. Available providers: {available_providers}"
            ),
            data=_get_error_data(),
        )

    if qualified_model_id in PlatformModelConfigs.models_to_platform_specific_model_ids:
        platform_specific_model_id = PlatformModelConfigs.models_to_platform_specific_model_ids[
            qualified_model_id
        ]
        if platform_specific_model_id in provider_models:
            return platform_specific_model_id
        # This is a case that really should never happen, but we'll handle it
        # just in case (I guess maybe someone might not have access to a model
        # the platform normally supports)
        elif platform == "openai":
            raise PlatformHTTPError(
                error_code=ErrorCode.BAD_REQUEST,
                message=(
                    f"Failed to resolve the generic model ID {model_id} to a platform-specific "
                    f"model ID, the platform-specific model ID {platform_specific_model_id} "
                    "is not available on the platform as configured. "
                    "Please make sure your OpenAI API key has sufficient permissions to access "
                    "the model you have requested."
                    f" Available models: {available_models[provider]}"
                ),
                data=_get_error_data(),
            )
        else:
            raise PlatformHTTPError(
                error_code=ErrorCode.BAD_REQUEST,
                message=(
                    f"Failed to resolve the generic model ID {model_id} to a platform-specific "
                    f"model ID, the platform-specific model ID {platform_specific_model_id} "
                    "is not available on the platform as configured."
                    "Please make sure your credentials can access the model "
                    "you have requested."
                ),
                data=_get_error_data(),
            )

    # In this scenario, we're going to trust that the model ID (unqualified) is
    # a valid platform-specific model ID, and we'll make sure it's available
    # on the platform
    if model in provider_models:
        return model
    else:
        raise PlatformHTTPError(
            error_code=ErrorCode.BAD_REQUEST,
            message=(
                f"Failed to resolve the generic model ID {model_id} to a platform-specific "
                f"model ID, the platform-specific model ID {model} is not available on the "
                f"platform as configured."
            ),
            data=_get_error_data(),
        )
