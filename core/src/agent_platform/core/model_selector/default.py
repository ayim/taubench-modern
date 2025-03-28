from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from agent_platform_core.configurations import Configuration
from agent_platform_core.model_selector.base import ModelSelector
from agent_platform_core.model_selector.selection_request import ModelSelectionRequest

if TYPE_CHECKING:
    from agent_platform_core.platforms import PlatformClient


@dataclass(frozen=True)
class ModelMappingConfig(Configuration):
    """
    Configuration mapping across multiple dimensions:
      (platform, provider, model_type, quality_tier) -> model_name
    """

    mappings: dict[str, dict[str, dict[str, dict[str, str]]]] = field(
        default_factory=lambda: {
            "anthropic": {
                "anthropic": {
                    "llm": {
                        "best": "claude-3-5-sonnet",
                        "balanced": "claude-3-5-sonnet",
                        "fastest": "claude-3-5-haiku",
                    },
                },
            },
            "bedrock": {
                "anthropic": {
                    "llm": {
                        "best": "claude-3-5-sonnet",
                        "balanced": "claude-3-5-sonnet",
                        "fastest": "claude-3-5-haiku",
                    },
                },
                "amazon": {
                    "embedding": {
                        "best": "titan-embed-text-v2",
                        "balanced": "titan-embed-text-v2",
                        "fastest": "titan-embed-text-v1",
                    },
                },
                "cohere": {
                    "embedding": {
                        "best": "cohere-embed-multilingual-v3",
                        "balanced": "cohere-embed-multilingual-v3",
                        "fastest": "cohere-embed-english-v3",
                    },
                },
                # Potentially other providers on bedrock
            },
            "openai": {
                "openai": {
                    "llm": {
                        "best": "o3-mini-high",
                        "balanced": "gpt-4o",
                        "fastest": "gpt-4o-mini",
                    },
                    "text-to-image": {
                        "best": "openai-dalle2-highres",
                        "balanced": "openai-dalle2",
                        "fastest": "openai-dalle2-lite",
                    },
                    "embedding": {
                        "best": "text-embedding-3-large",
                        "balanced": "text-embedding-3-large",
                        "fastest": "text-embedding-3-small",
                    },
                },
            },
        },
    )

    def get_model_name(
        self,
        platform: str,
        provider: str,
        model_type: str,
        tier: str,
    ) -> str | None:
        """Get model name from the multi-dimensional map."""
        # Normalize to lower case as needed
        p = platform.lower()
        r = provider.lower()
        mt = model_type.lower()
        t = tier.lower()

        try:
            return self.mappings[p][r][mt][t]
        except KeyError:
            return None


@dataclass(frozen=True)
class ModelFallbackConfig(Configuration):
    """Configuration for model fallback chains.

    Defines fallback chains for when a requested model is unavailable.
    """

    FALLBACKS: dict[str, list[str]] = field(
        default_factory=lambda: {
            "claude-3-5-sonnet": ["gpt-4o", "claude-3-5-haiku"],
            "o1": ["gpt-4o", "claude-3-5-sonnet"],
            "gpt-4o": ["claude-3-5-sonnet", "gpt-4o-mini"],
            "titan-embed-text-v2": ["titan-embed-text-v1"],
            "cohere-embed-multilingual-v3": ["cohere-embed-english-v3"],
        },
    )

    def get_fallbacks(self, model_name: str) -> list[str]:
        """Get the fallback chain for a specific model.

        Args:
            model_name: The name of the model

        Returns:
            List of model names to try as fallbacks, or empty list if none defined
        """
        return self.FALLBACKS.get(model_name, [])


@dataclass(frozen=True)
class PlatformDefaultModelConfig(Configuration):
    """Configuration for default models by platform.

    Defines the default model to use for each platform when no specific model
    or quality tier is requested. The model type is necessary to specify.
    """

    PLATFORM_DEFAULTS: dict[str, dict[str, str]] = field(
        default_factory=lambda: {
            "bedrock": {
                "llm": "claude-3-5-sonnet",
                "embedding": "titan-embed-text-v2",
            },
            "openai": {
                "llm": "gpt-4o",
                "text-to-image": "openai-dalle2",
                "embedding": "text-embedding-3-large",
            },
            "anthropic": {
                "llm": "claude-3-5-sonnet",
            },
        },
    )

    def get_default_model(self, platform: str, model_type: str) -> str | None:
        """Get the default model for a specific platform.

        Args:
            platform: The platform name (e.g., "bedrock", "openai")

        Returns:
            The default model name or None if not defined
        """
        defaults_by_type = self.PLATFORM_DEFAULTS.get(platform.lower())
        if defaults_by_type:
            return defaults_by_type.get(model_type, None)
        return None


