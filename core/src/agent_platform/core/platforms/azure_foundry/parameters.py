from dataclasses import dataclass, field, fields
from typing import Literal

from agent_platform.core.platforms.base import PlatformParameters


@dataclass(frozen=True, kw_only=True)
class AzureFoundryPlatformParameters(PlatformParameters):
    """Parameters for the Azure Foundry platform.

    This class encapsulates all configuration parameters for Azure AI Foundry
    client initialization, which provides access to Anthropic Claude models
    through Microsoft Azure.

    Parameters:
        endpoint_url: The full Azure AI Foundry endpoint URL
            (e.g. ``https://my-resource.services.ai.azure.com/v1/messages``).
        api_key: The API key for Azure AI Foundry authentication.
        deployment_name: The deployment name for the model.
        model: The model identifier (e.g. ``claude-4-5-sonnet``).

    Examples:
        Basic usage:
        ```python
        params = AzureFoundryPlatformParameters(
            endpoint_url='https://my-resource.services.ai.azure.com/v1/messages',
            api_key='my-api-key',
            deployment_name='claude-4-5-sonnet',
            model='claude-4-5-sonnet',
        )
        ```
    """

    kind: Literal["azure_foundry"] = field(
        default="azure_foundry",
        metadata={"description": "The kind of platform parameters."},
        init=False,
    )
    """The kind of platform parameters."""

    endpoint_url: str | None = field(
        default=None,
        metadata={
            "description": "The full Azure AI Foundry endpoint URL.",
            "example": "https://my-resource.services.ai.azure.com/v1/messages",
        },
    )

    api_key: str | None = field(
        default=None,
        metadata={
            "description": "API key for Azure AI Foundry authentication.",
            "example": "your-api-key-here",
        },
    )

    deployment_name: str | None = field(
        default=None,
        metadata={
            "description": "The deployment name for the model in Azure AI Foundry.",
            "example": "claude-4-5-sonnet",
        },
    )

    model: str | None = field(
        default=None,
        metadata={
            "description": "The model identifier.",
            "example": "claude-4-5-sonnet",
        },
    )

    def get_base_url(self) -> str | None:
        """Return the base URL by stripping the ``/v1/messages`` suffix."""
        if not self.endpoint_url:
            return None
        url = self.endpoint_url.rstrip("/")
        if url.endswith("/v1/messages"):
            url = url[: -len("/v1/messages")]
        return url

    def __post_init__(self):
        super().__post_init__()

        # Default the models allowlist from the model field when provided
        if self.model and (self.models is None or self.models == {}):
            object.__setattr__(
                self,
                "models",
                {"anthropic": [self.model]},
            )
        elif self.models is None or self.models == {}:
            object.__setattr__(
                self,
                "models",
                {"anthropic": ["claude-4-5-sonnet"]},
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
        """
        extra = {
            "endpoint_url": self.endpoint_url,
            "api_key": self.api_key,
            "deployment_name": self.deployment_name,
            "model": self.model,
        }

        return super().model_dump(exclude_none=exclude_none, extra=extra)

    def model_copy(self, *, update: dict | None = None) -> "AzureFoundryPlatformParameters":
        """Create a new instance of the model with the same values as
        the current instance.

        Args:
            update: A dictionary of values to update in the new instance.

        Returns:
            A new instance of AzureFoundryPlatformParameters with updated values.
        """
        data = self.model_dump(exclude_none=False)
        data.update(update or {})
        data.pop("kind", None)
        return AzureFoundryPlatformParameters(**data)

    @classmethod
    def model_validate(cls, obj: dict) -> "AzureFoundryPlatformParameters":
        obj = dict(obj)  # don't mutate caller's dict

        # Backward compat: map old azure_foundry_* field names to new names
        field_renames = {
            "azure_foundry_resource_name": "endpoint_url",
            "azure_foundry_api_key": "api_key",
            "azure_foundry_deployment_name": "deployment_name",
        }
        for old_key, new_key in field_renames.items():
            if old_key in obj and new_key not in obj:
                obj[new_key] = obj.pop(old_key)
            elif old_key in obj:
                obj.pop(old_key)

        # Drop removed field
        obj.pop("azure_foundry_api_version", None)

        # Remove kind, it's force-set to "azure_foundry"
        if "kind" in obj:
            obj.pop("kind")

        # Lift any stray keys that are not dataclass fields
        top_fields = {f.name for f in fields(cls)}
        stray = {k: obj.pop(k) for k in list(obj) if k not in top_fields}

        # Convert datetime strings back to datetime objects
        cls._convert_datetime_fields(obj)

        # Add any stray fields back (they'll be ignored by dataclass)
        # but we keep this pattern for consistency with other platforms
        if stray:
            # Log or handle stray fields if needed
            pass

        return cls(**obj)


PlatformParameters.register_platform_parameters("azure_foundry", AzureFoundryPlatformParameters)
