from datetime import datetime

import pytest

from agent_platform.core.document_intelligence.integrations import (
    DocumentIntelligenceIntegration,
    IntegrationKind,
)
from agent_platform.core.utils import SecretString


class TestDocumentIntelligenceIntegration:
    """Test DocumentIntelligenceIntegration dataclass functionality."""

    def test_creation_with_string_api_key(self):
        """Test creating integration with string API key (auto-converted to SecretString)."""
        integration = DocumentIntelligenceIntegration(
            kind=IntegrationKind.REDUCTO,
            endpoint="https://api.reducto.ai/v1",
            api_key="secret-api-key-123",  # type: ignore[arg-type] # String api_key
        )

        assert integration.kind == IntegrationKind.REDUCTO
        assert integration.endpoint == "https://api.reducto.ai/v1"
        assert isinstance(integration.api_key, SecretString)
        assert integration.api_key.get_secret_value() == "secret-api-key-123"
        assert str(integration.api_key) == "**********"

    def test_creation_with_secret_string_api_key(self):
        """Test creating integration with SecretString API key (preserved)."""
        secret_key = SecretString("secret-api-key-123")
        integration = DocumentIntelligenceIntegration(
            kind=IntegrationKind.REDUCTO,
            endpoint="https://api.reducto.ai/v1",
            api_key=secret_key,
        )

        assert integration.kind == IntegrationKind.REDUCTO
        assert integration.endpoint == "https://api.reducto.ai/v1"
        assert isinstance(integration.api_key, SecretString)
        assert integration.api_key is secret_key  # Same object preserved
        assert integration.api_key.get_secret_value() == "secret-api-key-123"

    def test_creation_with_enum_member(self):
        """Test creating integration using enum member."""
        integration = DocumentIntelligenceIntegration(
            kind=IntegrationKind.REDUCTO,
            endpoint="https://api.reducto.ai/v1",
            api_key="secret-key",  # type: ignore[arg-type]
        )

        assert integration.kind == IntegrationKind.REDUCTO
        assert integration.kind == "reducto"  # Can compare with string

    def test_model_dump(self):
        """Test model_dump returns correct dictionary."""
        integration = DocumentIntelligenceIntegration(
            kind=IntegrationKind.REDUCTO,
            endpoint="https://api.reducto.ai/v1",
            api_key="secret-api-key-123",  # type: ignore[arg-type]
        )

        dump = integration.model_dump()

        # Check that all expected fields are present
        assert "kind" in dump
        assert "endpoint" in dump
        assert "api_key" in dump
        assert "updated_at" in dump

        # Check field values
        assert dump["kind"] == IntegrationKind.REDUCTO
        assert dump["endpoint"] == "https://api.reducto.ai/v1"
        assert dump["api_key"] == integration.api_key  # SecretString object
        assert dump["updated_at"] == integration.updated_at

        # Verify SecretString is preserved in dump
        assert isinstance(dump["api_key"], SecretString)
        assert dump["api_key"].get_secret_value() == "secret-api-key-123"
        assert str(dump["api_key"]) == "**********"

        # Verify updated_at types
        assert isinstance(dump["updated_at"], datetime)

    def test_model_validate_from_dict_with_string_key(self):
        """Test model_validate creates instance from dictionary with string API key."""
        data = {
            "kind": "reducto",
            "endpoint": "https://api.reducto.ai/v1",
            "api_key": "secret-api-key-123",
        }

        integration = DocumentIntelligenceIntegration.model_validate(data)

        assert integration.kind == IntegrationKind.REDUCTO
        assert integration.endpoint == "https://api.reducto.ai/v1"
        assert isinstance(integration.api_key, SecretString)
        assert integration.api_key.get_secret_value() == "secret-api-key-123"

    def test_model_validate_from_dict_with_enum_kind(self):
        """Test model_validate handles enum kind values."""
        data = {
            "kind": IntegrationKind.REDUCTO,
            "endpoint": "https://api.reducto.ai/v1",
            "api_key": "secret-api-key-123",
        }

        integration = DocumentIntelligenceIntegration.model_validate(data)

        assert integration.kind == IntegrationKind.REDUCTO
        assert integration.endpoint == "https://api.reducto.ai/v1"
        assert isinstance(integration.api_key, SecretString)

    def test_model_validate_with_secret_string_key(self):
        """Test model_validate handles SecretString API keys correctly."""
        secret_key = SecretString("secret-api-key-123")
        data = {
            "kind": "reducto",
            "endpoint": "https://api.reducto.ai/v1",
            "api_key": secret_key,
        }

        integration = DocumentIntelligenceIntegration.model_validate(data)

        assert integration.kind == IntegrationKind.REDUCTO
        assert integration.endpoint == "https://api.reducto.ai/v1"
        assert isinstance(integration.api_key, SecretString)
        assert integration.api_key is secret_key  # Same object preserved

    def test_model_validate_roundtrip(self):
        """Test that model_dump -> model_validate is a roundtrip."""
        original = DocumentIntelligenceIntegration(
            kind=IntegrationKind.REDUCTO,
            endpoint="https://api.reducto.ai/v1",
            api_key="secret-api-key-123",  # type: ignore[arg-type]
        )

        dumped = original.model_dump()
        restored = DocumentIntelligenceIntegration.model_validate(dumped)

        assert restored.kind == original.kind
        assert restored.endpoint == original.endpoint
        assert isinstance(restored.api_key, SecretString)
        assert restored.api_key.get_secret_value() == original.api_key.get_secret_value()

    def test_endpoint_url_validation_valid_urls(self):
        """Test that valid endpoint URLs are accepted."""
        valid_urls = [
            "https://api.reducto.ai/v1",
            "https://api.reducto.ai/v2/process",
            "http://localhost:8080/api",
            "https://custom-domain.com/reducto",
            "http://192.168.1.1:3000",
            "https://api.example.org:8443/v1/documents",
            "https://sub.domain.example.com/path/to/api",
        ]

        for url in valid_urls:
            integration = DocumentIntelligenceIntegration(
                kind=IntegrationKind.REDUCTO,
                endpoint=url,
                api_key="test-key",  # type: ignore[arg-type]
            )
            assert integration.endpoint == url

    def test_endpoint_url_validation_invalid_urls(self):
        """Test that invalid endpoint URLs raise ValueError."""
        invalid_urls = [
            "",  # Empty string
            "not-a-url",  # No scheme or netloc
            "ftp://example.com",  # Invalid scheme
            "://example.com",  # Missing scheme
            "https://",  # Missing netloc
            "http:/",  # Malformed URL
            "https:///path",  # Missing netloc
            "file:///local/path",  # Invalid scheme
            "example.com/api",  # Missing scheme
            "https://:8080/api",  # Missing hostname
        ]

        for url in invalid_urls:
            with pytest.raises(ValueError, match="Invalid endpoint URL"):
                DocumentIntelligenceIntegration(
                    kind=IntegrationKind.REDUCTO,
                    endpoint=url,
                    api_key="test-key",  # type: ignore[arg-type]
                )

    def test_endpoint_url_validation_model_validate(self):
        """Test that URL validation also works with model_validate."""
        # Valid case
        valid_data = {
            "kind": "reducto",
            "endpoint": "https://api.example.com/v1",
            "api_key": "test-key",
        }
        integration = DocumentIntelligenceIntegration.model_validate(valid_data)
        assert integration.endpoint == "https://api.example.com/v1"

        # Invalid case
        invalid_data = {
            "kind": "reducto",
            "endpoint": "not-a-valid-url",
            "api_key": "test-key",
        }
        with pytest.raises(ValueError, match="Invalid endpoint URL"):
            DocumentIntelligenceIntegration.model_validate(invalid_data)
