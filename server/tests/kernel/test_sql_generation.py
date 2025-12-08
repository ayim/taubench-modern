from unittest.mock import AsyncMock, Mock, patch

import pytest

from agent_platform.core.thread.content.sql_generation import (
    SQLGenerationContent,
    SQLGenerationStatus,
)
from agent_platform.server.kernel.sql_generation import AgentServerSQLGenerationInterface


@pytest.mark.asyncio
async def test_upload_json_to_thread():
    """Test that SQL generation content is uploaded as a JSON file to the thread."""
    # Arrange
    interface = AgentServerSQLGenerationInterface()

    mock_thread = Mock()
    mock_thread.thread_id = "test-thread-id"
    mock_user = Mock()
    mock_user.user_id = "test-user-id"
    mock_kernel = Mock()
    mock_kernel.thread = mock_thread
    mock_kernel.user = mock_user
    interface.attach_kernel(mock_kernel)

    # Capture uploaded content
    uploaded_content = None

    async def capture_upload(**kwargs):
        nonlocal uploaded_content
        upload_file = kwargs["files"][0].file
        uploaded_content = upload_file.file.read()
        return [Mock(file_id="test-file-id")]

    mock_file_manager = AsyncMock()
    mock_file_manager.upload.side_effect = capture_upload

    content = SQLGenerationContent(
        status=SQLGenerationStatus.SUCCESS,
        logical_sql_query="SELECT * FROM customers",
        physical_sql_query="SELECT * FROM public.customers",
        assumptions_used="Assumed customers table in public schema",
    )

    # Act
    with patch(
        "agent_platform.server.file_manager.option.FileManagerService.get_instance",
        return_value=mock_file_manager,
    ):
        await interface._upload_json_to_thread(content, filename="output.json")

    # Assert - verify file manager was called correctly
    mock_file_manager.upload.assert_called_once()
    call_args = mock_file_manager.upload.call_args
    assert call_args.kwargs["owner"] == mock_thread
    assert call_args.kwargs["user_id"] == "test-user-id"
    assert len(call_args.kwargs["files"]) == 1

    upload_payload = call_args.kwargs["files"][0]
    assert upload_payload.file.filename == "output.json"
    assert upload_payload.file.headers.get("content-type") == "application/json"

    # Assert - verify uploaded JSON content
    assert uploaded_content is not None
    actual = SQLGenerationContent.model_validate_json(uploaded_content.decode("utf-8"))
    assert actual.status == SQLGenerationStatus.SUCCESS
    assert actual.logical_sql_query == "SELECT * FROM customers"
    assert actual.physical_sql_query == "SELECT * FROM public.customers"
    assert actual.assumptions_used == "Assumed customers table in public schema"
