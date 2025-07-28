"""
Envelope encryption implementation that separates data encryption keys (DEK) from
key encryption keys (KEK/master keys).

This allows for flexible key management strategies where the master key can be
stored in various secure locations (KMS, Key Vault, etc.) while the data
encryption remains consistent.
"""

import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass
class EncryptionMetadata:
    """Metadata for the encryption operation."""

    scheme: str
    kek_type: str
    enc_ts: str
    key_id: str | None = None  # Optional field for KMS implementations

    def to_json(self) -> str:
        """Convert metadata to a JSON string."""
        data = {
            "scheme": self.scheme,
            "kek_type": self.kek_type,
            "enc_ts": self.enc_ts,
        }
        if self.key_id is not None:
            data["key_id"] = self.key_id
        return json.dumps(data)

    @classmethod
    def from_json(cls, json_str: str) -> "EncryptionMetadata":
        """Create metadata from a JSON string."""
        data = json.loads(json_str)
        return cls(
            scheme=data["scheme"],
            kek_type=data["kek_type"],
            enc_ts=data["enc_ts"],
            key_id=data.get("key_id"),  # Optional field
        )


@dataclass
class EnvelopeEncryptionResult:
    """
    Result of envelope encryption containing:
    - metadata: Information about the encryption scheme and process
    - encrypted_data_key: The data encryption key (DEK) encrypted with the master key using XOR
    - encrypted_data: The actual encrypted data using the DEK with AES-GCM
    - data_nonce: Nonce used for data encryption
    - data_tag: Authentication tag for data encryption
    - associated_data: Additional authenticated data used in AES-GCM encryption
    """

    metadata: EncryptionMetadata
    encrypted_data_key: bytes
    encrypted_data: bytes
    data_nonce: bytes
    data_tag: bytes
    associated_data: bytes

    def to_json(self) -> str:
        """Convert the envelope encryption result to a JSON string."""
        metadata_dict = {
            "scheme": self.metadata.scheme,
            "kek_type": self.metadata.kek_type,
            "enc_ts": self.metadata.enc_ts,
        }
        if self.metadata.key_id is not None:
            metadata_dict["key_id"] = self.metadata.key_id

        return json.dumps(
            {
                "metadata": metadata_dict,
                "encrypted_data_key": self.encrypted_data_key.hex(),
                "encrypted_data": self.encrypted_data.hex(),
                "data_nonce": self.data_nonce.hex(),
                "data_tag": self.data_tag.hex(),
                "associated_data": self.associated_data.hex(),
            },
            separators=(",", ":"),
            sort_keys=True,
        )

    @classmethod
    def from_json(cls, json_str: str) -> "EnvelopeEncryptionResult":
        """Create an EnvelopeEncryptionResult from a JSON string."""
        data = json.loads(json_str)
        return cls(
            metadata=EncryptionMetadata(
                scheme=data["metadata"]["scheme"],
                kek_type=data["metadata"]["kek_type"],
                enc_ts=data["metadata"]["enc_ts"],
                key_id=data["metadata"].get("key_id"),  # Optional field
            ),
            encrypted_data_key=bytes.fromhex(data["encrypted_data_key"]),
            encrypted_data=bytes.fromhex(data["encrypted_data"]),
            data_nonce=bytes.fromhex(data["data_nonce"]),
            data_tag=bytes.fromhex(data["data_tag"]),
            associated_data=bytes.fromhex(data["associated_data"]),
        )


class EnvelopeEncryption(ABC):
    """
    Abstract base class for envelope encryption implementations.
    This class defines the interface for encrypting data using envelope encryption,
    where a data encryption key (DEK) is used to encrypt the actual data, and the DEK
    itself is encrypted using a master key (key encryption key, KEK).
    """

    @abstractmethod
    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt the plaintext using envelope encryption.

        :param plaintext: The string to be encrypted (e.g., a JSON stringified object)
        :return: JSON stringified data structure containing everything needed to decrypt,
                except the master key
        """
        pass

    @abstractmethod
    def decrypt(self, result_of_encryption: str) -> str:
        """
        Decrypt the data that was encrypted using envelope encryption.

        :param result_of_encryption: The JSON stringified data structure from encrypt()
        :return: The original plaintext string
        """
        pass


class StaticKeyEnvelopeEncryption(EnvelopeEncryption):
    """
    Implementation of envelope encryption using a static master key.
    This implementation:
    - Uses XOR for key encryption (DEK ⊕ master_key)
    - Uses AES-GCM for data encryption
    """

    SCHEME = "sema4ai-envelope-aes-gcm-256-v1"
    KEK_TYPE = "static-key"

    def __init__(self, master_key: bytes):
        """
        Initialize with a master key for key encryption.

        :param master_key: 32-byte (256-bit) master key
        """
        from .aes_gcm import AESGCM2

        if len(master_key) != AESGCM2.VALID_KEY_SIZE:
            raise ValueError(f"Master key must be exactly {AESGCM2.VALID_KEY_SIZE} bytes long")
        self.master_key = master_key

    def _xor_encrypt_key(self, key: bytes) -> bytes:
        """
        Encrypt/decrypt a key using XOR with the master key.
        XOR is its own inverse, so the same operation works for both encryption and decryption.
        Example: (A xor B) xor B = A

        :param key: The key to encrypt/decrypt (must be same length as master key)
        :return: The encrypted/decrypted key
        """
        if len(key) != len(self.master_key):
            raise ValueError("Key length must match master key length")
        return bytes(a ^ b for a, b in zip(key, self.master_key, strict=False))

    def encrypt(self, plaintext: str) -> str:
        from .aes_gcm import AESGCM2

        data_encryption_key = os.urandom(AESGCM2.VALID_KEY_SIZE)
        encrypted_dek = self._xor_encrypt_key(data_encryption_key)

        metadata = EncryptionMetadata(
            scheme=self.SCHEME,
            kek_type=self.KEK_TYPE,
            enc_ts=datetime.now(UTC).isoformat(),
        )

        data_cipher = AESGCM2(data_encryption_key)
        data_encryption_result = data_cipher.encrypt(
            plaintext.encode(),
            associated_data=metadata.to_json().encode(),
        )

        envelope_result = EnvelopeEncryptionResult(
            metadata=metadata,
            encrypted_data_key=encrypted_dek,
            encrypted_data=data_encryption_result.ciphertext,
            data_nonce=data_encryption_result.nonce,
            data_tag=data_encryption_result.tag,
            associated_data=metadata.to_json().encode(),
        )

        return envelope_result.to_json()

    def decrypt(self, result_of_encryption: str) -> str:
        from .aes_gcm import AESGCM2

        envelope_result = EnvelopeEncryptionResult.from_json(result_of_encryption)

        if envelope_result.metadata.scheme != self.SCHEME:
            raise ValueError(
                f"Unsupported encryption scheme: {envelope_result.metadata.scheme}, expected: {self.SCHEME}"  # noqa: E501
            )

        if envelope_result.metadata.kek_type != self.KEK_TYPE:
            raise ValueError(
                f"Unsupported key type: {envelope_result.metadata.kek_type}, expected: {self.KEK_TYPE}"  # noqa: E501
            )

        data_encryption_key = self._xor_encrypt_key(envelope_result.encrypted_data_key)
        data_cipher = AESGCM2(data_encryption_key)

        plaintext_bytes = data_cipher.decrypt(
            nonce=envelope_result.data_nonce,
            ciphertext=envelope_result.encrypted_data,
            tag=envelope_result.data_tag,
            associated_data=envelope_result.associated_data,
        )

        return plaintext_bytes.decode()
