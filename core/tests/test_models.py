import pytest
from pydantic import ValidationError

from agent_server_types.models import AzureGPTConfig


def test_valid_chat_url():
    valid_url = "https://example.com/openai/deployments/chat_model/chat/completions?api-version=2023-05-15"
    config = AzureGPTConfig(chat_url=valid_url)
    assert config.chat_url == valid_url


def test_invalid_chat_url():
    invalid_url = "https://example.com/openai/deployments/chat_model/wrong_endpoint?api-version=2023-05-15"
    with pytest.raises(ValidationError):
        AzureGPTConfig(chat_url=invalid_url)


def test_valid_embeddings_url():
    valid_url = "https://example.com/openai/deployments/embed_model/embeddings?api-version=2023-05-15"
    config = AzureGPTConfig(embeddings_url=valid_url)
    assert config.embeddings_url == valid_url


def test_invalid_embeddings_url():
    invalid_url = "https://example.com/openai/deployments/embed_model/wrong_endpoint?api-version=2023-05-15"
    with pytest.raises(ValidationError):
        AzureGPTConfig(embeddings_url=invalid_url)
