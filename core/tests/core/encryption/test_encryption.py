import json
import os
from datetime import UTC, datetime

import pytest
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from agent_platform.core.utils.encryption import (
    AESGCM2,
    StaticKeyEnvelopeEncryption,
)


class TestAESGCM:
    def test_encrypt_decrypt(self):
        key = AESGCM.generate_key(bit_length=256)
        aesgcm_encrypt = AESGCM2(key)

        data = b"The most secret message"
        aad = b"header-data"

        encrypted_data = aesgcm_encrypt.encrypt(data, aad)

        aesgcm_decrypt = AESGCM2(key)
        decrypted_data = aesgcm_decrypt.decrypt(
            nonce=encrypted_data.nonce,
            ciphertext=encrypted_data.ciphertext,
            tag=encrypted_data.tag,
            associated_data=aad,
        )

        assert decrypted_data == data

    def test_encrypt_decrypt_without_aad(self):
        key = AESGCM.generate_key(bit_length=256)
        aesgcm_encrypt = AESGCM2(key)

        data = b"The most secret message"

        encrypted_data = aesgcm_encrypt.encrypt(data, None)

        aesgcm_decrypt = AESGCM2(key)
        decrypted_data = aesgcm_decrypt.decrypt(
            nonce=encrypted_data.nonce,
            ciphertext=encrypted_data.ciphertext,
            tag=encrypted_data.tag,
            associated_data=None,
        )

        assert decrypted_data == data

    def test_encrypt_decrypt_wrong_key(self):
        encrypt_key = AESGCM.generate_key(bit_length=256)
        aesgcm_encrypt = AESGCM2(encrypt_key)

        data = b"The most secret message"
        aad = b"header-data"

        encrypted_data = aesgcm_encrypt.encrypt(data, aad)

        # Setup different key for decryption
        decrypt_key = AESGCM.generate_key(bit_length=256)
        aesgcm_decrypt = AESGCM2(decrypt_key)

        decrypted_data = None

        # Attempt decryption with wrong key should raise InvalidTag
        with pytest.raises(InvalidTag):
            decrypted_data = aesgcm_decrypt.decrypt(
                nonce=encrypted_data.nonce,
                ciphertext=encrypted_data.ciphertext,
                tag=encrypted_data.tag,
                associated_data=aad,
            )

        assert decrypted_data is None

    def test_encrypt_decrypt_modified_aad(self):
        key = AESGCM.generate_key(bit_length=256)
        aesgcm_encrypt = AESGCM2(key)

        data = b"The most secret message"
        aad = json.dumps({"scheme": "test-scheme", "kek_type": "test-key", "enc_ts": "2024-03-20T10:00:00Z"}).encode()

        encrypted_data = aesgcm_encrypt.encrypt(data, aad)

        aesgcm_decrypt = AESGCM2(key)

        # Test with modified scheme in AAD
        modified_aad = json.dumps(
            {"scheme": "modified-scheme", "kek_type": "test-key", "enc_ts": "2024-03-20T10:00:00Z"}
        ).encode()
        with pytest.raises(InvalidTag):
            aesgcm_decrypt.decrypt(
                nonce=encrypted_data.nonce,
                ciphertext=encrypted_data.ciphertext,
                tag=encrypted_data.tag,
                associated_data=modified_aad,
            )

        # Test with reordered JSON keys in AAD
        modified_aad = json.dumps(
            {"enc_ts": "2024-03-20T10:00:00Z", "kek_type": "test-key", "scheme": "test-scheme"},
            sort_keys=False,
        ).encode()
        with pytest.raises(InvalidTag):
            aesgcm_decrypt.decrypt(
                nonce=encrypted_data.nonce,
                ciphertext=encrypted_data.ciphertext,
                tag=encrypted_data.tag,
                associated_data=modified_aad,
            )

        # Test with extra field in AAD
        modified_aad = json.dumps(
            {
                "scheme": "test-scheme",
                "kek_type": "test-key",
                "enc_ts": "2024-03-20T10:00:00Z",
                "extra": "field",
            }
        ).encode()
        with pytest.raises(InvalidTag):
            aesgcm_decrypt.decrypt(
                nonce=encrypted_data.nonce,
                ciphertext=encrypted_data.ciphertext,
                tag=encrypted_data.tag,
                associated_data=modified_aad,
            )

        # Verify original AAD still works
        decrypted_data = aesgcm_decrypt.decrypt(
            nonce=encrypted_data.nonce,
            ciphertext=encrypted_data.ciphertext,
            tag=encrypted_data.tag,
            associated_data=aad,
        )
        assert decrypted_data == data


