"""OpenAI platform parameters."""

from dataclasses import MISSING, dataclass, field, fields
from typing import Any, Union

from agent_platform.core.platforms.base import PlatformParameters


@dataclass(frozen=True)
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
        result = {"api_key": field_info["api_key"][0]}

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

        if not update:
            # Always include api_key
            filtered_params = {
                k: v
                for k, v in current_params.items()
                if v is not None or k == "api_key"
            }
            return OpenAIPlatformParameters(**filtered_params)

        # Merge all parameters
        final_params = {**current_params, **update}
        # Always include api_key
        final_params = {
            k: v for k, v in final_params.items() if v is not None or k == "api_key"
        }
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
        # Remove kind from obj as it's not a field
        obj = obj.copy()
        obj.pop("kind", None)

        # Validate field types
        field_types = {f.name: f.type for f in fields(cls) if f.init}
        for field_name, value in obj.items():
            if field_name not in field_types or value is None:
                continue
            field_type = field_types[field_name]
            # Handle string type hints
            if isinstance(field_type, str):
                continue
            # Handle union types
            if hasattr(field_type, "__origin__") and field_type.__origin__ is Union:
                valid_types = [t for t in field_type.__args__ if not isinstance(t, str)]
                if not any(isinstance(value, t) for t in valid_types):
                    raise ValueError(
                        f"Field {field_name} must be one of types {valid_types}, "
                        f"got {type(value)}",
                    )
            # Handle simple types
            elif not isinstance(value, field_type):
                raise ValueError(
                    f"Field {field_name} must be of type {field_type}, "
                    f"got {type(value)}",
                )

        return cls(**obj)


PlatformParameters.register_platform_parameters("openai", OpenAIPlatformParameters)
