from dataclasses import dataclass, field
from typing import Any, Self

from agent_platform.core.errors import ErrorCode, PlatformHTTPError
from agent_platform.core.platforms.base import PlatformParameters


@dataclass(frozen=True)
class UpsertPlatformConfigPayload:
    """Payload for creating or updating a platform configuration."""

    name: str = field(
        metadata={"description": "Human-readable name for this platform configuration"},
    )
    """Human-readable name for this platform configuration."""

    kind: str = field(
        metadata={"description": "Platform kind"},
    )
    """Platform kind (e.g. openai, azure, bedrock, google, cortex, groq, anthropic)."""

    credentials: dict[str, Any] | None = field(
        default=None,
        metadata={"description": "Credentials required for authenticating against the platform"},
    )
    """Credentials required for authenticating against the platform."""

    description: str | None = field(
        default=None,
        metadata={"description": "Description of the platform configuration"},
    )
    """Description of the platform configuration."""

    models: dict[str, list[str]] | None = field(
        default=None,
        metadata={
            "description": ("Allow list of provider -> models mapping (e.g. {'openai': ['gpt-4-1', 'o3-high']})"),
        },
    )
    """Allow list of provider -> models mapping (e.g. {'openai': ['gpt-4-1', 'o3-high']})"""

    id: str | None = field(
        default=None,
        metadata={"description": "Unique identifier (server-generated)"},
    )
    """Unique identifier (server-generated)."""

    def model_dump(self) -> dict[str, Any]:
        """Convert the payload to a dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "kind": self.kind,
            "description": self.description,
            "credentials": self.credentials,
            "models": self.models,
        }

    def to_platform_parameters(self) -> PlatformParameters:
        """Convert to a PlatformParameters object."""
        # Ensure payload passes our validation rules before constructing parameters
        # (FastAPI won't call our model_validate automatically for dataclasses)
        _ = UpsertPlatformConfigPayload.model_validate(self.model_dump())

        params_dict = {
            "kind": self.kind,
            "name": self.name,
            "description": self.description,
            "models": self.models,
        }

        # Mix in credentials directly (they become fields on the PlatformParameters)
        if self.credentials:
            params_dict.update(self.credentials)

        try:
            return PlatformParameters.model_validate(params_dict)
        except ValueError as e:
            if "Invalid platform parameters kind" in str(e):
                # For an invalid 'kind' value, this is a client input error -> 400 Bad Request
                raise PlatformHTTPError(
                    error_code=ErrorCode.BAD_REQUEST,
                    message=(
                        "Invalid platform parameters kind. "
                        f"Provided: {self.kind!r}. "
                        "Must be one of: " + ", ".join(PlatformParameters._platform_parameters_registry.keys())
                    ),
                    data={"kind": self.kind},
                ) from e
            raise e

    @classmethod
    def from_platform_parameters(cls, platform_params: PlatformParameters, config_id: str | None = None) -> Self:
        """Create a payload from PlatformParameters.

        Args:
            platform_params: The core platform parameters
            config_id: Optional ID for the configuration
        """
        # Get the raw data from platform parameters
        params_dict = platform_params.model_dump()

        # Extract known PlatformParameters fields
        kind = params_dict.pop("kind", "")
        name = params_dict.pop("name", "")
        description = params_dict.pop("description", None)
        models = params_dict.pop("models", None)

        # Remove other PlatformParameters fields that aren't credentials
        params_dict.pop("alias", None)
        params_dict.pop("created_at", None)
        params_dict.pop("updated_at", None)
        params_dict.pop("platform_id", None)

        # Remaining items are credentials (platform-specific fields)
        credentials = params_dict if params_dict else None

        return cls(
            id=config_id,
            name=name,
            kind=kind,
            description=description,
            credentials=credentials,
            models=models,
        )

    @classmethod
    def model_validate(cls, data: dict[str, Any]) -> Self:
        """Validate and convert dictionary data to UpsertPlatformConfigPayload instance."""
        # Collect validation errors to return a single 422 response
        validation_errors: dict[str, str] = {}

        # Validate required fields presence first to avoid KeyError
        if "name" not in data:
            validation_errors["name"] = "is required"
        if "kind" not in data:
            validation_errors["kind"] = "is required"

        # Only perform further checks if keys are present
        name_value = data.get("name")
        if isinstance(name_value, str) and name_value.strip() == "":
            validation_errors["name"] = "must not be empty"

        models_value = data.get("models")
        if models_value is not None and isinstance(models_value, dict) and len(models_value) == 0:
            validation_errors["models"] = "must not be empty"

        credentials_value = data.get("credentials")
        if credentials_value is not None and isinstance(credentials_value, dict):
            empty_credential_keys = [
                key for key, value in credentials_value.items() if isinstance(value, str) and value.strip() == ""
            ]
            if empty_credential_keys:
                validation_errors["credentials"] = f"empty values for: {', '.join(sorted(empty_credential_keys))}"

        if validation_errors:
            raise PlatformHTTPError(
                error_code=ErrorCode.UNPROCESSABLE_ENTITY,
                message="Request validation failed.",
                data=validation_errors,
            )

        return cls(
            id=data.get("id"),
            name=data["name"],
            kind=data["kind"],
            description=data.get("description"),
            credentials=data.get("credentials"),
            models=data.get("models"),
        )
