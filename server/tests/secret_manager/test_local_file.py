"""Unit tests for LocalFileSecretManager."""

import os
import tempfile
from unittest.mock import patch

import pytest

from agent_platform.core.utils.encryption.aes_gcm import AESGCM2
from agent_platform.server.secret_manager.local_file.local_file import LocalFileSecretManager


class TestLocalFileSecretManager:
    """Test suite for LocalFileSecretManager."""

    def setup_method(self):
        """Set up test environment."""
        self.manager = LocalFileSecretManager()

    def test_init_with_no_env_var(self, monkeypatch):
        """Test initialization when no environment variable is set."""
        monkeypatch.delenv("SEMA4AI_AGENT_SERVER_ENCRYPTION_KEY_FILE", raising=False)
        manager = LocalFileSecretManager()
        assert manager.secret_file is None
        assert len(manager.encryption_key) > 0

    def test_init_with_env_var(self, monkeypatch):
        """Test initialization with environment variable set."""
        test_path = "/path/to/secret"
        monkeypatch.setenv("SEMA4AI_AGENT_SERVER_ENCRYPTION_KEY_FILE", test_path)
        manager = LocalFileSecretManager()
        assert manager.secret_file == test_path
        assert len(manager.encryption_key) > 0

    def test_setup_with_valid_key_file(self, monkeypatch):
        """Test setup with a valid key file containing hex-encoded 32-byte key."""
        # Create a temporary file with a valid 64-char hex key (32 bytes)
        valid_hex_key = "a" * 64  # 64 hex chars = 32 bytes

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write(valid_hex_key)
            temp_path = f.name

        try:
            monkeypatch.setenv("SEMA4AI_AGENT_SERVER_ENCRYPTION_KEY_FILE", temp_path)
            manager = LocalFileSecretManager()
            manager.setup()

            # encryption_key is now stored as bytes (hex decoded)
            expected_bytes = bytes.fromhex(valid_hex_key)
            assert manager.encryption_key == expected_bytes
            assert len(manager.encryption_key) == AESGCM2.VALID_KEY_SIZE
        finally:
            os.unlink(temp_path)

    def test_setup_with_invalid_key_length(self, monkeypatch):
        """Test setup with a key file containing invalid hex key - should fail brutally."""
        # Create a temporary file with an invalid hex key
        invalid_key = "short"

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write(invalid_key)
            temp_path = f.name

        try:
            monkeypatch.setenv("SEMA4AI_AGENT_SERVER_ENCRYPTION_KEY_FILE", temp_path)

            # Should fail brutally when file contains invalid content (during construction)
            with pytest.raises(ValueError, match="Key file contains invalid hex data"):
                LocalFileSecretManager()
        finally:
            os.unlink(temp_path)

    def test_setup_with_wrong_length_hex_key(self, monkeypatch):
        """Test setup with valid hex but wrong byte length - should fail brutally."""
        # Create a temporary file with valid hex but wrong length (16 bytes instead of 32)
        wrong_length_hex = "a" * 32  # 32 hex chars = 16 bytes

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write(wrong_length_hex)
            temp_path = f.name

        try:
            monkeypatch.setenv("SEMA4AI_AGENT_SERVER_ENCRYPTION_KEY_FILE", temp_path)

            # Should fail brutally when hex produces wrong number of bytes (during construction)
            with pytest.raises(ValueError, match="Key must be exactly 32 bytes, got 16 bytes"):
                LocalFileSecretManager()
        finally:
            os.unlink(temp_path)

    def test_setup_with_empty_key_file(self, monkeypatch):
        """Test setup with an empty key file - should use fallback."""
        # Create an empty file
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("")  # empty file
            temp_path = f.name

        try:
            monkeypatch.setenv("SEMA4AI_AGENT_SERVER_ENCRYPTION_KEY_FILE", temp_path)
            manager = LocalFileSecretManager()
            manager.setup()

            # Should use fallback key for empty file
            assert manager.encryption_key == LocalFileSecretManager.FALLBACK_KEY
        finally:
            os.unlink(temp_path)

    def test_setup_with_no_file_configured(self, monkeypatch):
        """Test setup when no file is configured."""
        monkeypatch.delenv("SEMA4AI_AGENT_SERVER_ENCRYPTION_KEY_FILE", raising=False)
        manager = LocalFileSecretManager()
        manager.setup()

        assert manager.encryption_key == LocalFileSecretManager.FALLBACK_KEY

    def test_setup_with_nonexistent_file(self, monkeypatch):
        """Test setup when configured file doesn't exist."""
        nonexistent_path = "/this/path/does/not/exist"

        monkeypatch.setenv("SEMA4AI_AGENT_SERVER_ENCRYPTION_KEY_FILE", nonexistent_path)
        manager = LocalFileSecretManager()
        manager.setup()

        # Should use fallback key
        assert manager.encryption_key == LocalFileSecretManager.FALLBACK_KEY

    def test_setup_with_key_file_with_whitespace(self, monkeypatch):
        """Test setup with a key file that has leading/trailing whitespace."""
        valid_hex_key = "a" * 64  # 64 hex chars = 32 bytes
        key_with_whitespace = f"  \n{valid_hex_key}\n  "

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write(key_with_whitespace)
            temp_path = f.name

        try:
            monkeypatch.setenv("SEMA4AI_AGENT_SERVER_ENCRYPTION_KEY_FILE", temp_path)
            manager = LocalFileSecretManager()
            manager.setup()

            # Should strip whitespace and use the valid hex key, encryption_key is stored as bytes
            expected_bytes = bytes.fromhex(valid_hex_key)
            assert manager.encryption_key == expected_bytes
            assert len(manager.encryption_key) == AESGCM2.VALID_KEY_SIZE
        finally:
            os.unlink(temp_path)

    def test_load_key_from_file_success(self):
        """Test _load_key_from_file with successful file read."""
        test_key = "test_key_content"

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write(test_key)
            temp_path = f.name

        try:
            manager = LocalFileSecretManager()
            manager.secret_file = temp_path

            result = manager._load_key_from_file()
            assert result == test_key
        finally:
            os.unlink(temp_path)

    def test_load_key_from_file_no_file_configured(self):
        """Test _load_key_from_file when no file is configured."""
        manager = LocalFileSecretManager()
        manager.secret_file = None

        result = manager._load_key_from_file()
        assert result is None

    def test_load_key_from_file_empty_path(self):
        """Test _load_key_from_file with empty file path."""
        manager = LocalFileSecretManager()
        manager.secret_file = ""

        result = manager._load_key_from_file()
        assert result is None

    def test_load_key_from_file_file_not_found(self):
        """Test _load_key_from_file when file doesn't exist."""
        manager = LocalFileSecretManager()
        manager.secret_file = "/nonexistent/path"

        result = manager._load_key_from_file()
        assert result is None

    def test_use_fallback_key(self):
        """Test _use_fallback_key method."""
        manager = LocalFileSecretManager()
        manager._use_fallback_key()

        assert manager.encryption_key == LocalFileSecretManager.FALLBACK_KEY

    def test_fallback_key_is_correct_length(self):
        """Test that the fallback key is the correct length."""
        assert len(LocalFileSecretManager.FALLBACK_KEY) == AESGCM2.VALID_KEY_SIZE

    def test_setup_fails_brutally_for_invalid_key(self):
        """Test that setup fails with exception for invalid key in file."""
        invalid_key = "not_hex_data_at_all"
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write(invalid_key)
            temp_path = f.name

        try:
            with patch.dict(os.environ, {"SEMA4AI_AGENT_SERVER_ENCRYPTION_KEY_FILE": temp_path}):
                with pytest.raises(ValueError, match="Key file contains invalid hex data"):
                    LocalFileSecretManager()
        finally:
            os.unlink(temp_path)

    @patch("agent_platform.server.secret_manager.local_file.local_file.logger")
    def test_load_key_logs_warning_for_file_error(self, mock_logger):
        """Test that _load_key_from_file logs warning for file errors."""
        manager = LocalFileSecretManager()
        manager.secret_file = "/nonexistent/path"

        manager._load_key_from_file()

        # Check that warning was logged
        assert mock_logger.warning.called
        warning_call = mock_logger.warning.call_args[0][0]
        assert "Cannot read key file" in warning_call

    def test_store_encrypts_data(self):
        """Test that store() encrypts data using envelope encryption."""
        test_data = '{"key": "value", "number": 42}'

        result = self.manager.store(test_data)

        # Result should be a JSON string containing encrypted data
        assert isinstance(result, str)
        assert result != test_data  # Should be encrypted, not plaintext
        assert len(result) > len(test_data)  # Encrypted data should be larger

        # Should be valid JSON
        import json

        parsed = json.loads(result)
        assert "metadata" in parsed
        assert "encrypted_data_key" in parsed
        assert "encrypted_data" in parsed

    def test_fetch_decrypts_data(self):
        """Test that fetch() decrypts data that was encrypted with store()."""
        test_data = '{"test": "data", "nested": {"value": 123}}'

        # Store the data
        encrypted_reference = self.manager.store(test_data)

        # Fetch it back
        decrypted_data = self.manager.fetch(encrypted_reference)

        # Should match original data
        assert decrypted_data == test_data

    def test_store_fetch_roundtrip_different_data_types(self):
        """Test store/fetch roundtrip with different types of data."""
        test_cases = [
            '{"simple": "string"}',
            '{"number": 42, "float": 3.14, "bool": true, "null": null}',
            '{"array": [1, 2, 3], "nested": {"deep": {"value": "test"}}}',
            "{}",
            "[]",
            '"simple string"',
        ]

        for test_data in test_cases:
            encrypted_reference = self.manager.store(test_data)
            decrypted_data = self.manager.fetch(encrypted_reference)
            assert decrypted_data == test_data, f"Failed for: {test_data}"

    def test_store_uninitialized_manager_raises_error(self, monkeypatch):
        """Test that store() raises error if envelope encryption is not initialized."""
        manager = LocalFileSecretManager()
        # Manually set envelope encryption to None to simulate uninitialized state
        manager._envelope_encryption = None

        with pytest.raises(RuntimeError, match="Secret manager not properly initialized"):
            manager.store("test data")

    def test_fetch_uninitialized_manager_raises_error(self, monkeypatch):
        """Test that fetch() raises error if envelope encryption is not initialized."""
        manager = LocalFileSecretManager()
        # Manually set envelope encryption to None to simulate uninitialized state
        manager._envelope_encryption = None

        with pytest.raises(RuntimeError, match="Secret manager not properly initialized"):
            manager.fetch("test reference")

    def test_different_instances_cannot_decrypt_each_others_data(self):
        """Test that data encrypted by one manager instance cannot be decrypted
        by another with different key."""
        # Create first manager with fallback key
        manager1 = LocalFileSecretManager()
        manager1.setup()

        test_data = '{"key": "value", "number": 42}'
        encrypted_reference = manager1.store(test_data)

        # Create a temporary key file with different key
        temp_key = "a" * 64  # Different 64-character hex string
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".key") as f:
            f.write(temp_key)
            temp_key_path = f.name

        try:
            # Create second manager with different key
            env_var = "SEMA4AI_AGENT_SERVER_ENCRYPTION_KEY_FILE"
            with patch.dict(os.environ, {env_var: temp_key_path}):
                manager2 = LocalFileSecretManager()
                manager2.setup()

                # Attempting to decrypt with different key should fail
                from cryptography.exceptions import InvalidTag

                with pytest.raises(InvalidTag):  # Specific crypto exception
                    manager2.fetch(encrypted_reference)
        finally:
            # Clean up temp file
            try:
                os.unlink(temp_key_path)
            except FileNotFoundError:
                pass
