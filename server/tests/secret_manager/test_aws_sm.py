"""Unit tests for AwsSecretManager."""

import json
from unittest.mock import MagicMock, patch

import pytest

from agent_platform.server.secret_manager.aws_sm.aws_sm import AwsKmsConstants, AwsSecretManager


class TestAwsSecretManager:
    """Test suite for AwsSecretManager."""

    # Test KMS ARN for testing
    TEST_KMS_ARN = "arn:aws:kms:eu-west-1:471112748664:key/d22373bb-5466-4ea9-a770-195cef4f4a00"

    @patch("boto3.client")
    def test_setup_with_arn_success(self, mock_boto_client):
        """Test successful setup with KMS ARN."""
        mock_client = MagicMock()
        mock_boto_client.return_value = mock_client

        manager = AwsSecretManager(kms_key_arn=self.TEST_KMS_ARN)

        mock_boto_client.assert_called_once_with("kms", region_name="eu-west-1")
        mock_client.describe_key.assert_called_once_with(KeyId=self.TEST_KMS_ARN)
        assert manager._kms_key_arn == self.TEST_KMS_ARN
        assert manager._region_name == "eu-west-1"

    def test_init_missing_arn(self):
        """Test initialization fails without KMS ARN."""
        with pytest.raises(ValueError, match="KMS key ARN is required"):
            AwsSecretManager(kms_key_arn=None)

    def test_parse_region_from_arn_success(self):
        """Test parsing region from valid ARN."""
        manager = AwsSecretManager.__new__(AwsSecretManager)  # Create without calling __init__

        region = manager._parse_region_from_arn(self.TEST_KMS_ARN)
        assert region == "eu-west-1"

    def test_parse_region_from_arn_invalid_format(self):
        """Test parsing region fails with invalid ARN format."""
        manager = AwsSecretManager.__new__(AwsSecretManager)  # Create without calling __init__

        with pytest.raises(ValueError, match="Invalid KMS ARN format"):
            manager._parse_region_from_arn("invalid-arn")

    @patch("boto3.client")
    def test_setup_key_not_found_error(self, mock_boto_client):
        """Test setup fails when KMS key is not found."""
        from botocore.exceptions import ClientError

        mock_client = MagicMock()
        mock_boto_client.return_value = mock_client
        mock_client.describe_key.side_effect = ClientError({"Error": {"Code": "NotFoundException"}}, "DescribeKey")

        with pytest.raises(RuntimeError, match="AWS KMS key not found"):
            AwsSecretManager(kms_key_arn=self.TEST_KMS_ARN)

    @patch("boto3.client")
    def test_store_and_fetch_roundtrip(self, mock_boto_client):
        """Test storing and fetching data works correctly."""
        mock_client = MagicMock()
        mock_boto_client.return_value = mock_client

        # Mock KMS responses
        mock_client.generate_data_key.return_value = {
            "Plaintext": b"0" * 32,  # 32-byte key
            "CiphertextBlob": b"encrypted_key_data",
        }
        mock_client.decrypt.return_value = {"Plaintext": b"0" * 32}

        manager = AwsSecretManager(kms_key_arn=self.TEST_KMS_ARN)

        # Test data
        data = "sensitive information"

        # Store data
        stored_ref = manager.store(data)
        assert isinstance(stored_ref, str)

        # Verify it's valid JSON
        parsed = json.loads(stored_ref)
        assert "metadata" in parsed
        assert "encrypted_data_key" in parsed

        # Fetch data
        retrieved = manager.fetch(stored_ref)
        assert retrieved == data

        # Verify KMS calls
        mock_client.generate_data_key.assert_called_once_with(
            KeyId=self.TEST_KMS_ARN, KeySpec=AwsKmsConstants.KEY_SPEC_AES_256
        )
        mock_client.decrypt.assert_called_once()

    @patch("boto3.client")
    def test_store_kms_access_denied(self, mock_boto_client):
        """Test store fails when KMS access is denied."""
        from botocore.exceptions import ClientError

        mock_client = MagicMock()
        mock_boto_client.return_value = mock_client
        mock_client.generate_data_key.side_effect = ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "Access denied"}},
            "GenerateDataKey",
        )

        manager = AwsSecretManager(kms_key_arn=self.TEST_KMS_ARN)

        with pytest.raises(RuntimeError, match="Access denied to AWS KMS"):
            manager.store("test data")

    @patch("boto3.client")
    def test_fetch_invalid_json(self, mock_boto_client):
        """Test fetch fails with invalid JSON."""
        mock_client = MagicMock()
        mock_boto_client.return_value = mock_client

        manager = AwsSecretManager(kms_key_arn=self.TEST_KMS_ARN)

        with pytest.raises(RuntimeError, match="Invalid stored reference"):
            manager.fetch("invalid json")
