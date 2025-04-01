from dataclasses import dataclass, field, fields
from typing import Literal

from agent_platform.core.platforms.base import PlatformParameters


@dataclass(frozen=True, kw_only=True)
class OpenAIPlatformParameters(PlatformParameters):
    """Parameters for the OpenAI platform.

    This class encapsulates all configuration parameters for OpenAI client
    initialization.
    """

    kind: Literal["openai"] = field(
        default="openai",
        metadata={"description": "The kind of platform parameters."},
        init=False,
    )
    """The kind of platform parameters."""

    openai_api_key: str = field(
        metadata={
            "description": "The OpenAI API key.",
        },
    )
    """The OpenAI API key."""

    # TODO: add other parameters in post_init

    def model_dump(
        self,
        *,
        exclude_none: bool = True,
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
    ) -> dict:
        """Convert parameters to a dictionary for client initialization.

        Args:
            exclude_none: Whether to exclude fields with value ``None``.
                Defaults to True.
            exclude_unset: Whether to exclude fields that were not explicitly set.
                Not implemented.
            exclude_defaults: Whether to exclude fields that are set to their
                default values. Not implemented.
        """
        result = {
            "kind": self.kind,
            "openai_api_key": self.openai_api_key,
        }

        if exclude_none:
            result = {k: v for k, v in result.items() if v is not None}

        return result

    def model_copy(self, *, update: dict | None = None) -> "OpenAIPlatformParameters":
        """Create a new instance of the model with the same values as
        the current instance.

        Args:
            update: A dictionary of values to update in the new instance.

        Returns:
            A new instance of OpenAIParameters with updated values.
        """
        # Start with current direct parameters
        current_params = {f.name: getattr(self, f.name) for f in fields(self) if f.init}

        if not update:
            current_params = {k: v for k, v in current_params.items() if v is not None}
            return OpenAIPlatformParameters(**current_params)

        # Merge all parameters
        final_params = {**current_params, **update}
        final_params = {k: v for k, v in final_params.items() if v is not None}
        return OpenAIPlatformParameters(**final_params)

    @classmethod
    def model_validate(cls, obj: dict) -> "OpenAIPlatformParameters":
        """Validate and convert a dictionary to an OpenAIPlatformParameters instance.

        Args:
            obj: A dictionary of parameters.

        Returns:
            An OpenAIParameters instance.
        """
        # Directly pass the dictionary to the constructor.
        # The constructor and __post_init__ will handle extra parameters.
        return cls(**obj)


PlatformParameters.register_platform_parameters("openai", OpenAIPlatformParameters)
