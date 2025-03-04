from dataclasses import dataclass, field
from typing import Literal

from agent_server_types_v2.configurations import Configuration
from agent_server_types_v2.model_selector.base import ModelSelector
from agent_server_types_v2.models.model import Model
from agent_server_types_v2.models.provider import ModelProviders

# TODO: We also need to provide for a "type" or "category" of model, that is,
# we might have to select an "embedding" model, a "text-to-speech" model,
# a "speech-to-text" model, a "text-to-image" model, a "image-to-text" model,
# etc.


@dataclass(frozen=True)
class ModelQualityTierConfig(Configuration):
    """Configuration for model quality tiers by platform.

    Maps quality tiers (best, balanced, fastest) to specific models for each platform.
    """

    BEDROCK_MODELS: dict[str, str] = field(
        default_factory=lambda: {
            "best": "claude-3-5-sonnet",
            "balanced": "claude-3-5-sonnet",
            "fastest": "claude-3-5-haiku",
        },
    )

    OPENAI_MODELS: dict[str, str] = field(
        default_factory=lambda: {
            "best": "o3-mini-high",
            "balanced": "gpt-4o",
            "fastest": "gpt-4o-mini",
        },
    )

    ANTHROPIC_MODELS: dict[str, str] = field(
        default_factory=lambda: {
            "best": "claude-3-5-sonnet",
            "balanced": "claude-3-5-sonnet",
            "fastest": "claude-3-5-haiku",
        },
    )

    # Add more platforms as needed

    def get_model_name(self, platform: str, tier: str) -> str | None:
        """Get the model name for a specific platform and quality tier.

        Args:
            platform: The platform name (e.g., "bedrock", "openai")
            tier: The quality tier (e.g., "best", "balanced", "fastest")

        Returns:
            The model name or None if not found
        """
        platform = platform.upper()
        config_key = f"{platform}_MODELS"

        if hasattr(self, config_key):
            models = getattr(self, config_key)
            return models.get(tier)

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
    or quality tier is requested.
    """

    PLATFORM_DEFAULTS: dict[str, str] = field(
        default_factory=lambda: {
            "bedrock": "claude-3-5-sonnet",
            "openai": "gpt-4o",
            "anthropic": "claude-3-5-sonnet",
        },
    )

    def get_default_model(self, platform: str) -> str | None:
        """Get the default model for a specific platform.

        Args:
            platform: The platform name (e.g., "bedrock", "openai")

        Returns:
            The default model name or None if not defined
        """
        return self.PLATFORM_DEFAULTS.get(platform.lower())


@dataclass
class DefaultModelSelector(ModelSelector):
    """Default implementation of model selection logic.

    This selector provides a platform-specific strategy for selecting models based on:
    1. Platform-specific default models for quality tiers
    2. Fallback chains when requested models are unavailable

    The selector uses Configuration classes to define mappings and defaults.
    """

    quality_tier_config: ModelQualityTierConfig = field(
        default_factory=ModelQualityTierConfig,
    )
    fallback_config: ModelFallbackConfig = field(
        default_factory=ModelFallbackConfig,
    )
    platform_default_config: PlatformDefaultModelConfig = field(
        default_factory=PlatformDefaultModelConfig,
    )
    default_quality_tier: Literal["best", "balanced", "fastest"] = field(
        default="balanced",
    )

    def _find_model_by_name(self, model_name: str) -> Model | None:
        """Find a model by name from supported providers.

        Args:
            model_name: The name of the model to find

        Returns:
            The Model instance or None if not found
        """
        for provider in [ModelProviders.ANTHROPIC, ModelProviders.OPENAI]:
            for model in provider.supported_models:
                if model.name == model_name:
                    return model
        return None

    def _get_model_with_fallbacks(self, model_name: str) -> Model | None:
        """Get a model with fallbacks if the primary model is not found.

        Args:
            model_name: The name of the primary model to find

        Returns:
            The Model instance or None if no suitable model found
        """
        # Try the primary model first
        model = self._find_model_by_name(model_name)
        if model:
            return model

        # Try fallbacks in order
        for fallback_name in self.fallback_config.get_fallbacks(model_name):
            fallback_model = self._find_model_by_name(fallback_name)
            if fallback_model:
                return fallback_model

        return None

    def select_model(self, selection: str | None = None) -> Model:
        """Select a model for the agent architecture.

        This implementation follows these steps:
        1. Check if a selection parameter is provided (model name or quality tier)
        2. If a model name is provided, try to find it in the supported models list
        3. If a quality tier is specified, use the platform-specific model for that tier
        4. Fall back to the platform's default model
        5. Apply fallback chains when models are unavailable

        Args:
            selection: Optional selection criteria, which could be a model name or
                quality tier. If not provided, the kernel's platform default model
                will be used.

        Returns:
            The selected Model instance

        Raises:
            ValueError: If no suitable model can be selected
        """
        # Get platform information from kernel
        platform_name = self.kernel.platform.name
        if not platform_name:
            raise ValueError("Platform name not specified in kernel configuration")

        # First, check if selection parameter is provided
        if selection:
            # Try to interpret selection as a direct model name first
            model = self._get_model_with_fallbacks(selection)
            if model:
                return model

            # If not a model name, check if it's a quality tier
            if selection in ["best", "balanced", "fastest"]:
                model_name = self.quality_tier_config.get_model_name(
                    platform_name,
                    selection,
                )
                if model_name:
                    model = self._get_model_with_fallbacks(model_name)
                    if model:
                        return model

            # If we get here, the selection couldn't be resolved
            raise ValueError(
                f"Could not resolve selection '{selection}' to a valid model",
            )

        # If no selection is provided, use the platform's default model
        default_model_name = self.platform_default_config.get_default_model(
            platform_name,
        )
        if default_model_name:
            model = self._get_model_with_fallbacks(default_model_name)
            if model:
                return model

        # If we still don't have a model, check if the platform has a supported
        # model list and use the first one
        if (
            hasattr(self.kernel.platform.configs, "supported_models")
            and self.kernel.platform.configs.supported_models
        ):
            return self.kernel.platform.configs.supported_models[0]

        # If we get here, we couldn't find a suitable model
        raise ValueError(
            f"Could not find suitable model for platform '{platform_name}'",
        )
