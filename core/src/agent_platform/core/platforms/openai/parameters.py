from dataclasses import dataclass, field, fields
from typing import Literal

from agent_platform.core.platforms.base import PlatformParameters
from agent_platform.core.utils import SecretString


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

    openai_api_key: SecretString | None = field(
        default=None,
        metadata={
            "description": "The OpenAI API key. If not provided, it will be "
            "attempted to be inferred from the environment.",
        },
    )
    """The OpenAI API key. If not provided, it will be attempted to be inferred
    from the environment."""

    # TODO: add other parameters in post_init
    def __post_init__(self):
        from os import getenv

        super().__post_init__()

        # Default the models allowlist to "{ "openai": ["gpt-4-1"] }"
        # to match prior semantics
        if self.models is None or self.models == {}:
            object.__setattr__(
                self,
                "models",
                {"openai": ["gpt-4-1"]},
            )

        # Handle case where openai_api_key is passed as a string or dict
        if self.openai_api_key and not isinstance(self.openai_api_key, SecretString):
            object.__setattr__(
                self,
                "openai_api_key",
                SecretString.from_value(self.openai_api_key),
            )
        # Handle case where openai_api_key is not provided
        elif not self.openai_api_key:
            openai_api_key = getenv("OPENAI_API_KEY")
            if openai_api_key:
                object.__setattr__(
                    self,
                    "openai_api_key",
                    SecretString(openai_api_key),
                )
            else:
                raise ValueError("OPENAI_API_KEY environment variable is required")

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
        if self.openai_api_key:
            if isinstance(self.openai_api_key, SecretString):
                api_key_value = self.openai_api_key.get_secret_value()
            else:
                api_key_value = str(self.openai_api_key)

        extra = {
            "openai_api_key": api_key_value,
        }

        return super().model_dump(exclude_none=exclude_none, extra=extra)

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
        obj = dict(obj)  # Create a copy to avoid modifying the original

        # Convert datetime strings back to datetime objects
        cls._convert_datetime_fields(obj)

        # Directly pass the dictionary to the constructor.
        # The constructor and __post_init__ will handle extra parameters.
        return cls(**obj)


PlatformParameters.register_platform_parameters("openai", OpenAIPlatformParameters)
