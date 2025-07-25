from dataclasses import dataclass, field, fields
from typing import Literal

from agent_platform.core.platforms.base import PlatformParameters
from agent_platform.core.utils import SecretString


@dataclass(frozen=True, kw_only=True)
class ReductoPlatformParameters(PlatformParameters):
    """Parameters for the Reducto platform.

    This class encapsulates all configuration parameters for Reducto client
    initialization.
    """

    kind: Literal["reducto"] = field(
        default="reducto",
        metadata={"description": "The kind of platform parameters."},
        init=False,
    )
    """The kind of platform parameters."""

    reducto_api_url: str = field(
        default="https://backend.sema4ai.dev/reducto",
        metadata={
            "description": "The Reducto API URL.",
        },
    )
    """The Reducto API URL."""

    reducto_api_key: SecretString | None = field(
        default=None,
        metadata={
            "description": "The Reducto API key. If not provided, it will be "
            "attempted to be inferred from the environment.",
        },
    )
    """The Reducto API key. If not provided, it will be attempted to be inferred
    from the environment."""

    delegate_kind: str | None = field(
        default=None,
        metadata={
            "description": "The kind of the delegate platform client.",
        },
    )
    """The kind of the delegate platform client."""

    delegate_api_key: SecretString | None = field(
        default=None,
        metadata={
            "description": "The API key for the delegate platform client. If not "
            "provided, it will be attempted to be inferred from the environment.",
        },
    )
    """The API key for the delegate platform client."""

    def __post_init__(self):
        from os import getenv

        # Handle case where reducto_api_key is passed as a string
        if self.reducto_api_key and not isinstance(self.reducto_api_key, SecretString):
            object.__setattr__(
                self,
                "reducto_api_key",
                SecretString(str(self.reducto_api_key)),
            )
        # Handle case where reducto_api_key is not provided
        elif not self.reducto_api_key:
            reducto_api_key = getenv("REDUCTO_API_KEY")
            if reducto_api_key:
                object.__setattr__(
                    self,
                    "reducto_api_key",
                    SecretString(reducto_api_key),
                )
            else:
                raise ValueError("REDUCTO_API_KEY environment variable is required")

        if self.delegate_api_key and not isinstance(self.delegate_api_key, SecretString):
            object.__setattr__(
                self,
                "delegate_api_key",
                SecretString(str(self.delegate_api_key)),
            )

    def model_dump(
        self,
        *,
        exclude_none: bool = True,
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
        api_key_value = None
        if self.reducto_api_key:
            if isinstance(self.reducto_api_key, SecretString):
                api_key_value = self.reducto_api_key.get_secret_value()
            else:
                api_key_value = str(self.reducto_api_key)

        extra = {
            "reducto_api_key": api_key_value,
        }

        if self.delegate_kind:
            extra["delegate_kind"] = self.delegate_kind
        if self.delegate_api_key:
            if isinstance(self.delegate_api_key, SecretString):
                extra["delegate_api_key"] = self.delegate_api_key.get_secret_value()
            else:
                extra["delegate_api_key"] = str(self.delegate_api_key)

        return super().model_dump(exclude_none=exclude_none, extra=extra)

    def model_copy(self, *, update: dict | None = None) -> "ReductoPlatformParameters":
        """Create a new instance of the model with the same values as
        the current instance.

        Args:
            update: A dictionary of values to update in the new instance.

        Returns:
            A new instance of ReductoParameters with updated values.
        """
        # Start with current direct parameters
        current_params = {f.name: getattr(self, f.name) for f in fields(self) if f.init}

        if not update:
            current_params = {k: v for k, v in current_params.items() if v is not None}
            return ReductoPlatformParameters(**current_params)

        # Merge all parameters
        final_params = {**current_params, **update}
        final_params = {k: v for k, v in final_params.items() if v is not None}
        return ReductoPlatformParameters(**final_params)

    @classmethod
    def model_validate(cls, obj: dict) -> "ReductoPlatformParameters":
        """Validate and convert a dictionary to an ReductoPlatformParameters instance.

        Args:
            obj: A dictionary of parameters.

        Returns:
            An ReductoParameters instance.
        """
        obj = dict(obj)  # Create a copy to avoid modifying the original

        # Convert datetime strings back to datetime objects
        cls._convert_datetime_fields(obj)

        # Directly pass the dictionary to the constructor.
        # The constructor and __post_init__ will handle extra parameters.
        return cls(**obj)


PlatformParameters.register_platform_parameters("reducto", ReductoPlatformParameters)
