"""Unit tests for _DocumentTools.extract_document method."""

import json
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest


def _create_document_tools(
    storage: Mock | None = None,
    kernel: Mock | None = None,
    user: Mock | None = None,
    tid: str = "test-thread-id",
):
    """Helper to create a _DocumentTools instance with mocked dependencies."""
    from agent_platform.server.kernel.documents import _DocumentTools

    if user is None:
        user = MagicMock()
        user.user_id = "test-user-id"

    if kernel is None:
        kernel = MagicMock()
        kernel.thread = MagicMock()
        kernel.thread.thread_id = tid
        kernel.agent = MagicMock()
        kernel.agent.agent_id = "test-agent-id"
        kernel.ctx = MagicMock()

    if storage is None:
        storage = AsyncMock()

    return _DocumentTools(
        user=user,
        tid=tid,
        storage=storage,
        kernel=kernel,
    )


@pytest.mark.asyncio
async def test_extract_document_empty_schema_returns_error():
    """Test that empty extraction_schema returns an error."""
    tools = _create_document_tools()

    result = await tools.extract_document(
        extraction_schema="",
        file_name="test.pdf",
    )

    assert result["error_code"] == "invalid_input"
    assert "extraction_schema is required" in result["message"]


@pytest.mark.asyncio
async def test_extract_document_invalid_reducto_settings_returns_error():
    """Test that invalid Reducto settings returns an error."""
    storage = AsyncMock()
    mock_integration = MagicMock()
    mock_integration.settings = "not_reducto_settings"  # Wrong type
    storage.get_integration_by_kind = AsyncMock(return_value=mock_integration)

    tools = _create_document_tools(storage=storage)

    schema = json.dumps({"type": "object", "properties": {"name": {"type": "string"}}})
    result = await tools.extract_document(
        extraction_schema=schema,
        file_name="test.pdf",
    )

    assert result["error_code"] == "invalid_reducto_config"
    assert "invalid settings" in result["message"]


@pytest.mark.asyncio
async def test_extract_document():
    """Test extraction with start_page and end_page parameters."""
    from agent_platform.core.integrations.settings.reducto import ReductoSettings
    from agent_platform.core.utils import SecretString

    storage = AsyncMock()
    mock_integration = MagicMock()
    mock_integration.settings = ReductoSettings(endpoint="https://api.reducto.ai", api_key=SecretString("test-api-key"))
    storage.get_integration_by_kind = AsyncMock(return_value=mock_integration)

    tools = _create_document_tools(storage=storage)

    mock_doc = MagicMock()
    mock_extract_result = MagicMock()
    mock_extract_result.model_dump.return_value = {"data": "extracted"}

    with (
        patch("agent_platform.server.file_manager.FileManagerService") as mock_file_manager_class,
        patch("agent_platform.server.document_intelligence.DirectKernelTransport") as mock_transport_class,
        patch("sema4ai_docint.build_di_service") as mock_build_di,
    ):
        mock_file_manager_class.get_instance.return_value = MagicMock()
        mock_transport_class.return_value = MagicMock()

        mock_di_service = MagicMock()
        mock_di_service.document_v2 = MagicMock()
        mock_di_service.document_v2.new_document = AsyncMock(return_value=mock_doc)
        mock_di_service.document_v2.extract_document = AsyncMock(return_value=mock_extract_result)
        # Mock async context manager protocol
        mock_di_service.__aenter__ = AsyncMock(return_value=mock_di_service)
        mock_di_service.__aexit__ = AsyncMock(return_value=None)
        mock_build_di.return_value = mock_di_service

        schema = json.dumps({"type": "object", "properties": {"data": {"type": "string"}}})

        result = await tools.extract_document(
            extraction_schema=schema,
            file_name="document.pdf",
            start_page=1,
            end_page=5,
        )

        assert result == {"data": "extracted"}
        call_kwargs = mock_di_service.document_v2.extract_document.call_args[1]
        assert call_kwargs["start_page"] == 1
        assert call_kwargs["end_page"] == 5