@dataclass
class DefaultModelSelector(ModelSelector):
    """
    An enhanced model selector that:
      1. Allows specifying a direct model name
      2. Allows specifying a provider + model_type + tier
      3. Falls back to platform defaults
      4. Uses fallback chains if a chosen model is unavailable
    """

    model_mapping_config: ModelMappingConfig = field(
        default_factory=ModelMappingConfig,
    )
    fallback_config: ModelFallbackConfig = field(
        default_factory=ModelFallbackConfig,
    )
    platform_default_config: PlatformDefaultModelConfig = field(
        default_factory=PlatformDefaultModelConfig,
    )

    def _find_model_by_name(
        self,
        platform: "PlatformClient",
        model_name: str,
    ) -> str | None:
        """Scan all supported providers for a given model name."""
        for _, models in platform.configs.supported_models_by_provider.items():
            for model in models:
                if model == model_name:
                    return model
        return None

    def _get_model_with_fallbacks(
        self,
        platform: "PlatformClient",
        model_name: str,
    ) -> str | None:
        """Try primary model, then fallback chain."""
        primary = self._find_model_by_name(platform, model_name)
        if primary:
            return primary

        for fallback_name in self.fallback_config.get_fallbacks(model_name):
            fb_model = self._find_model_by_name(platform, fallback_name)
            if fb_model:
                return fb_model
        return None

    def select_model(   # noqa: C901 (lots of necessary nested conditionals)
        self,
        platform: "PlatformClient",
        request: ModelSelectionRequest | None = None,
    ) -> str:
        """
        Attempt to find a model with the following priority:
          1. If request.direct_model_name is provided -> use it (with fallback).
          2. Else if (provider, model_type, tier) is specified -> lookup
             in config (with fallback).
          3. Else use platform default (with fallback).
          4. If still none found, pick the first from platform.configs.supported_models.
          5. If still none, raise ValueError.
        """
        if request is None:
            request = ModelSelectionRequest()  # empty

        platform_name = platform.name.lower()
        if not platform_name:
            raise ValueError("Platform name not specified in configuration")

        # 1) If direct model name is given, try that first.
        if request.direct_model_name:
            maybe_model = self._get_model_with_fallbacks(
                platform, request.direct_model_name,
            )
            if maybe_model:
                return maybe_model
            # If it fails, we raise right away or keep going.
            # Example: We'll raise for clarity:
            raise ValueError(
                f"Could not resolve direct model name '{request.direct_model_name}'",
            )

        # 2) If provider/model_type/tier was specified, try to look up
        #    in the multi-dimensional ModelMappingConfig. We only do this
        #    if all three fields are available, or we can decide on defaults.
        if request.provider or request.model_type or request.quality_tier:
            # We need to handle partial specification. Let's define some defaults:
            model_type = (
                request.model_type or platform.configs.default_model_type
            )
            provider = (
                request.provider or
                platform.configs.default_platform_provider[model_type]
            )
            tier = (
                request.quality_tier or
                platform.configs.default_quality_tier[model_type]
            )

            model_name = self.model_mapping_config.get_model_name(
                platform=platform_name,
                provider=provider,
                model_type=model_type,
                tier=tier,
            )
            if model_name:
                maybe_model = self._get_model_with_fallbacks(
                    platform, model_name,
                )
                if maybe_model:
                    return maybe_model
                else:
                    # If there's a config but we can't find or fallback
                    raise ValueError(
                        f"Model '{model_name}' for (provider={provider}, "
                        f"type={model_type}, tier={tier}) not found "
                        "or fallback failed.",
                    )
            # If that didn't work, we continue on to next step

        # 3a) If at this point we don't have a model, and we have no model type,
        # that's an error
        if not request.model_type:
            raise ValueError(
                f"Failed to find model for platform '{platform_name}' "
                f"with selection request: {request}",
            )

        # 3b) If the request is entirely empty OR if the above didn't yield a model,
        #    try platform default (filtered by model type, that's important!)
        default_model_name = self.platform_default_config.get_default_model(
            platform_name, request.model_type,
        )
        if default_model_name:
            maybe_model = self._get_model_with_fallbacks(
                platform, default_model_name,
            )
            if maybe_model:
                return maybe_model

        # 4) If we still don't have a model, check if the platform has a
        #    `supported_models` list and use the first one
        if (
            hasattr(platform.configs, "supported_models")
            and platform.configs.supported_models
        ):
            return platform.configs.supported_models[0]

        # 5) If we get here, no suitable model was found
        raise ValueError(
            f"Could not find suitable model for platform '{platform_name}' "
            f"with selection request: {request}",
        )
