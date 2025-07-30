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
    if slug.endswith("-high") or slug.endswith("-low"):
        slug = slug.rsplit("-", 1)[0]

    # Handle specific model name differences between our config and llms.json
    slug_mappings = {
        # Claude models: our config uses claude-3-5-sonnet but llms.json has claude-35-sonnet
        "claude-3-5-sonnet": "claude-35-sonnet",
        # Note: claude-3-5-haiku exists as-is in llms.json so no mapping needed
        # Gemini models: our config uses simplified names but llms.json has versioned slugs
        "gemini-2-0-flash-lite": "gemini-2-0-flash-lite-001",
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
    # Normalize the slug for lookup (handles -high/-low suffixes)
    normalized_slug = _normalize_model_slug_for_lookup(slug)

    # Get model from in-memory data loader
    return llms_metadata_loader.get_model_by_slug(normalized_slug)


@dataclass(frozen=True)
class PlatformModelConfigs(Configuration):
    """Configuration describing models across all platforms."""

    # PLATFORMS TO DEFAULT MODELS
    # This is a mapping of platforms to their default models.
    platforms_to_default_model: dict[str, str] = field(
        default_factory=lambda: {
            "azure": "azure/openai/gpt-4-1",
            "bedrock": "bedrock/anthropic/claude-4-sonnet",
            "cortex": "cortex/anthropic/claude-3-5-sonnet",
            "openai": "openai/openai/gpt-4-1",
            "google": "google/google/gemini-2-5-pro",
            "groq": "groq/moonshotai/kimi-k2",
            "reducto": "reducto/reducto/reducto-standard-parse",
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
            "azure/openai/gpt-4-1",
            "azure/openai/gpt-4-1-mini",
            "azure/openai/gpt-4o",
            "azure/openai/gpt-4o-chatgpt",
            "azure/openai/o3-high",
            "azure/openai/o3-low",
            "azure/openai/o4-mini-high",
            "azure/openai/o4-mini-low",
            # Amazon Bedrock
            "bedrock/anthropic/claude-4-sonnet",
            "bedrock/anthropic/claude-4-opus",
            "bedrock/anthropic/claude-3-7-sonnet",
            "bedrock/anthropic/claude-3-5-sonnet",
            "bedrock/anthropic/claude-3-5-haiku",
            "bedrock/deepseek/deepseek-r1",
            "bedrock/meta/llama-4-scout",
            "bedrock/meta/llama-4-maverick",
            "bedrock/cohere/command-r-plus",
            # Snowflake Cortex
            "cortex/anthropic/claude-3-5-sonnet",
            "cortex/anthropic/claude-3-7-sonnet",
            "cortex/anthropic/claude-4-opus",
            "cortex/anthropic/claude-4-sonnet",
            "cortex/openai/o4-mini-high",
            "cortex/openai/o4-mini-low",
            "cortex/openai/gpt-4-1",
            # OpenAI
            "openai/openai/gpt-4-5",
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
            "groq/meta/llama-3-3-instruct-70b",
            "groq/meta/llama-4-scout",
            "groq/meta/llama-4-maverick",
            "groq/moonshotai/kimi-k2",
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
            "bedrock/anthropic/claude-4-sonnet": "anthropic.claude-sonnet-4-20250514-v1:0",
            "bedrock/anthropic/claude-4-opus": "anthropic.claude-opus-4-20250514-v1:0",
            "bedrock/anthropic/claude-3-7-sonnet": "anthropic.claude-3-7-sonnet-20250219-v1:0",
            "bedrock/anthropic/claude-3-5-sonnet": "anthropic.claude-3-5-sonnet-20241022-v2:0",
            "bedrock/anthropic/claude-3-5-haiku": "anthropic.claude-3-haiku-20240307-v1:0",
            "bedrock/deepseek/deepseek-r1": "deepseek.r1-v1:0",
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
            "cortex/anthropic/claude-4-sonnet": "claude-4-sonnet",
            "cortex/openai/o4-mini-high": "o4-mini",
            "cortex/openai/o4-mini-low": "o4-mini",
            "cortex/openai/gpt-4-1": "gpt-4.1",
            "cortex/deepseek/deepseek-r1": "deepseek-r1",
            "cortex/meta/llama-4-scout": "llama-4-scout",
            "cortex/meta/llama-4-maverick": "llama-4-maverick",
            "cortex/snowflake/snowflake-arctic-embed-m": "snowflake-arctic-embed-m",
            "cortex/snowflake/snowflake-arctic-embed-l": "snowflake-arctic-embed-l",
            "cortex/voyage/voyage-multilingual": "voyage-multilingual",
            # OpenAI (does have date-based pinning)
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
            "groq/meta/llama-3-3-instruct-70b": "llama-3.3-70b-versatile",
            "groq/meta/llama-4-scout": "llama-4-scout-17b-16e-instruct",
            "groq/meta/llama-4-maverick": "llama-4-maverick-17b-128e-instruct",
            "groq/moonshotai/kimi-k2": "moonshotai/kimi-k2-instruct",
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
            "bedrock/anthropic/claude-4-sonnet": "claude",
            "bedrock/anthropic/claude-4-opus": "claude",
            "bedrock/anthropic/claude-3-7-sonnet": "claude",
            "bedrock/anthropic/claude-3-5-sonnet": "claude",
            "bedrock/anthropic/claude-3-5-haiku": "claude",
            "bedrock/deepseek/deepseek-r1": "deepseek",
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
            "cortex/anthropic/claude-4-sonnet": "claude",
            "cortex/openai/o4-mini-high": "openai-o-series",
            "cortex/openai/o4-mini-low": "openai-o-series",
            "cortex/openai/gpt-4-1": "openai-gpt",
            "cortex/deepseek/deepseek-r1": "deepseek",
            "cortex/meta/llama-4-scout": "llama",
            "cortex/meta/llama-4-maverick": "llama",
            "cortex/snowflake/snowflake-arctic-embed-m": "snowflake-embeddings",
            "cortex/snowflake/snowflake-arctic-embed-l": "snowflake-embeddings",
            "cortex/voyage/voyage-multilingual": "voyage-embeddings",
            # OpenAI (does have date-based pinning)
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
            "groq/meta/llama-3-3-instruct-70b": "llama",
            "groq/meta/llama-4-scout": "llama",
            "groq/meta/llama-4-maverick": "llama",
            "groq/moonshotai/kimi-k2": "moonshotai",
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
            "bedrock/anthropic/claude-4-sonnet": "llm",
            "bedrock/anthropic/claude-4-opus": "llm",
            "bedrock/anthropic/claude-3-7-sonnet": "llm",
            "bedrock/anthropic/claude-3-5-sonnet": "llm",
            "bedrock/anthropic/claude-3-5-haiku": "llm",
            "bedrock/deepseek/deepseek-r1": "llm",
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
            "cortex/anthropic/claude-4-sonnet": "llm",
            "cortex/openai/o4-mini-high": "llm",
            "cortex/openai/o4-mini-low": "llm",
            "cortex/openai/gpt-4-1": "llm",
            "cortex/deepseek/deepseek-r1": "llm",
            "cortex/meta/llama-4-scout": "llm",
            "cortex/meta/llama-4-maverick": "llm",
            "cortex/snowflake/snowflake-arctic-embed-m": "embedding",
            "cortex/snowflake/snowflake-arctic-embed-l": "embedding",
            "cortex/voyage/voyage-multilingual": "embedding",
            # OpenAI
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
            "groq/meta/llama-3-3-instruct-70b": "llm",
            "groq/meta/llama-4-scout": "llm",
            "groq/meta/llama-4-maverick": "llm",
            "groq/moonshotai/kimi-k2": "llm",
            # Reducto
            "reducto/reducto/reducto-standard-parse": "document-processor",
            "reducto/reducto/reducto-standard-extract": "document-processor",
        },
        metadata=FieldMetadata(
            description="A mapping of model names to their types.",
        ),
    )


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
    if qualified_model_id in PlatformModelConfigs.models_to_platform_specific_model_ids:
        platform_specific_model_id = PlatformModelConfigs.models_to_platform_specific_model_ids[
            qualified_model_id
        ]
        if platform_specific_model_id in available_models[provider]:
            return platform_specific_model_id
        else:
            # This is a case that really should never happen, but we'll handle it
            # just in case (I guess maybe someone might not have access to a model
            # the platform normally supports)
            raise PlatformHTTPError(
                error_code=ErrorCode.BAD_REQUEST,
                message=(
                    f"Failed to resolve the generic model ID {model_id} to a platform-specific "
                    f"model ID, the platform-specific model ID {platform_specific_model_id} "
                    f"is not available on the platform as configured."
                ),
                data=_get_error_data(),
            )

    # In this scenario, we're going to trust that the model ID (unqualified) is
    # a valid platform-specific model ID, and we'll make sure it's available
    # on the platform
    if model in available_models[provider]:
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
