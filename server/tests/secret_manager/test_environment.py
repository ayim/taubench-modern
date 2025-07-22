"""Unit tests for EnvironmentSecretManager."""

from unittest.mock import patch

import pytest

from agent_platform.core.utils.encryption.aes_gcm import AESGCM2
from agent_platform.server.secret_manager.environment.environment import EnvironmentSecretManager


class TestEnvironmentSecretManager:
    """Test suite for EnvironmentSecretManager."""

    def test_init_with_no_env_var(self, monkeypatch):
        """Test initialization when no environment variable is set."""
        monkeypatch.delenv("SEMA4AI_AGENT_SERVER_ENCRYPTION_KEY", raising=False)
        manager = EnvironmentSecretManager()
        assert len(manager.encryption_key) > 0
        # Should use fallback key
        assert manager.encryption_key == EnvironmentSecretManager.FALLBACK_KEY

    def test_init_with_empty_env_var(self, monkeypatch):
        """Test initialization with empty environment variable."""
        monkeypatch.setenv("SEMA4AI_AGENT_SERVER_ENCRYPTION_KEY", "")
        manager = EnvironmentSecretManager()
        assert len(manager.encryption_key) > 0
        # Should use fallback key
        assert manager.encryption_key == EnvironmentSecretManager.FALLBACK_KEY

    def test_setup_with_valid_key(self, monkeypatch):
        """Test setup with a valid hex-encoded 32-byte key."""
        # Valid 64-char hex key (32 bytes)
        valid_hex_key = "a" * 64  # 64 hex chars = 32 bytes

        monkeypatch.setenv("SEMA4AI_AGENT_SERVER_ENCRYPTION_KEY", valid_hex_key)
        manager = EnvironmentSecretManager()

        # encryption_key is now stored as bytes (hex decoded)
        expected_bytes = bytes.fromhex(valid_hex_key)
        assert manager.encryption_key == expected_bytes
        assert len(manager.encryption_key) == AESGCM2.VALID_KEY_SIZE

    def test_setup_with_invalid_key_length(self, monkeypatch):
        """Test setup with invalid key length."""
        # Too short key (30 hex chars = 15 bytes)
        invalid_hex_key = "a" * 30

        monkeypatch.setenv("SEMA4AI_AGENT_SERVER_ENCRYPTION_KEY", invalid_hex_key)

        with pytest.raises(ValueError, match="Key must be exactly 32 bytes"):
            EnvironmentSecretManager()

    def test_setup_with_wrong_length_hex_key(self, monkeypatch):
        """Test setup with wrong length hex key."""
        # Too long key (128 hex chars = 64 bytes)
        invalid_hex_key = "a" * 128

        monkeypatch.setenv("SEMA4AI_AGENT_SERVER_ENCRYPTION_KEY", invalid_hex_key)

        with pytest.raises(ValueError, match="Key must be exactly 32 bytes"):
            EnvironmentSecretManager()

    def test_setup_with_empty_key(self, monkeypatch):
        """Test setup with empty key string."""
        monkeypatch.setenv("SEMA4AI_AGENT_SERVER_ENCRYPTION_KEY", "")
        manager = EnvironmentSecretManager()
        # Should use fallback key
        assert manager.encryption_key == EnvironmentSecretManager.FALLBACK_KEY

    def test_setup_with_key_with_whitespace(self, monkeypatch):
        """Test setup with key containing whitespace."""
        valid_hex_key = "a" * 64
        key_with_whitespace = f"  {valid_hex_key}  "

        monkeypatch.setenv("SEMA4AI_AGENT_SERVER_ENCRYPTION_KEY", key_with_whitespace)
        manager = EnvironmentSecretManager()

        # Should strip whitespace and work correctly
        expected_bytes = bytes.fromhex(valid_hex_key)
        assert manager.encryption_key == expected_bytes

    def test_load_key_from_environment_success(self, monkeypatch):
        """Test loading key from environment variable successfully."""
        test_key = "abcd1234" * 8  # 64 hex chars
        monkeypatch.setenv("SEMA4AI_AGENT_SERVER_ENCRYPTION_KEY", test_key)

        manager = EnvironmentSecretManager()
        result = manager._load_key_from_environment()

        assert result == test_key

    def test_load_key_from_environment_not_set(self, monkeypatch):
        """Test loading key when environment variable is not set."""
        monkeypatch.delenv("SEMA4AI_AGENT_SERVER_ENCRYPTION_KEY", raising=False)

        manager = EnvironmentSecretManager()
        result = manager._load_key_from_environment()

        assert result is None

    def test_use_fallback_key(self):
        """Test using fallback key."""
        manager = EnvironmentSecretManager()
        manager._use_fallback_key()

        assert manager.encryption_key == EnvironmentSecretManager.FALLBACK_KEY
        assert manager._envelope_encryption is not None

    def test_fallback_key_is_correct_length(self):
        """Test that fallback key is the correct length."""
        fallback_key = EnvironmentSecretManager.FALLBACK_KEY
        assert len(fallback_key) == AESGCM2.VALID_KEY_SIZE

    def test_setup_fails_brutally_for_invalid_key(self, monkeypatch):
        """Test that setup fails with descriptive error for invalid hex."""
        invalid_key = "not_hex_at_all_this_is_invalid!"
        monkeypatch.setenv("SEMA4AI_AGENT_SERVER_ENCRYPTION_KEY", invalid_key)

        expected_msg = "SEMA4AI_AGENT_SERVER_ENCRYPTION_KEY contains invalid hex data"
        with pytest.raises(ValueError, match=expected_msg):
            EnvironmentSecretManager()

    @patch("agent_platform.server.secret_manager.environment.environment.logger")
    def test_load_key_logs_warning_for_missing_env_var(self, mock_logger, monkeypatch):
        """Test that missing environment variable logs a warning."""
        monkeypatch.delenv("SEMA4AI_AGENT_SERVER_ENCRYPTION_KEY", raising=False)

        manager = EnvironmentSecretManager()
        manager._load_key_from_environment()

        # Check that warning was logged
        assert mock_logger.warning.called
        warning_call = mock_logger.warning.call_args[0][0]
        assert "SEMA4AI_AGENT_SERVER_ENCRYPTION_KEY environment variable not set" in warning_call

    def test_store_encrypts_data(self, monkeypatch):
        """Test that store method encrypts data."""
        valid_hex_key = "a" * 64
        monkeypatch.setenv("SEMA4AI_AGENT_SERVER_ENCRYPTION_KEY", valid_hex_key)

        manager = EnvironmentSecretManager()
        test_data = "secret_data_to_encrypt"

        encrypted = manager.store(test_data)

        assert encrypted != test_data
        assert isinstance(encrypted, str)
        assert len(encrypted) > 0

    def test_fetch_decrypts_data(self, monkeypatch):
        """Test that fetch method decrypts data."""
        valid_hex_key = "a" * 64
        monkeypatch.setenv("SEMA4AI_AGENT_SERVER_ENCRYPTION_KEY", valid_hex_key)

        manager = EnvironmentSecretManager()
        test_data = "secret_data_to_encrypt"

        encrypted = manager.store(test_data)
        decrypted = manager.fetch(encrypted)

        assert decrypted == test_data

    def test_store_fetch_roundtrip_different_data_types(self, monkeypatch):
        """Test store/fetch roundtrip with different data types."""
        valid_hex_key = "a" * 64
        monkeypatch.setenv("SEMA4AI_AGENT_SERVER_ENCRYPTION_KEY", valid_hex_key)

        manager = EnvironmentSecretManager()

        test_cases = [
            "simple_string",
            "string with spaces and special chars: !@#$%^&*()",
            '{"key": "value", "number": 123}',  # JSON-like string
            "single_char",  # minimal non-empty string
            "a" * 1000,  # long string
        ]

        for test_data in test_cases:
            encrypted = manager.store(test_data)
            decrypted = manager.fetch(encrypted)
            assert decrypted == test_data, f"Failed for test case: {test_data}"

    def test_store_uninitialized_manager_raises_error(self, monkeypatch):
        """Test that store raises error when manager is not initialized."""
        manager = EnvironmentSecretManager()
        manager._envelope_encryption = None

        with pytest.raises(RuntimeError, match="Secret manager not properly initialized"):
            manager.store("test_data")

    def test_fetch_uninitialized_manager_raises_error(self, monkeypatch):
        """Test that fetch raises error when manager is not initialized."""
        manager = EnvironmentSecretManager()
        manager._envelope_encryption = None

        with pytest.raises(RuntimeError, match="Secret manager not properly initialized"):
            manager.fetch("test_data")

    def test_different_instances_cannot_decrypt_each_others_data(self, monkeypatch):
        """Test that instances with different keys cannot decrypt each other's data."""
        key1 = "a" * 64
        key2 = "b" * 64

        # First manager with key1
        monkeypatch.setenv("SEMA4AI_AGENT_SERVER_ENCRYPTION_KEY", key1)
        manager1 = EnvironmentSecretManager()

        test_data = "secret_data"
        encrypted_by_manager1 = manager1.store(test_data)

        # Second manager with key2
        monkeypatch.setenv("SEMA4AI_AGENT_SERVER_ENCRYPTION_KEY", key2)
        manager2 = EnvironmentSecretManager()

        # Manager2 should not be able to decrypt manager1's data
        with pytest.raises(Exception, match=".*"):  # Should raise decryption error
            manager2.fetch(encrypted_by_manager1)

    def test_inheritance(self):
        """Test that EnvironmentSecretManager inherits from BaseSecretManager."""
        from agent_platform.server.secret_manager.base import BaseSecretManager

        manager = EnvironmentSecretManager()
        assert isinstance(manager, BaseSecretManager)

    def test_abstract_methods_implementation(self):
        """Test that EnvironmentSecretManager implements all abstract methods."""
        manager = EnvironmentSecretManager()

        # Test that store and fetch methods exist and are callable
        assert hasattr(manager, "store")
        assert callable(manager.store)
        assert hasattr(manager, "fetch")
        assert callable(manager.fetch)

    def test_error_message_consistency(self, monkeypatch):
        """Test that error messages are consistent and helpful."""
        invalid_key = "invalid_hex_123xyz"
        monkeypatch.setenv("SEMA4AI_AGENT_SERVER_ENCRYPTION_KEY", invalid_key)

        expected_msg = "SEMA4AI_AGENT_SERVER_ENCRYPTION_KEY"
        with pytest.raises(ValueError, match=expected_msg):
            EnvironmentSecretManager()
