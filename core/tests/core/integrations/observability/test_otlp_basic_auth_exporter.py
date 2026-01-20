"""Tests for OTLP Basic Auth observability exporter."""

import base64
from unittest.mock import MagicMock, patch

import pytest

from agent_platform.core.integrations.observability.models import (
    OtlpBasicAuthObservabilitySettings,
)
from agent_platform.core.utils import SecretString


class TestOtlpBasicAuthExporter:
    """Test OTLP Basic Auth exporter creation."""

    @patch("agent_platform.core.integrations.observability.models.build_network_session")
    @patch("agent_platform.core.integrations.observability.models.OTLPSpanExporter")
    def test_make_exporter_with_basic_auth(self, mock_exporter_class, mock_build_session):
        """Test make_exporter creates Basic Auth header correctly."""
        mock_session = MagicMock()
        mock_build_session.return_value = mock_session
        mock_exporter = MagicMock()
        mock_exporter_class.return_value = mock_exporter

        settings = OtlpBasicAuthObservabilitySettings(
            url="http://localhost:14318",
            username="alloy",
            password="steel",
        )

        exporter = settings.make_exporter()

        # Verify exporter was created with correct Basic Auth
        # Format: username:password
        expected_auth = base64.b64encode(b"alloy:steel").decode()
        mock_exporter_class.assert_called_once_with(
            endpoint="http://localhost:14318/v1/traces",
            headers={"Authorization": f"Basic {expected_auth}"},
            session=mock_session,
        )
        assert exporter == mock_exporter

    @patch("agent_platform.core.integrations.observability.models.build_network_session")
    @patch("agent_platform.core.integrations.observability.models.OTLPSpanExporter")
    def test_make_exporter_with_secret_string_password(self, mock_exporter_class, mock_build_session):
        """Test make_exporter handles SecretString password correctly."""
        mock_session = MagicMock()
        mock_build_session.return_value = mock_session
        mock_exporter = MagicMock()
        mock_exporter_class.return_value = mock_exporter

        settings = OtlpBasicAuthObservabilitySettings(
            url="http://localhost:14318",
            username="alloy",
            password=SecretString("steel"),
        )

        exporter = settings.make_exporter()

        # Verify exporter was created with correct Basic Auth
        expected_auth = base64.b64encode(b"alloy:steel").decode()
        mock_exporter_class.assert_called_once_with(
            endpoint="http://localhost:14318/v1/traces",
            headers={"Authorization": f"Basic {expected_auth}"},
            session=mock_session,
        )
        assert exporter == mock_exporter

    @pytest.mark.parametrize(
        ("missing_field", "provided_fields"),
        [
            ("url", {"username": "alloy", "password": "steel"}),
            ("username", {"url": "http://localhost:14318", "password": "steel"}),
            ("password", {"url": "http://localhost:14318", "username": "alloy"}),
        ],
    )
    def test_model_validate_requires_fields(self, missing_field: str, provided_fields: dict):
        """Test that model_validate raises if required fields are missing."""
        with pytest.raises(
            ValueError,
            match=f"OTLP Basic Auth settings require '{missing_field}'",
        ):
            OtlpBasicAuthObservabilitySettings.model_validate(provided_fields)

    @patch("agent_platform.core.integrations.observability.models.build_network_session")
    @patch("agent_platform.core.integrations.observability.models.OTLPSpanExporter")
    def test_endpoint_normalization(self, mock_exporter_class, mock_build_session):
        """Test that endpoint gets /v1/traces suffix added."""
        mock_build_session.return_value = MagicMock()
        mock_exporter_class.return_value = MagicMock()

        settings = OtlpBasicAuthObservabilitySettings(
            url="http://localhost:14318/",  # Note: trailing slash
            username="alloy",
            password="steel",
        )

        settings.make_exporter()

        # Verify endpoint was normalized (trailing slash removed, /v1/traces added)
        call_args = mock_exporter_class.call_args
        assert call_args[1]["endpoint"] == "http://localhost:14318/v1/traces"

    @patch("agent_platform.core.integrations.observability.models.build_network_session")
    @patch("agent_platform.core.integrations.observability.models.OTLPSpanExporter")
    def test_endpoint_already_has_suffix(self, mock_exporter_class, mock_build_session):
        """Test that endpoint with /v1/traces suffix is not duplicated."""
        mock_build_session.return_value = MagicMock()
        mock_exporter_class.return_value = MagicMock()

        settings = OtlpBasicAuthObservabilitySettings(
            url="http://localhost:14318/v1/traces",
            username="alloy",
            password="steel",
        )

        settings.make_exporter()

        # Verify endpoint was not duplicated
        call_args = mock_exporter_class.call_args
        assert call_args[1]["endpoint"] == "http://localhost:14318/v1/traces"

    @patch("agent_platform.core.integrations.observability.models.build_network_session")
    @patch("agent_platform.core.integrations.observability.models.OTLPSpanExporter")
    def test_multiple_exporters_get_separate_sessions(self, mock_exporter_class, mock_build_session):
        """Test that each exporter gets its own session (not shared).

        This is critical - if exporters share a session, headers from one will
        overwrite headers from another, causing all exporters to send to the
        same backend.
        """
        # Create two different session mocks
        session1 = MagicMock()
        session2 = MagicMock()
        mock_build_session.side_effect = [session1, session2]
        mock_exporter_class.return_value = MagicMock()

        settings1 = OtlpBasicAuthObservabilitySettings(
            url="http://localhost:14318",
            username="alloy",
            password="steel",
        )

        settings2 = OtlpBasicAuthObservabilitySettings(
            url="http://localhost:24318",
            username="tempo",
            password="iron",
        )

        # Create two exporters
        settings1.make_exporter()
        settings2.make_exporter()

        # Verify build_network_session was called twice (not shared)
        assert mock_build_session.call_count == 2

        # Verify each exporter got a different session
        calls = mock_exporter_class.call_args_list
        assert calls[0][1]["session"] == session1
        assert calls[1][1]["session"] == session2

    def test_model_dump_redaction(self):
        """Test that model_dump redacts password by default."""
        settings = OtlpBasicAuthObservabilitySettings(
            url="http://localhost:14318",
            username="alloy",
            password="steel",
        )

        # Test default redaction
        dumped = settings.model_dump()
        assert dumped["password"] == "**********"
        assert dumped["username"] == "alloy"
        assert dumped["url"] == "http://localhost:14318"

        # Test without redaction
        dumped_plain = settings.model_dump(redact_secret=False)
        assert dumped_plain["password"] == "steel"
        assert dumped_plain["username"] == "alloy"

    def test_model_dump_redaction_with_secret_string(self):
        """Test that model_dump redacts SecretString password correctly."""
        settings = OtlpBasicAuthObservabilitySettings(
            url="http://localhost:14318",
            username="alloy",
            password=SecretString("steel"),
        )

        # Test default redaction
        dumped = settings.model_dump()
        assert dumped["password"] == "**********"

        # Test without redaction
        dumped_plain = settings.model_dump(redact_secret=False)
        assert dumped_plain["password"] == "steel"

    def test_model_validate_from_dict(self):
        """Test that model_validate creates settings from dict."""
        data = {
            "url": "http://localhost:14318",
            "username": "alloy",
            "password": "steel",
        }

        settings = OtlpBasicAuthObservabilitySettings.model_validate(data)

        assert settings.url == "http://localhost:14318"
        assert settings.username == "alloy"
        assert settings.password == "steel"

    def test_model_validate_rejects_non_dict(self):
        """Test that model_validate rejects non-dict input."""
        with pytest.raises(
            ValueError,
            match="OTLP Basic Auth settings payload must be an object",
        ):
            OtlpBasicAuthObservabilitySettings.model_validate("not a dict")