class TestEnvelopeEncryption:
    def test_encrypt_decrypt(self):
        master_key = AESGCM.generate_key(bit_length=256)
        encryption = StaticKeyEnvelopeEncryption(master_key)

        plaintext = json.dumps({"sensitive": "data", "numbers": [1, 2, 3]})
        encrypted = encryption.encrypt(plaintext)

        # Verify the encrypted result is a valid JSON with expected structure
        encrypted_data = json.loads(encrypted)
        assert "metadata" in encrypted_data
        assert encrypted_data["metadata"]["scheme"] == StaticKeyEnvelopeEncryption.SCHEME
        assert encrypted_data["metadata"]["kek_type"] == StaticKeyEnvelopeEncryption.KEK_TYPE

        # Verify timestamp is recent and in ISO format
        enc_ts = datetime.fromisoformat(encrypted_data["metadata"]["enc_ts"])
        assert enc_ts.tzinfo == UTC
        time_diff = datetime.now(UTC) - enc_ts
        assert time_diff.total_seconds() < 10  # Test should complete within 10 seconds

        decrypted = encryption.decrypt(encrypted)
        assert decrypted == plaintext

    def test_encrypt_decrypt_wrong_master_key(self):
        master_key1 = AESGCM.generate_key(bit_length=256)
        master_key2 = AESGCM.generate_key(bit_length=256)

        encryption1 = StaticKeyEnvelopeEncryption(master_key1)
        encryption2 = StaticKeyEnvelopeEncryption(master_key2)

        plaintext = json.dumps({"sensitive": "data"})
        encrypted = encryption1.encrypt(plaintext)

        # With XOR, wrong key will decrypt to wrong DEK, which will then fail AES-GCM
        with pytest.raises(InvalidTag):
            encryption2.decrypt(encrypted)

    def test_encrypt_decrypt_large_data(self):
        master_key = AESGCM.generate_key(bit_length=256)
        encryption = StaticKeyEnvelopeEncryption(master_key)

        large_data = {
            "array": list(range(1000)),
            "nested": {"data": "x" * 1000},
            "strings": ["test" * 100] * 10,
        }
        plaintext = json.dumps(large_data)

        encrypted = encryption.encrypt(plaintext)
        decrypted = encryption.decrypt(encrypted)

        assert decrypted == plaintext

    def test_xor_key_encryption(self):
        master_key = AESGCM.generate_key(bit_length=256)
        encryption = StaticKeyEnvelopeEncryption(master_key)

        # Test that XOR encryption is reversible
        test_key = os.urandom(32)
        encrypted_key = encryption._xor_encrypt_key(test_key)
        decrypted_key = encryption._xor_encrypt_key(encrypted_key)
        assert test_key == decrypted_key
        assert encrypted_key != test_key  # XOR with non-zero key should change the value

    def test_invalid_master_key_length(self):
        # Test that wrong master key length is rejected
        with pytest.raises(ValueError) as exc_info:  # noqa: PT011
            StaticKeyEnvelopeEncryption(os.urandom(16))
        assert "32 bytes" in str(exc_info.value)

        with pytest.raises(ValueError) as exc_info:  # noqa: PT011
            StaticKeyEnvelopeEncryption(os.urandom(64))
        assert "32 bytes" in str(exc_info.value)

    def test_unsupported_scheme(self):
        master_key = AESGCM.generate_key(bit_length=256)
        encryption = StaticKeyEnvelopeEncryption(master_key)

        # Encrypt some data
        plaintext = json.dumps({"test": "data"})
        encrypted = encryption.encrypt(plaintext)

        # Modify the scheme in the encrypted data
        encrypted_data = json.loads(encrypted)
        encrypted_data["metadata"]["scheme"] = "unsupported-scheme"
        modified_encrypted = json.dumps(encrypted_data)

        # Attempt to decrypt with modified scheme should fail
        with pytest.raises(ValueError, match="Unsupported encryption scheme"):
            encryption.decrypt(modified_encrypted)

    def test_unsupported_key_type(self):
        master_key = AESGCM.generate_key(bit_length=256)
        encryption = StaticKeyEnvelopeEncryption(master_key)

        # Encrypt some data
        plaintext = json.dumps({"test": "data"})
        encrypted = encryption.encrypt(plaintext)

        # Modify the key type in the encrypted data
        encrypted_data = json.loads(encrypted)
        encrypted_data["metadata"]["kek_type"] = "aws-kms"
        modified_encrypted = json.dumps(encrypted_data)

        # Attempt to decrypt with modified key type should fail
        with pytest.raises(ValueError, match="Unsupported key type"):
            encryption.decrypt(modified_encrypted)

    def test_key_id_fallback(self):
        """Test that fallback key_id is correctly stored in metadata."""
        master_key = AESGCM.generate_key(bit_length=256)
        encryption = StaticKeyEnvelopeEncryption(master_key, key_id="fallback")

        plaintext = json.dumps({"test": "data"})
        encrypted = encryption.encrypt(plaintext)

        # Verify key_id is stored correctly
        encrypted_data = json.loads(encrypted)
        assert encrypted_data["metadata"]["key_id"] == "fallback"

    def test_key_id_sha256_hash(self):
        """Test that SHA256 hash key_id is correctly stored and consistent."""
        import hashlib

        master_key = AESGCM.generate_key(bit_length=256)
        expected_key_id = hashlib.sha256(master_key).hexdigest()
        encryption = StaticKeyEnvelopeEncryption(master_key, key_id=expected_key_id)

        plaintext = json.dumps({"test": "data"})
        encrypted = encryption.encrypt(plaintext)

        # Verify key_id matches SHA256 hash
        encrypted_data = json.loads(encrypted)
        assert encrypted_data["metadata"]["key_id"] == expected_key_id
        assert len(expected_key_id) == 64  # SHA256 hex is 64 characters

    def test_key_id_consistency(self):
        """Test that same key produces same key_id across encryptions."""
        import hashlib

        master_key = AESGCM.generate_key(bit_length=256)
        key_id = hashlib.sha256(master_key).hexdigest()
        encryption = StaticKeyEnvelopeEncryption(master_key, key_id=key_id)

        # Encrypt same data twice
        plaintext = json.dumps({"test": "data"})
        encrypted1 = encryption.encrypt(plaintext)
        encrypted2 = encryption.encrypt(plaintext)

        # Both should have same key_id (but different nonces/ciphertext)
        data1 = json.loads(encrypted1)
        data2 = json.loads(encrypted2)
        assert data1["metadata"]["key_id"] == data2["metadata"]["key_id"] == key_id
