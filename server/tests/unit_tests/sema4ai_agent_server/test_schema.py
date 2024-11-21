import pytest
from agent_server_types import NOT_CONFIGURED, AzureGPTConfig
from pydantic import ValidationError

valid_chat_url = "https://example1.openai.azure.com/openai/deployments/my-chat-deployment/chat/completions?api-version=2023-05-15"
valid_embeddings_url = "https://example2.openai.azure.com/openai/deployments/my-embeddings-deployment/embeddings?api-version=2023-10-15"


def test_empty_configuration():
    config = AzureGPTConfig()
    assert config.chat_deployment_name == NOT_CONFIGURED
    assert config.chat_azure_endpoint == NOT_CONFIGURED
    assert config.chat_openai_api_version == NOT_CONFIGURED
    assert config.embeddings_deployment_name == NOT_CONFIGURED
    assert config.embeddings_azure_endpoint == NOT_CONFIGURED
    assert config.embeddings_openai_api_version == NOT_CONFIGURED


def test_valid_urls():
    config = AzureGPTConfig(
        chat_url=valid_chat_url, embeddings_url=valid_embeddings_url
    )
    assert config.chat_deployment_name == "my-chat-deployment"
    assert config.chat_azure_endpoint == "https://example1.openai.azure.com"
    assert config.chat_openai_api_version == "2023-05-15"
    assert config.embeddings_deployment_name == "my-embeddings-deployment"
    assert config.embeddings_azure_endpoint == "https://example2.openai.azure.com"
    assert config.embeddings_openai_api_version == "2023-10-15"


def test_invalid_urls():
    with pytest.raises(ValidationError):
        AzureGPTConfig(chat_url="https://example.com/invalid")

    with pytest.raises(ValidationError):
        AzureGPTConfig(embeddings_url="https://example.com/invalid")

    # Using embeddings url for chat
    with pytest.raises(ValidationError):
        AzureGPTConfig(chat_url=valid_embeddings_url)

    # Missing version
    with pytest.raises(ValidationError):
        AzureGPTConfig(chat_url=valid_chat_url.rsplit("?", 1)[0])


def test_partial_configuration():
    config = AzureGPTConfig(chat_url=valid_chat_url)
    assert config.chat_deployment_name == "my-chat-deployment"
    assert config.embeddings_deployment_name == NOT_CONFIGURED
