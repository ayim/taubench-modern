"""Unit tests for the Google platform parameters."""

import json
import os
from unittest.mock import patch

import pytest

from agent_platform.core.platforms.configs import PlatformModelConfigs
from agent_platform.core.platforms.google.parameters import GooglePlatformParameters
from agent_platform.core.utils import SecretString

SERVICE_ACCOUNT_JSON = SecretString(
    (
        '{"type":"service_account","project_id":"demo","private_key_id":"key",'
        '"private_key":"-----BEGIN PRIVATE KEY-----\\nABC\\n-----END PRIVATE KEY-----\\n",'
        '"client_email":"demo@example.com","client_id":"1234567890",'
        '"token_uri":"https://oauth2.googleapis.com/token"}'
    ),
)


class TestGooglePlatformParameters:
    """Tests for the Google platform parameters."""

    def test_init_with_api_key(self) -> None:
        """Test initialization with an API key."""
        api_key = SecretString("test-api-key")
        params = GooglePlatformParameters(google_api_key=api_key)
        assert params.google_api_key is not None
        assert params.google_api_key.get_secret_value() == "test-api-key"

    def test_init_with_missing_api_key(self) -> None:
        """Test initialization without an API key when no env var is set."""
        # Mock environment to ensure GOOGLE_API_KEY is not set
        with patch.dict(os.environ, {"GOOGLE_API_KEY": ""}, clear=True):
            with pytest.raises(
                ValueError,
                match="GOOGLE_API_KEY environment variable is required",
            ):
                GooglePlatformParameters()

    def test_model_dump(self) -> None:
        """Test serialization to dict."""
        api_key = SecretString("test-api-key")
        params = GooglePlatformParameters(google_api_key=api_key)
        dumped = params.model_dump()
        assert "google_api_key" in dumped
        assert dumped["google_api_key"] == "test-api-key"
        assert dumped["kind"] == "google"

    def test_model_dump_exclude_none(self) -> None:
        """Test serialization excluding None values."""
        api_key = SecretString("test-api-key")
        params = GooglePlatformParameters(google_api_key=api_key)
        dumped = params.model_dump(exclude_none=True)
        assert "google_api_key" in dumped
        assert dumped["google_api_key"] == "test-api-key"

    def test_model_copy(self) -> None:
        """Test creating a copy with updates."""
        api_key = SecretString("test-api-key")
        params = GooglePlatformParameters(google_api_key=api_key)

        new_api_key = SecretString("new-api-key")
        updated = params.model_copy(update={"google_api_key": new_api_key})

        assert updated.google_api_key is not None
        assert updated.google_api_key.get_secret_value() == "new-api-key"

    def test_model_validate(self) -> None:
        """Test creating from dict."""
        data = {
            "google_api_key": "test-api-key",
        }
        params = GooglePlatformParameters.model_validate(data)
        assert params.google_api_key is not None
        assert params.google_api_key.get_secret_value() == "test-api-key"

    def test_model_validate_with_string_api_key(self) -> None:
        """Test validation with string API key."""
        # The implementation should convert string to SecretString
        data = {
            "google_api_key": "test-api-key",
        }
        params = GooglePlatformParameters.model_validate(data)
        assert isinstance(params.google_api_key, SecretString)
        assert params.google_api_key.get_secret_value() == "test-api-key"

    def test_vertex_ai_requires_project_and_location(self) -> None:
        """Vertex AI config mandates project and location values."""
        api_key = SecretString("test-api-key")
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(
                ValueError,
                match="google_cloud_project_id is required",
            ):
                GooglePlatformParameters(
                    google_api_key=api_key,
                    google_use_vertex_ai=True,
                )

    def test_vertex_ai_uses_env_defaults(self) -> None:
        """Vertex AI config can pull defaults from environment variables."""
        api_key = SecretString("test-api-key")
        with patch.dict(
            os.environ,
            {
                "GOOGLE_CLOUD_PROJECT_ID": "project-123",
                "GOOGLE_CLOUD_LOCATION": "us-central1",
                "GOOGLE_VERTEX_SERVICE_ACCOUNT_JSON": SERVICE_ACCOUNT_JSON.get_secret_value(),
            },
            clear=True,
        ):
            params = GooglePlatformParameters(
                google_api_key=api_key,
                google_use_vertex_ai=True,
            )
            assert params.google_cloud_project_id == "project-123"
            assert params.google_cloud_location == "us-central1"
            assert params.google_vertex_service_account_json is not None

    def test_model_dump_includes_vertex_fields(self) -> None:
        """Serialized output includes Vertex AI configuration values."""
        api_key = SecretString("test-api-key")
        params = GooglePlatformParameters(
            google_api_key=api_key,
            google_use_vertex_ai=True,
            google_cloud_project_id="project-123",
            google_cloud_location="us-central1",
            google_vertex_service_account_json=SERVICE_ACCOUNT_JSON,
        )
        dumped = params.model_dump()
        assert dumped["google_use_vertex_ai"] is True
        assert dumped["google_cloud_project_id"] == "project-123"
        assert dumped["google_cloud_location"] == "us-central1"
        assert dumped["google_vertex_service_account_json"] == SERVICE_ACCOUNT_JSON.get_secret_value()

    def test_vertex_ai_allows_missing_service_account_json_for_legacy_configs(self) -> None:
        """Allow pre-existing configs without service account JSON."""
        with patch.dict(os.environ, {}, clear=True):
            params = GooglePlatformParameters(
                google_use_vertex_ai=True,
                google_cloud_project_id="project-123",
                google_cloud_location="us-central1",
            )

        assert params.google_vertex_service_account_json is None
        assert params.google_api_key is None

    def test_vertex_ai_uses_application_credentials_file(self, tmp_path) -> None:
        """Vertex AI accepts GOOGLE_APPLICATION_CREDENTIALS path."""
        api_key = SecretString("test-api-key")
        sa_path = tmp_path / "sa.json"
        sa_path.write_text(
            (
                '{"type":"service_account","project_id":"demo",'
                '"private_key":"-----BEGIN PRIVATE KEY-----\\nABC\\n-----END PRIVATE KEY-----\\n",'
                '"client_email":"demo@example.com","token_uri":"https://oauth2.googleapis.com/token"}'
            ),
        )
        with patch.dict(
            os.environ,
            {
                "GOOGLE_API_KEY": "test-api-key",
                "GOOGLE_APPLICATION_CREDENTIALS": str(sa_path),
                "GOOGLE_CLOUD_PROJECT_ID": "project-123",
                "GOOGLE_CLOUD_LOCATION": "us-central1",
            },
            clear=True,
        ):
            params = GooglePlatformParameters(
                google_use_vertex_ai=True,
                google_api_key=api_key,
            )
        assert params.google_cloud_project_id == "project-123"
        assert params.google_cloud_location == "us-central1"
        assert params.google_vertex_service_account_json is None

    def test_default_models_use_provider_specific_slug(self) -> None:
        """Default model should map to provider-specific identifier."""
        params = GooglePlatformParameters(google_api_key=SecretString("test"))
        platform_configs = PlatformModelConfigs()
        default_generic = platform_configs.platforms_to_default_model["google"]
        expected_slug = platform_configs.models_to_platform_specific_model_ids[default_generic]
        assert params.models == {"google": [expected_slug]}

    def test_google_parameters_vertex_service_account_accepts_dict(self) -> None:
        """Service account JSON should accept raw dictionaries."""
        service_account_dict = {"type": "service_account", "project_id": "test-project"}

        params = GooglePlatformParameters(
            google_use_vertex_ai=True,
            google_cloud_project_id="test-project",
            google_cloud_location="us-central1",
            # Passing a dict reproduces the issue we're testing for.
            google_vertex_service_account_json=service_account_dict,  # type: ignore[arg-type]
        )

        assert isinstance(params.google_vertex_service_account_json, SecretString)
        secret_value = params.google_vertex_service_account_json.get_secret_value()
        assert json.loads(secret_value) == service_account_dict

    def test_init_uses_api_key_from_environment(self) -> None:
        """API keys should be derived from the GOOGLE_API_KEY env var when missing."""
        with patch.dict(
            os.environ,
            {
                "GOOGLE_API_KEY": "env-key",
            },
            clear=True,
        ):
            params = GooglePlatformParameters()

        assert params.google_api_key is not None
        assert params.google_api_key.get_secret_value() == "env-key"
