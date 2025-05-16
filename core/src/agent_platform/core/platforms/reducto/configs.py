from dataclasses import dataclass, field

from agent_platform.core.configurations import Configuration
from agent_platform.core.configurations.base import FieldMetadata
from agent_platform.core.platforms.base import PlatformConfigs, PlatformModelMap


@dataclass(frozen=True)
class ReductoModelMap(PlatformModelMap):
    """Reducto doesn't really have "models" per se, it has lots of options.
    We might have nice model names that map to reasonable sets of options, but
    for now we're looking at just a "default" model.
    """

    model_aliases: dict[str, str] = field(
        default_factory=lambda: {
            "reducto-standard-parse": "standard:parse",
            "reducto-standard-extract": "standard:extract",
        },
        metadata=FieldMetadata(
            description=("A mapping between our model names and Reducto model IDs."),
        ),
    )

    models_to_type: dict[str, str] = field(
        default_factory=lambda: {
            "reducto-standard-parse": "document-to-text",
            "reducto-standard-extract": "document-to-text",
        },
        metadata=FieldMetadata(
            description=("A mapping between our model names and model types."),
        ),
    )

    models_to_input_modalities: dict[str, list[str]] = field(
        default_factory=lambda: {
            "reducto-standard-parse": ["document"],
            "reducto-standard-extract": ["document"],
        },
        metadata=FieldMetadata(
            description=("A mapping between our model names and input modalities."),
        ),
    )

    models_to_output_modalities: dict[str, list[str]] = field(
        default_factory=lambda: {
            "reducto-standard-parse": ["text"],
            "reducto-standard-extract": ["text"],
        },
        metadata=FieldMetadata(
            description=("A mapping between our model names and output modalities."),
        ),
    )

    model_families: dict[str, str] = field(
        default_factory=lambda: {
            "reducto-standard-parse": "standard",
            "reducto-standard-extract": "standard",
        },
    )

    model_context_windows: dict[str, int | None] = field(
        default_factory=lambda: {
            "reducto-standard-parse": None,
            "reducto-standard-extract": None,
        },
        metadata=FieldMetadata(
            description=("The context window size for each model."),
        ),
    )


@dataclass(frozen=True)
class ReductoDefaultModel(Configuration):
    """The default model to use for the Reducto platform."""

    default_model: str = field(
        default="standard-parse",
        metadata=FieldMetadata(
            description="The default model to use for the Reducto platform.",
        ),
    )


@dataclass(frozen=True)
class ReductoPlatformConfigs(PlatformConfigs):
    """The configs for the Reducto platform."""

    default_platform_provider: dict[str, str] = field(
        default_factory=lambda: {
            "standard": "reducto",
        },
        metadata={
            "description": "The default platform provider by model type.",
        },
    )
    """The default platform provider by model type."""

    default_model_type: str = field(
        default="document-to-text",
        metadata={"description": "The default model type."},
    )
    """The default model type."""

    default_quality_tier: dict[str, str] = field(
        default_factory=lambda: {
            "document-to-text": "balanced",
        },
        metadata={
            "description": "The default quality tier by model type.",
        },
    )
    """The default quality tier by model type."""

    supported_models_by_provider: dict[str, list[str]] = field(
        # TODO: does this need model type refinement?
        # provider + type -> model
        default_factory=lambda: {
            "reducto": [
                "reducto-standard-parse",
                "reducto-standard-extract",
                "reducto-standard-classify",
            ],
        },
        metadata={"description": "The supported models by provider."},
    )
    """The supported models by provider."""
