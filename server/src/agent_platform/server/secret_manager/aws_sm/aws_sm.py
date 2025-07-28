import json
from datetime import UTC, datetime
from typing import Any

import boto3
from botocore.exceptions import ClientError
from structlog import get_logger

from agent_platform.core.utils.encryption.aes_gcm import AESGCM2
from agent_platform.core.utils.encryption.envelope import (
    EncryptionMetadata,
    EnvelopeEncryptionResult,
)
from agent_platform.server.secret_manager.base import BaseSecretManager

logger = get_logger(__name__)


# AWS KMS Constants
class AwsKmsConstants:
    """Constants for AWS KMS operations."""

    # Service
    SERVICE_NAME = "kms"

    # Key specifications
    KEY_SPEC_AES_256 = "AES_256"

    # Error codes
    ERROR_NOT_FOUND = "NotFoundException"
    ERROR_ACCESS_DENIED = "AccessDeniedException"
    ERROR_DISABLED = "DisabledException"
    ERROR_INVALID_CIPHERTEXT = "InvalidCiphertextException"


class AwsSecretManager(BaseSecretManager):
    """
    AWS KMS-based secret manager using envelope encryption.

    This implementation:
    1. Uses AWS KMS to generate and encrypt/decrypt data keys
    2. Uses local AES-GCM encryption for actual data
    3. Returns JSON envelope containing metadata, encrypted data key, and encrypted data
    4. Follows the envelope encryption pattern for secure key management
    """

    SCHEME = "sema4ai-envelope-aws-kms-aes-gcm-256-v1"
    KEK_TYPE = "aws-kms"

    def __init__(self, kms_key_arn: str | None = None):
        """
        Initialize the AWS KMS Secret Manager.

        Args:
            kms_key_arn: AWS KMS key ARN (e.g., arn:aws:kms:region:account:key/key-id).
        """
        self._kms_key_arn = kms_key_arn
        self._region_name: str | None = None
        self._client: Any | None = None

        if self._kms_key_arn is None:
            raise ValueError("KMS key ARN is required to initialize AWS KMS Secret Manager")

        # Parse region from ARN
        self._region_name = self._parse_region_from_arn(self._kms_key_arn)

        self.setup()

    def _parse_region_from_arn(self, arn: str) -> str:
        """
        Parse AWS region from KMS key ARN.

        Args:
            arn: KMS key ARN (e.g., arn:aws:kms:region:account:key/key-id)

        Returns:
            AWS region name

        Raises:
            ValueError: If ARN format is invalid
        """
        try:
            # ARN format: arn:aws:kms:region:account:key/key-id
            # Minimum expected parts: arn, aws, kms, region
            min_arn_parts = 4
            parts = arn.split(":")
            if (
                len(parts) < min_arn_parts
                or parts[0] != "arn"
                or parts[1] != "aws"
                or parts[2] != "kms"
            ):
                raise ValueError("Invalid KMS ARN format")
            return parts[3]  # region is the 4th component
        except (IndexError, AttributeError) as e:
            raise ValueError(f"Invalid KMS ARN format: {arn}") from e

    def setup(self) -> None:
        """
        Setup the AWS KMS client and validate configuration.

        Initializes the boto3 KMS client and validates the KMS key ID.
        """
        try:
            try:
                self._client = boto3.client(
                    AwsKmsConstants.SERVICE_NAME, region_name=self._region_name
                )
                logger.info(f"AWS KMS client initialized for region: {self._region_name}")
            except Exception as client_error:
                logger.error(f"Failed to create AWS KMS client: {client_error}")
                raise RuntimeError(
                    f"Failed to create AWS KMS client: {client_error}"
                ) from client_error

            # Assert for type checker - client should be initialized at this point
            assert self._client is not None

            # If no KMS key ID is provided, raise an error
            if not self._kms_key_arn:
                raise RuntimeError("AWS KMS key ARN not provided.")

            # Validate KMS key exists and we have permissions
            try:
                self._client.describe_key(KeyId=self._kms_key_arn)
                logger.info(f"AWS KMS key validated: {self._kms_key_arn}")
            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "Unknown")
                if error_code == AwsKmsConstants.ERROR_NOT_FOUND:
                    raise RuntimeError(f"AWS KMS key not found: {self._kms_key_arn}") from e
                elif error_code == AwsKmsConstants.ERROR_ACCESS_DENIED:
                    raise RuntimeError(
                        f"Access denied to AWS KMS key: {self._kms_key_arn}. "
                        "Ensure proper IAM permissions are configured."
                    ) from e
                else:
                    raise RuntimeError(f"Failed to validate AWS KMS key: {e}") from e

        except Exception as e:
            logger.error(f"Failed to initialize AWS KMS client: {e}")
            raise RuntimeError(f"AWS KMS setup failed: {e}") from e

    def store(self, data: str) -> str:
        """
        Store data using AWS KMS envelope encryption.

        1. Generates a data key using AWS KMS
        2. Encrypts the data locally using AES-GCM with the plaintext data key
        3. Returns the encrypted envelope containing the KMS-encrypted data key

        Args:
            data: The plaintext data to store securely

        Returns:
            JSON string containing the encrypted envelope

        Raises:
            RuntimeError: If the client is not initialized or encryption fails
        """
        if self._client is None:
            raise RuntimeError("AWS KMS client not initialized. Call setup() first.")

        if not self._kms_key_arn:
            raise RuntimeError("AWS KMS key ARN not configured.")

        try:
            # Generate a data key using AWS KMS
            response = self._client.generate_data_key(
                KeyId=self._kms_key_arn, KeySpec=AwsKmsConstants.KEY_SPEC_AES_256
            )

            plaintext_data_key = response["Plaintext"]
            encrypted_data_key = response["CiphertextBlob"]

            # Create metadata
            metadata = EncryptionMetadata(
                scheme=self.SCHEME,
                kek_type=self.KEK_TYPE,
                enc_ts=datetime.now(UTC).isoformat(),
                key_id=self._kms_key_arn,
            )

            # Encrypt the data using AES-GCM with the plaintext data key
            data_cipher = AESGCM2(plaintext_data_key)
            encryption_result = data_cipher.encrypt(
                data.encode(), associated_data=metadata.to_json().encode()
            )

            # Create envelope result
            envelope_result = EnvelopeEncryptionResult(
                metadata=metadata,
                encrypted_data_key=encrypted_data_key,
                encrypted_data=encryption_result.ciphertext,
                data_nonce=encryption_result.nonce,
                data_tag=encryption_result.tag,
                associated_data=metadata.to_json().encode(),
            )

            # Clear the plaintext key from memory
            plaintext_data_key = b"\x00" * len(plaintext_data_key)

            result_json = envelope_result.to_json()
            logger.info("Successfully encrypted data using AWS KMS envelope encryption")
            return result_json

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))
            logger.error(f"AWS KMS encryption failed - {error_code}: {error_message}")

            if error_code == AwsKmsConstants.ERROR_ACCESS_DENIED:
                raise RuntimeError(
                    "Access denied to AWS KMS. Ensure proper IAM permissions for "
                    f"kms:GenerateDataKey on key: {self._kms_key_arn}"
                ) from e
            elif error_code == AwsKmsConstants.ERROR_NOT_FOUND:
                raise RuntimeError(f"AWS KMS key not found: {self._kms_key_arn}") from e
            elif error_code == AwsKmsConstants.ERROR_DISABLED:
                raise RuntimeError(f"AWS KMS key is disabled: {self._kms_key_arn}") from e
            else:
                raise RuntimeError(f"AWS KMS encryption failed: {error_message}") from e

        except (RuntimeError, ValueError):
            raise

        except Exception as e:
            # Only sanitize truly unexpected exceptions that might contain sensitive data
            logger.error("Unexpected error during encryption")
            raise RuntimeError("Failed to encrypt data due to unexpected error") from e

    def _parse_and_validate_envelope(self, stored_reference: str) -> EnvelopeEncryptionResult:
        """Parse and validate the envelope from stored reference."""
        try:
            envelope_result = EnvelopeEncryptionResult.from_json(stored_reference)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid stored reference format: {e}")
            raise RuntimeError("Invalid stored reference: not valid JSON") from e
        except KeyError as e:
            logger.error(f"Missing required field in stored reference: {e}")
            raise RuntimeError(f"Invalid stored reference: missing field {e}") from e

        # Validate scheme and key type
        if envelope_result.metadata.scheme != self.SCHEME:
            raise RuntimeError(
                f"Unsupported encryption scheme: {envelope_result.metadata.scheme}, "
                f"expected: {self.SCHEME}"
            )

        if envelope_result.metadata.kek_type != self.KEK_TYPE:
            raise RuntimeError(
                f"Unsupported key type: {envelope_result.metadata.kek_type}, "
                f"expected: {self.KEK_TYPE}"
            )

        return envelope_result

    def _decrypt_data_key(self, envelope_result: EnvelopeEncryptionResult) -> bytes:
        """Decrypt the data key using AWS KMS."""
        if self._client is None:
            raise RuntimeError("AWS KMS client not initialized. Call setup() first.")

        try:
            response = self._client.decrypt(
                CiphertextBlob=envelope_result.encrypted_data_key,
                KeyId=envelope_result.metadata.key_id,  # Specify the key for additional security
            )
            return response["Plaintext"]
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))
            logger.error(f"AWS KMS decryption failed - {error_code}: {error_message}")

            if error_code == AwsKmsConstants.ERROR_ACCESS_DENIED:
                raise RuntimeError(
                    "Access denied to AWS KMS. Ensure proper IAM permissions for "
                    "kms:Decrypt on the key used for encryption."
                ) from e
            elif error_code == AwsKmsConstants.ERROR_INVALID_CIPHERTEXT:
                raise RuntimeError("Invalid encrypted data key format") from e
            elif error_code == AwsKmsConstants.ERROR_NOT_FOUND:
                raise RuntimeError("AWS KMS key used for encryption not found") from e
            else:
                raise RuntimeError(f"AWS KMS decryption failed: {error_message}") from e

    def fetch(self, stored_reference: str) -> str:
        """
        Retrieve and decrypt data using AWS KMS envelope encryption.

        1. Parses the stored envelope
        2. Uses AWS KMS to decrypt the data key
        3. Uses the plaintext data key to decrypt the data locally

        Args:
            stored_reference: The JSON envelope returned from store()

        Returns:
            The original plaintext data

        Raises:
            RuntimeError: If the client is not initialized or decryption fails
        """
        if self._client is None:
            raise RuntimeError("AWS KMS client not initialized. Call setup() first.")

        try:
            # Parse and validate the envelope
            envelope_result = self._parse_and_validate_envelope(stored_reference)

            # Decrypt the data key using AWS KMS
            plaintext_data_key = self._decrypt_data_key(envelope_result)

            # Decrypt the data using AES-GCM
            data_cipher = AESGCM2(plaintext_data_key)
            plaintext_bytes = data_cipher.decrypt(
                nonce=envelope_result.data_nonce,
                ciphertext=envelope_result.encrypted_data,
                tag=envelope_result.data_tag,
                associated_data=envelope_result.associated_data,
            )

            # Clear the plaintext key from memory
            plaintext_data_key = b"\x00" * len(plaintext_data_key)

            logger.info("Successfully decrypted data using AWS KMS envelope encryption")
            return plaintext_bytes.decode()

        except (RuntimeError, ValueError, json.JSONDecodeError, KeyError):
            raise

        except Exception as e:
            # Only sanitize truly unexpected exceptions that might contain sensitive data
            logger.error("Unexpected error during decryption")
            raise RuntimeError("Failed to decrypt data due to unexpected error") from e
