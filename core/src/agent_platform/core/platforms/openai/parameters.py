from dataclasses import MISSING, dataclass, field, fields
from typing import Any, Literal

from agent_platform.core.platforms.base import PlatformParameters


@dataclass(frozen=True, kw_only=True)
class OpenAIPlatformParameters(PlatformParameters):
    """Parameters for the OpenAI platform.

    This class encapsulates all configuration parameters for OpenAI client
    initialization. It supports both direct client parameters and
    advanced configuration via the botocore Config object.

    Direct Parameters:
        api_key: The OpenAI API key.
        organization_id: The OpenAI organization ID.
        base_url: The OpenAI API base URL.
        timeout: The timeout in seconds for API calls.
        max_retries: The maximum number of retries for API calls.
        retry_delay: The delay in seconds between retries.
        additional_parameters: Additional parameters for OpenAI API calls.

    Examples:
        Basic usage with region:
        ```python
        params = OpenAIPlatformParameters(api_key='YOUR_API_KEY')
        ```

        Using custom endpoint and credentials:
        ```python
        params = OpenAIPlatformParameters(
            base_url='https://api.openai.com/v1',
            api_key='YOUR_API_KEY',
            organization_id='YOUR_ORGANIZATION_ID'
        )
        ```

        Advanced configuration with retries and timeouts:
        ```python
        params = OpenAIPlatformParameters(
            base_url='https://api.openai.com/v1',
            api_key='YOUR_API_KEY',
            organization_id='YOUR_ORGANIZATION_ID',
            timeout=60,
            max_retries=3,
            retry_delay=1.0,
            additional_parameters={'proxy': 'http://your.proxy.com:8080'}
        )
        ```
    """

    kind: Literal["openai"] = field(
        default="openai",
        metadata={"description": "The kind of platform parameters."},
        init=False,
    )
    """The kind of platform parameters."""

    api_key: str = field(
        metadata={"description": "OpenAI API key"},
    )
    """OpenAI API key"""

    organization_id: str | None = field(
        default=None,
        metadata={"description": "OpenAI organization ID"},
    )
    """OpenAI organization ID"""

    base_url: str = field(
        default="https://api.openai.com/v1",
        metadata={"description": "OpenAI API base URL"},
    )
    """OpenAI API base URL"""

    timeout: float = field(
        default=30.0,
        metadata={"description": "Timeout in seconds for API calls"},
    )
    """Timeout in seconds for API calls"""

    max_retries: int = field(
        default=3,
        metadata={"description": "Maximum number of retries for API calls"},
    )
    """Maximum number of retries for API calls"""

    retry_delay: float = field(
        default=1.0,
        metadata={"description": "Delay in seconds between retries"},
    )
    """Delay in seconds between retries"""

    additional_parameters: dict[str, Any] = field(
        default_factory=dict,
        metadata={"description": "Additional parameters for OpenAI API calls"},
    )
    """Additional parameters for OpenAI API calls"""

    _extra_config_params: dict | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        """Process any extra kwargs as Config parameters after dataclass
        initialization."""
        # Get all dataclass fields that are meant for initialization
        all_fields = {f.name for f in fields(self) if f.init}

        # Get any parameters that aren't part of our declared fields
        extra_params = {}
        to_delete = []
        for k, v in vars(self).items():
            if k not in all_fields and not k.startswith("_"):
                extra_params[k] = v
                to_delete.append(k)

        # Pop kind from extra_params if it exists
        extra_params.pop("kind", None)

        # Delete the extra attributes after iteration
        # (Can't do this in the above loop, or you'll get a RuntimeError)
        for k in to_delete:
            object.__delattr__(self, k)

        if extra_params:
            # Store for later use in model_copy
            object.__setattr__(self, "_extra_config_params", extra_params)

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
        # Get all fields and their default values
        field_info = {
            f.name: (
                getattr(self, f.name),
                f.default,
                f.default_factory
                if hasattr(f, "default_factory") and f.default_factory is not MISSING
                else None,
            )
            for f in fields(self)
            if f.init
        }

        # Start with only api_key
        result = {"kind": self.kind, "api_key": field_info["api_key"][0]}

        # Handle exclude_none
        if exclude_none:
            result = {k: v for k, v in result.items() if v is not None}

        # Handle exclude_defaults
        if exclude_defaults:
            # For fields with default values, only include if they differ from defaults
            for name, (value, default, default_factory) in field_info.items():
                if value is not None and (
                    (default_factory is not None and value != {})
                    or (
                        default_factory is None
                        and default is not MISSING
                        and value != default
                    )
                ):
                    result[name] = value

        # Handle exclude_unset - in this case, we only include fields that were
        # explicitly set
        if exclude_unset:
            # For fields with default values, only include if they differ from
            # defaults
            for name, (value, default, default_factory) in field_info.items():
                if value is not None and (
                    (default_factory is not None and value != {})
                    or (
                        default_factory is None
                        and default is not MISSING
                        and value != default
                    )
                ):
                    result[name] = value

        return result

    def model_copy(self, *, update: dict | None = None) -> "OpenAIPlatformParameters":
        """Create a new instance of the model with the same values as
        the current instance.

        Args:
            update: A dictionary of values to update in the new instance.

        Returns:
            A new instance of OpenAIPlatformParameters with updated values.
        """
        # Start with current direct parameters
        current_params = {f.name: getattr(self, f.name) for f in fields(self) if f.init}

        # Add stored extra config params if they exist
        if self._extra_config_params:
            current_params.update(self._extra_config_params)

        if not update:
            current_params = {k: v for k, v in current_params.items() if v is not None}
            return OpenAIPlatformParameters(**current_params)

        # Split updates into direct params and config params
        direct_param_names = {f.name for f in fields(self) if f.init}
        update_params = {}
        config_updates = {}

        for k, v in update.items():
            if k in direct_param_names:
                update_params[k] = v
            else:
                config_updates[k] = v

        # Merge all parameters
        final_params = {**current_params, **update_params, **config_updates}
        final_params = {k: v for k, v in final_params.items() if v is not None}
        return OpenAIPlatformParameters(**final_params)

    @classmethod
    def model_validate(cls, obj: dict) -> "OpenAIPlatformParameters":
        """Create a platform parameters from a dictionary.

        Args:
            obj: The dictionary to create the platform parameters from.

        Returns:
            The platform parameters.

        Raises:
            ValueError: If any field has an invalid type.
        """
        return cls(**obj)


PlatformParameters.register_platform_parameters("openai", OpenAIPlatformParameters)
