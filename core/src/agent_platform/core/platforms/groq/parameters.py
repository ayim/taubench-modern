from dataclasses import dataclass, field, fields
from typing import Literal

from agent_platform.core.platforms.base import PlatformParameters
from agent_platform.core.utils import SecretString


@dataclass(frozen=True, kw_only=True)
class GroqPlatformParameters(PlatformParameters):
    """Parameters for the Groq platform.

    This class encapsulates all configuration parameters for Groq client
    initialization.
    """

    kind: Literal["groq"] = field(
        default="groq",
        metadata={"description": "The kind of platform parameters."},
        init=False,
    )
    """The kind of platform parameters."""

    groq_api_key: SecretString | None = field(
        default=None,
        metadata={
            "description": "The Groq API key. If not provided, it will be "
            "attempted to be inferred from the environment.",
        },
    )
    """The Groq API key. If not provided, it will be attempted to be inferred
    from the environment."""

    def __post_init__(self):
        from os import getenv

        # Handle case where groq_api_key is passed as a string
        if self.groq_api_key and not isinstance(self.groq_api_key, SecretString):
            object.__setattr__(
                self,
                "groq_api_key",
                SecretString(str(self.groq_api_key)),
            )
        # Handle case where groq_api_key is not provided
        elif not self.groq_api_key:
            key_from_env = getenv("GROQ_API_KEY")
            if key_from_env:
                object.__setattr__(
                    self,
                    "groq_api_key",
                    SecretString(key_from_env),
                )
            else:
                raise ValueError("GROQ_API_KEY environment variable is required")

    def api_key(self) -> str | None:
        if self.groq_api_key:
            if isinstance(self.groq_api_key, SecretString):
                return self.groq_api_key.get_secret_value()
            else:
                return str(self.groq_api_key)
        return None

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
            "groq_api_key": self.api_key(),
        }

        if exclude_none:
            result = {k: v for k, v in result.items() if v is not None}

        return result

    def model_copy(self, *, update: dict | None = None) -> "GroqPlatformParameters":
        """Create a new instance of the model with the same values as
        the current instance.

        Args:
            update: A dictionary of values to update in the new instance.

        Returns:
            A new instance of GroqParameters with updated values.
        """
        # Start with current direct parameters
        current_params = {f.name: getattr(self, f.name) for f in fields(self) if f.init}

        if not update:
            current_params = {k: v for k, v in current_params.items() if v is not None}
            return GroqPlatformParameters(**current_params)

        # Merge all parameters
        final_params = {**current_params, **update}
        final_params = {k: v for k, v in final_params.items() if v is not None}
        return GroqPlatformParameters(**final_params)

    @classmethod
    def model_validate(cls, obj: dict) -> "GroqPlatformParameters":
        """Validate and convert a dictionary to an GroqPlatformParameters instance.

        Args:
            obj: A dictionary of parameters.

        Returns:
            An GroqPlatformParameters instance.
        """

        # Directly pass the dictionary to the constructor.
        # The constructor and __post_init__ will handle extra parameters.
        return cls(**obj)


PlatformParameters.register_platform_parameters("groq", GroqPlatformParameters)
