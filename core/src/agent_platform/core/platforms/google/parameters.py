from dataclasses import dataclass, field, fields
from typing import Literal

from agent_platform.core.platforms.base import PlatformParameters
from agent_platform.core.utils import SecretString


@dataclass(frozen=True, kw_only=True)
class GooglePlatformParameters(PlatformParameters):
    """Parameters for the Google platform.

    This class encapsulates all configuration parameters for Google client
    initialization.
    """

    kind: Literal["google"] = field(
        default="google",
        metadata={"description": "The kind of platform parameters."},
        init=False,
    )
    """The kind of platform parameters."""

    google_api_key: SecretString | None = field(
        default=None,
        metadata={
            "description": "The Google API key. If not provided, it will be "
            "attempted to be inferred from the environment.",
        },
    )
    """The Google API key. If not provided, it will be attempted to be inferred
    from the environment."""

    def __post_init__(self):
        from os import getenv

        super().__post_init__()

        # Handle case where google_api_key is passed as a string
        if self.google_api_key and not isinstance(self.google_api_key, SecretString):
            object.__setattr__(
                self,
                "google_api_key",
                SecretString(str(self.google_api_key)),
            )
        # Handle case where google_api_key is not provided
        elif not self.google_api_key:
            google_api_key = getenv("GOOGLE_API_KEY")
            if google_api_key:
                object.__setattr__(
                    self,
                    "google_api_key",
                    SecretString(google_api_key),
                )
            else:
                raise ValueError("GOOGLE_API_KEY environment variable is required")

    def model_dump(
        self,
        *,
        exclude_none: bool = True,
    ) -> dict:
        """Convert parameters to a dictionary for client initialization.

        Args:
            exclude_none: Whether to exclude fields with value ``None``.
                Defaults to True.
        """
        api_key_value = None
        if self.google_api_key:
            api_key_value = self.google_api_key.get_secret_value()

        extra = {
            "google_api_key": api_key_value,
        }

        return super().model_dump(exclude_none=exclude_none, extra=extra)

    def model_copy(self, *, update: dict | None = None) -> "GooglePlatformParameters":
        """Create a new instance of the model with the same values as
        the current instance.

        Args:
            update: A dictionary of values to update in the new instance.

        Returns:
            A new instance of GooglePlatformParameters with updated values.
        """
        # Start with current direct parameters
        current_params = {f.name: getattr(self, f.name) for f in fields(self) if f.init}

        if not update:
            current_params = {k: v for k, v in current_params.items() if v is not None}
            return GooglePlatformParameters(**current_params)

        # Merge all parameters
        final_params = {**current_params, **update}
        final_params = {k: v for k, v in final_params.items() if v is not None}
        return GooglePlatformParameters(**final_params)

    @classmethod
    def model_validate(cls, obj: dict) -> "GooglePlatformParameters":
        """Validate and convert a dictionary to an GooglePlatformParameters instance.

        Args:
            obj: A dictionary of parameters.

        Returns:
            An GooglePlatformParameters instance.
        """
        obj = dict(obj)  # Create a copy to avoid modifying the original

        # Convert datetime strings back to datetime objects
        cls._convert_datetime_fields(obj)

        # Directly pass the dictionary to the constructor.
        # The constructor and __post_init__ will handle extra parameters.
        return cls(**obj)


PlatformParameters.register_platform_parameters("google", GooglePlatformParameters)
