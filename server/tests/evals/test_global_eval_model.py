import pytest


@pytest.mark.asyncio
async def test_resolve_global_eval_model_missing_config():
    from unittest.mock import AsyncMock

    from agent_platform.server.evals.utils import resolve_global_eval_model
    from agent_platform.server.storage.errors import ConfigNotFoundError

    storage = AsyncMock()
    storage.get_config.side_effect = ConfigNotFoundError()

    result = await resolve_global_eval_model(storage)

    assert result == ("", None)
    storage.get_platform_params.assert_not_called()


@pytest.mark.asyncio
async def test_resolve_global_eval_model_ignores_blank_value():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from agent_platform.server.evals.utils import resolve_global_eval_model

    storage = AsyncMock()
    storage.get_config.return_value = SimpleNamespace(config_value="  ")

    result = await resolve_global_eval_model(storage)

    assert result == ("", None)
    storage.get_platform_params.assert_not_called()


@pytest.mark.asyncio
async def test_resolve_global_eval_model_platform_config():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from agent_platform.server.evals.utils import resolve_global_eval_model

    storage = AsyncMock()
    storage.get_config.return_value = SimpleNamespace(config_value="platform-123")
    storage.get_platform_params.return_value = SimpleNamespace(model_dump=lambda: {"platform_id": "platform-123"})

    result = await resolve_global_eval_model(storage)

    assert result == ("", {"platform_id": "platform-123"})
    storage.get_platform_params.assert_called_once_with("platform-123")


@pytest.mark.asyncio
async def test_resolve_global_eval_model_direct_model_fallback():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from agent_platform.server.evals.utils import resolve_global_eval_model
    from agent_platform.server.storage.errors import InvalidUUIDError

    storage = AsyncMock()
    storage.get_config.return_value = SimpleNamespace(config_value="openai/gpt-4-1")
    storage.get_platform_params.side_effect = InvalidUUIDError()

    result = await resolve_global_eval_model(storage)

    assert result == ("openai/gpt-4-1", None)
    storage.get_platform_params.assert_called_once_with("openai/gpt-4-1")
