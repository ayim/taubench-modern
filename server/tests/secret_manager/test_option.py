"""Unit tests for SecretService."""

from unittest.mock import MagicMock, patch

import pytest

from agent_platform.server.secret_manager.aws_sm.aws_sm import AwsSecretManager
from agent_platform.server.secret_manager.base import BaseSecretManager
from agent_platform.server.secret_manager.environment.environment import EnvironmentSecretManager
from agent_platform.server.secret_manager.local_file.local_file import LocalFileSecretManager
from agent_platform.server.secret_manager.option import SecretService


class TestSecretService:
    """Test suite for SecretService."""

    def setup_method(self):
        """Reset singleton before each test."""
        SecretService._instance = None

    def test_get_instance_creates_singleton(self, monkeypatch):
        """Test that get_instance creates a singleton."""
        # Explicitly set to file source to avoid AWS default
        monkeypatch.setenv("SEMA4AI_AGENT_SERVER_ENCRYPTION_KEY_SOURCE", "file")

        instance1 = SecretService.get_instance()
        instance2 = SecretService.get_instance()

        assert instance1 is instance2
        assert isinstance(instance1, BaseSecretManager)

    def test_get_instance_with_file_source(self, monkeypatch):
        """Test get_instance with file source."""
        monkeypatch.setenv("SEMA4AI_AGENT_SERVER_ENCRYPTION_KEY_SOURCE", "file")
        instance = SecretService.get_instance()

        assert isinstance(instance, LocalFileSecretManager)
        assert isinstance(instance, BaseSecretManager)

    def test_get_instance_with_environment_source(self, monkeypatch):
        """Test get_instance with environment source."""
        monkeypatch.setenv("SEMA4AI_AGENT_SERVER_ENCRYPTION_KEY_SOURCE", "environment")
        instance = SecretService.get_instance()

        assert isinstance(instance, EnvironmentSecretManager)
        assert isinstance(instance, BaseSecretManager)

    @patch("boto3.client")
    def test_get_instance_with_aws_source(self, mock_boto_client, monkeypatch):
        """Test get_instance with AWS source."""
        # Mock the boto3 client to prevent real AWS calls
        mock_client = MagicMock()
        mock_boto_client.return_value = mock_client

        monkeypatch.setenv("SEMA4AI_AGENT_SERVER_ENCRYPTION_KEY_SOURCE", "aws")
        monkeypatch.setenv(
            "SEMA4AI_AGENT_SERVER_ENCRYPTION_KEY_AWS_KMS_ARN",
            "arn:aws:kms:eu-west-1:471112748664:key/d22373bb-5466-4ea9-a770-195cef4f4a00",
        )

        instance = SecretService.get_instance()
        assert isinstance(instance, AwsSecretManager)

    def test_get_instance_defaults_to_file(self, monkeypatch):
        """Test that get_instance defaults to file when env var not set."""
        monkeypatch.delenv("SEMA4AI_AGENT_SERVER_ENCRYPTION_KEY_SOURCE", raising=False)
        instance = SecretService.get_instance()

        assert isinstance(instance, LocalFileSecretManager)

    def test_initialize_secret_manager_file(self, monkeypatch):
        """Test _initialize_secret_manager with file source."""
        monkeypatch.setenv("SEMA4AI_AGENT_SERVER_ENCRYPTION_KEY_SOURCE", "file")
        manager = SecretService._initialize_secret_manager()

        assert isinstance(manager, LocalFileSecretManager)

    def test_initialize_secret_manager_environment(self, monkeypatch):
        """Test _initialize_secret_manager with environment source."""
        monkeypatch.setenv("SEMA4AI_AGENT_SERVER_ENCRYPTION_KEY_SOURCE", "environment")
        manager = SecretService._initialize_secret_manager()

        assert isinstance(manager, EnvironmentSecretManager)

    @patch("boto3.client")
    def test_initialize_secret_manager_aws(self, mock_boto_client, monkeypatch):
        """Test AWS secret manager initialization."""
        mock_client = MagicMock()
        mock_boto_client.return_value = mock_client

        monkeypatch.setenv("SEMA4AI_AGENT_SERVER_ENCRYPTION_KEY_SOURCE", "aws")
        monkeypatch.setenv(
            "SEMA4AI_AGENT_SERVER_ENCRYPTION_KEY_AWS_KMS_ARN",
            "arn:aws:kms:eu-west-1:471112748664:key/d22373bb-5466-4ea9-a770-195cef4f4a00",
        )

        manager = SecretService._initialize_secret_manager()
        assert isinstance(manager, AwsSecretManager)

    def test_initialize_secret_manager_unsupported_source(self, monkeypatch):
        """Test _initialize_secret_manager with unsupported source."""
        monkeypatch.setenv("SEMA4AI_AGENT_SERVER_ENCRYPTION_KEY_SOURCE", "unsupported")

        with pytest.raises(ValueError, match="secret source type unsupported not supported"):
            SecretService._initialize_secret_manager()

    def test_initialize_secret_manager_case_sensitivity(self, monkeypatch):
        """Test that secret source is case sensitive."""
        monkeypatch.setenv("SEMA4AI_AGENT_SERVER_ENCRYPTION_KEY_SOURCE", "FILE")

        with pytest.raises(ValueError, match="secret source type FILE not supported"):
            SecretService._initialize_secret_manager()

    def test_singleton_persists_across_calls(self, monkeypatch):
        """Test that singleton persists across multiple calls."""
        # Explicitly set to file source to avoid AWS default
        monkeypatch.setenv("SEMA4AI_AGENT_SERVER_ENCRYPTION_KEY_SOURCE", "file")

        instance1 = SecretService.get_instance()
        instance2 = SecretService.get_instance()
        instance3 = SecretService.get_instance()

        assert instance1 is instance2 is instance3

    @patch("boto3.client")
    def test_different_env_var_values(self, mock_boto_client, monkeypatch):
        """Test different environment variable values."""
        # Mock boto3 client for AWS tests
        mock_client = MagicMock()
        mock_boto_client.return_value = mock_client

        test_cases = [
            ("file", LocalFileSecretManager),
            ("environment", EnvironmentSecretManager),
            ("aws", AwsSecretManager),
        ]

        for env_value, expected_type in test_cases:
            # Reset singleton for each test case
            SecretService._instance = None

            monkeypatch.setenv("SEMA4AI_AGENT_SERVER_ENCRYPTION_KEY_SOURCE", env_value)

            # Set AWS configuration for AWS test case
            if env_value == "aws":
                monkeypatch.setenv(
                    "SEMA4AI_AGENT_SERVER_ENCRYPTION_KEY_AWS_KMS_ARN",
                    "arn:aws:kms:eu-west-1:471112748664:key/d22373bb-5466-4ea9-a770-195cef4f4a00",
                )

            instance = SecretService.get_instance()
            assert isinstance(instance, expected_type)

    def test_empty_env_var_treated_as_unsupported(self, monkeypatch):
        """Test that empty environment variable is treated as unsupported."""
        monkeypatch.setenv("SEMA4AI_AGENT_SERVER_ENCRYPTION_KEY_SOURCE", "")
        with pytest.raises(ValueError, match="secret source type  not supported"):
            SecretService.get_instance()

    def test_whitespace_env_var_treated_as_unsupported(self, monkeypatch):
        """Test that whitespace in env var is treated as unsupported."""
        monkeypatch.setenv("SEMA4AI_AGENT_SERVER_ENCRYPTION_KEY_SOURCE", " file ")
        with pytest.raises(ValueError, match="secret source type  file  not supported"):
            SecretService._initialize_secret_manager()

    def test_none_env_var_defaults_to_file(self, monkeypatch):
        """Test that None environment variable (missing) defaults to file."""
        # Ensure the env var is not set
        monkeypatch.delenv("SEMA4AI_AGENT_SERVER_ENCRYPTION_KEY_SOURCE", raising=False)

        instance = SecretService.get_instance()
        assert isinstance(instance, LocalFileSecretManager)
