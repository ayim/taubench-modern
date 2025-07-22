"""Shared fixtures for secret manager tests."""

import os
import tempfile

import pytest

from agent_platform.core.utils.encryption.aes_gcm import AESGCM2


@pytest.fixture
def valid_key():
    """Provide a valid 32-byte encryption key."""
    return "a" * AESGCM2.VALID_KEY_SIZE


@pytest.fixture
def invalid_key():
    """Provide an invalid (too short) encryption key."""
    return "short_key"


@pytest.fixture
def temp_key_file(valid_key):
    """Create a temporary file with a valid encryption key."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
        f.write(valid_key)
        temp_path = f.name

    yield temp_path

    # Cleanup
    try:
        os.unlink(temp_path)
    except FileNotFoundError:
        pass  # File already deleted


@pytest.fixture
def temp_invalid_key_file(invalid_key):
    """Create a temporary file with an invalid encryption key."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
        f.write(invalid_key)
        temp_path = f.name

    yield temp_path

    # Cleanup
    try:
        os.unlink(temp_path)
    except FileNotFoundError:
        pass


@pytest.fixture
def clean_env(monkeypatch):
    """Provide a clean environment without secret manager env vars."""
    monkeypatch.delenv("SEMA4AI_AGENT_SERVER_ENCRYPTION_KEY_SOURCE", raising=False)
    monkeypatch.delenv("SEMA4AI_AGENT_SERVER_ENCRYPTION_KEY_FILE", raising=False)


@pytest.fixture
def file_source_env(monkeypatch):
    """Set environment to use file source."""
    monkeypatch.setenv("SEMA4AI_AGENT_SERVER_ENCRYPTION_KEY_SOURCE", "file")


@pytest.fixture
def aws_source_env(monkeypatch):
    """Set environment to use AWS source."""
    monkeypatch.setenv("SEMA4AI_AGENT_SERVER_ENCRYPTION_KEY_SOURCE", "aws")


@pytest.fixture
def file_env_with_key_file(temp_key_file, monkeypatch):
    """Set environment to use file source with a specific key file."""
    monkeypatch.setenv("SEMA4AI_AGENT_SERVER_ENCRYPTION_KEY_SOURCE", "file")
    monkeypatch.setenv("SEMA4AI_AGENT_SERVER_ENCRYPTION_KEY_FILE", temp_key_file)
    return temp_key_file
