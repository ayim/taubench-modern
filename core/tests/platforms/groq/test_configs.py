"""Tests for Groq platform configuration integration."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from agent_platform.core.platforms.configs import PlatformModelConfigs
from agent_platform.core.platforms.groq.client import GroqClient
from agent_platform.core.platforms.groq.parameters import GroqPlatformParameters
from agent_platform.core.utils import SecretString


def test_platform_model_configs_contains_groq_models() -> None:
    models = PlatformModelConfigs.models_to_platform_specific_model_ids
    assert "groq/openai/gpt-oss-120b" in models
    assert models["groq/openai/gpt-oss-120b"] == "openai/gpt-oss-120b"


@pytest.mark.asyncio
async def test_get_available_models_uses_global_config() -> None:
    parameters = GroqPlatformParameters(groq_api_key=SecretString("key"))
    with patch("openai.AsyncOpenAI") as mock_async_openai:
        mock_model_list = SimpleNamespace(
            data=[SimpleNamespace(id="openai/gpt-oss-120b")],
        )
        mock_models = SimpleNamespace(
            list=AsyncMock(return_value=mock_model_list),
        )
        mock_async_openai.return_value.models = mock_models
        client = GroqClient(parameters=parameters)
    available = await client.get_available_models()
    assert "openai" in available
    assert "openai/gpt-oss-120b" in available["openai"]
