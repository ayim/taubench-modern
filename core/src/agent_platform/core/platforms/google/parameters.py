import os
from collections.abc import Callable
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any, Literal

from agent_platform.core.platforms.base import PlatformParameters
from agent_platform.core.utils import SecretString

GOOGLE_PROVIDER = "google"
_DEFAULT_SA_PATH = (
    Path(__file__).parents[5]
    / "tests"
    / "platforms"
    / "google"
    / "google_vertex_service_account.json"
)
_DEFAULT_PROJECT_ID = "high-bedrock-479317-g9"
_DEFAULT_LOCATION = "global"


def extract_vertex_platform_kwargs_from_env(models: list[str]) -> dict[str, Any]:
    """Helper function to extract vertex specific kwargs from environment variables."""

    # Use Vertex AI for Gemini 3
    service_account_json = os.environ.get(
        "GOOGLE_VERTEX_SERVICE_ACCOUNT_JSON",
        _DEFAULT_SA_PATH.read_text(encoding="utf-8"),
    )
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT_ID", _DEFAULT_PROJECT_ID)
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", _DEFAULT_LOCATION)

    vertex_kwargs: dict[str, Any] = {
        "google_use_vertex_ai": True,
        "google_cloud_project_id": project_id,
        "google_cloud_location": location,
        "google_vertex_service_account_json": service_account_json,
        "models": {
            "google": models,
        },
    }

    return vertex_kwargs


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

    google_cloud_project_id: str | None = field(
        default=None,
        metadata={
            "description": "The Google Cloud project ID used for Vertex AI requests.",
        },
    )
    """The Google Cloud project ID used for Vertex AI requests."""

    google_cloud_location: str | None = field(
        default=None,
        metadata={
            "description": "The Google Cloud region/location for Vertex AI requests.",
        },
    )
    """The Google Cloud region/location for Vertex AI requests."""

    google_use_vertex_ai: bool | None = field(
        default=None,
        metadata={
            "description": "Whether to route requests through Vertex AI.",
        },
    )
    """Whether to route requests through Vertex AI."""

    google_vertex_service_account_json: SecretString | None = field(
        default=None,
        metadata={
            "description": "Service account JSON used to authenticate with Vertex AI.",
        },
    )
    """Service account JSON used to authenticate with Vertex AI."""

    def __post_init__(self):
        from os import getenv

        super().__post_init__()

        # Default the models allowlist to "{ "google": ["gemini-3-pro-preview"] }"
        if self.models is None or self.models == {}:
            object.__setattr__(
                self,
                "models",
                {"google": ["gemini-3-pro-preview"]},
            )

        self._configure_ai_studio_settings_api_key(getenv)
        self._configure_vertex_settings(getenv)

    def _configure_vertex_settings(self, getenv: Callable[[str], str | None]) -> None:
        if not self.google_use_vertex_ai:
            return

        # Set Project ID
        project_id = self.google_cloud_project_id or getenv("GOOGLE_CLOUD_PROJECT_ID")
        if not project_id:
            raise ValueError(
                "google_cloud_project_id is required when google_use_vertex_ai is enabled",
            )
        object.__setattr__(self, "google_cloud_project_id", project_id)

        # Set Location
        location = self.google_cloud_location or getenv("GOOGLE_CLOUD_LOCATION")
        if not location:
            raise ValueError(
                "google_cloud_location is required when google_use_vertex_ai is enabled",
            )
        object.__setattr__(self, "google_cloud_location", location)

        # Set Vertex Service Account JSON Credential
        vertex_credentials = self.google_vertex_service_account_json or getenv(
            "GOOGLE_VERTEX_SERVICE_ACCOUNT_JSON"
        )

        # Legacy configurations might rely on credentials set elsewhere. We defer
        # validation to the Google client so existing configs can still load.
        if not vertex_credentials:
            return

        if not isinstance(vertex_credentials, SecretString):
            vertex_credentials = SecretString(vertex_credentials)
        object.__setattr__(
            self,
            "google_vertex_service_account_json",
            vertex_credentials,
        )

    def _configure_ai_studio_settings_api_key(self, getenv: Callable[[str], str | None]) -> None:
        """Configure the Google API key for AI Studio settings."""

        api_key: SecretString | str | dict | None = self.google_api_key

        if isinstance(api_key, str):
            api_key = api_key.strip() or None

        if not api_key:
            env_value = getenv("GOOGLE_API_KEY")
            api_key = env_value.strip() if isinstance(env_value, str) else env_value
            if isinstance(api_key, str) and not api_key:
                api_key = None

        if api_key and not isinstance(api_key, SecretString):
            api_key = SecretString.from_value(api_key)

        object.__setattr__(self, "google_api_key", api_key)

        if not self.google_use_vertex_ai and not api_key:
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
        vertex_credentials = None
        if self.google_vertex_service_account_json:
            vertex_credentials = self.google_vertex_service_account_json.get_secret_value()

        extra = {
            "google_api_key": api_key_value,
            "google_cloud_project_id": self.google_cloud_project_id,
            "google_cloud_location": self.google_cloud_location,
            "google_use_vertex_ai": self.google_use_vertex_ai,
            "google_vertex_service_account_json": vertex_credentials,
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
