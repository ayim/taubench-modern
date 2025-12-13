"""Tests for the AgentServerDocumentsInterface."""

from typing import Literal
from unittest.mock import AsyncMock, Mock

import pytest


class _DefaultDocumentArchState:
    """Mock state for testing."""

    documents_tools_state: Literal["enabled", ""] = ""


@pytest.mark.asyncio
async def test_documents_interface_initialization():
    """Test that AgentServerDocumentsInterface can be initialized."""
    from agent_platform.server.kernel.documents import AgentServerDocumentsInterface

    interface = AgentServerDocumentsInterface()

    assert interface is not None
    assert interface.documents_summary == "You have no documents to work with."
    assert interface.documents_system_prompt == ""


@pytest.mark.asyncio
async def test_documents_interface_get_tools():
    """Test getting document tools."""
    from agent_platform.server.kernel.documents import AgentServerDocumentsInterface

    interface = AgentServerDocumentsInterface()
    tools = interface.get_document_tools()

    assert isinstance(tools, tuple)
    # Initially returns empty tuple before initialization
    assert len(tools) == 0


@pytest.mark.asyncio
async def test_documents_in_context_filters_by_mime_type():
    """Test that documents_in_context filters files by supported MIME types."""
    from agent_platform.server.kernel.documents import AgentServerDocumentsInterface

    interface = AgentServerDocumentsInterface()

    # Create mock kernel
    mock_kernel = Mock()
    mock_kernel.thread_state = Mock()
    mock_kernel.thread_state.thread_id = "thread-123"
    mock_kernel.user = Mock()
    mock_kernel.user.user_id = "user-456"
    interface.attach_kernel(mock_kernel)

    # Create mock storage with various file types
    mock_storage = AsyncMock()

    # Create mock files - some should be filtered, some should pass
    mock_pdf = Mock()
    mock_pdf.file_ref = "document.pdf"
    mock_pdf.mime_type = "application/pdf"

    mock_image = Mock()
    mock_image.file_ref = "chart.png"
    mock_image.mime_type = "image/png"

    mock_json = Mock()
    mock_json.file_ref = "data.json"
    mock_json.mime_type = "application/json"  # Should be filtered out

    mock_video = Mock()
    mock_video.file_ref = "presentation.mp4"
    mock_video.mime_type = "video/mp4"  # Should be filtered out

    mock_storage.get_thread_files = AsyncMock(return_value=[mock_pdf, mock_image, mock_json, mock_video])

    documents = await interface.documents_in_context(mock_storage)

    # Only PDF and PNG should be included
    assert len(documents) == 2
    assert mock_pdf in documents
    assert mock_image in documents
    assert mock_json not in documents
    assert mock_video not in documents


@pytest.mark.asyncio
async def test_is_enabled_requires_reducto_integration():
    """Test that is_enabled checks for Reducto integration."""
    from agent_platform.server.kernel.documents import AgentServerDocumentsInterface

    interface = AgentServerDocumentsInterface()

    # Create mock kernel without document_intelligence setting (to allow internal processing)
    mock_kernel = Mock()
    mock_kernel.agent = Mock()
    mock_kernel.agent.extra = {"agent_settings": {}}

    # Mock storage that doesn't have Reducto
    mock_storage = AsyncMock()
    from agent_platform.server.storage.errors import IntegrationNotFoundError

    mock_storage.get_integration_by_kind = AsyncMock(side_effect=IntegrationNotFoundError("reducto", by="kind"))
    mock_kernel.storage = mock_storage

    interface.attach_kernel(mock_kernel)

    # Should be disabled without Reducto
    is_enabled = await interface.is_enabled()
    assert is_enabled is False


@pytest.mark.asyncio
async def test_is_enabled_disabled_when_external_system_configured():
    """Test that is_enabled returns False when external document intelligence is configured."""
    from agent_platform.server.kernel.documents import AgentServerDocumentsInterface

    interface = AgentServerDocumentsInterface()

    # Create mock kernel with external document_intelligence setting
    mock_kernel = Mock()
    mock_kernel.agent = Mock()
    mock_kernel.agent.extra = {"document_intelligence": "v2"}

    interface.attach_kernel(mock_kernel)

    # Should be disabled when using external system
    is_enabled = await interface.is_enabled()
    assert is_enabled is False


@pytest.mark.asyncio
async def test_step_initialize_creates_tools_when_documents_present():
    """Test that step_initialize creates tools when documents are present."""
    from agent_platform.server.kernel.documents import AgentServerDocumentsInterface

    interface = AgentServerDocumentsInterface()

    # Create mock kernel
    mock_kernel = Mock()
    mock_kernel.thread_state = Mock()
    mock_kernel.thread_state.thread_id = "thread-123"
    mock_kernel.user = Mock()
    mock_kernel.user.user_id = "user-456"
    mock_kernel.agent = Mock()
    # Don't set document_intelligence - leave it empty to enable internal processing
    mock_kernel.agent.extra = {"agent_settings": {}}

    # Mock storage with Reducto integration
    mock_storage = AsyncMock()
    mock_integration = Mock()
    mock_integration.id = "integration-123"
    mock_storage.get_integration_by_kind = AsyncMock(return_value=mock_integration)

    # Mock document file
    mock_doc = Mock()
    mock_doc.file_ref = "test.pdf"
    mock_doc.file_id = "file-123"
    mock_doc.mime_type = "application/pdf"
    mock_doc.file_size_raw = 1024

    mock_storage.get_thread_files = AsyncMock(return_value=[mock_doc])
    mock_kernel.storage = mock_storage

    interface.attach_kernel(mock_kernel)

    state = _DefaultDocumentArchState()

    await interface.step_initialize(state=state, storage=mock_storage)

    # Should have created tools
    tools = interface.get_document_tools()
    assert len(tools) > 0
    assert state.documents_tools_state == "enabled"

    # Verify the parse_document tool exists
    tool_names = [tool.name for tool in tools]
    assert "parse_document" in tool_names


@pytest.mark.asyncio
async def test_step_initialize_no_tools_when_no_documents():
    """Test that step_initialize doesn't create tools when no documents are present."""
    from agent_platform.server.kernel.documents import AgentServerDocumentsInterface

    interface = AgentServerDocumentsInterface()

    # Create mock kernel
    mock_kernel = Mock()
    mock_kernel.thread_state = Mock()
    mock_kernel.thread_state.thread_id = "thread-123"
    mock_kernel.user = Mock()
    mock_kernel.user.user_id = "user-456"
    mock_kernel.agent = Mock()
    # Don't set document_intelligence - leave it empty to enable internal processing
    mock_kernel.agent.extra = {"agent_settings": {}}

    # Mock storage with Reducto integration but no documents
    mock_storage = AsyncMock()
    mock_integration = Mock()
    mock_integration.id = "integration-123"
    mock_storage.get_integration_by_kind = AsyncMock(return_value=mock_integration)
    mock_storage.get_thread_files = AsyncMock(return_value=[])
    mock_kernel.storage = mock_storage

    interface.attach_kernel(mock_kernel)

    state = _DefaultDocumentArchState()

    await interface.step_initialize(state=state, storage=mock_storage)

    # Should not have created tools
    tools = interface.get_document_tools()
    assert len(tools) == 0
    assert state.documents_tools_state == ""


@pytest.mark.asyncio
async def test_documents_summary_formats_file_size():
    """Test that documents_summary formats file sizes in a human-readable way."""
    from agent_platform.server.kernel.documents import AgentServerDocumentsInterface

    interface = AgentServerDocumentsInterface()

    # Create mock kernel
    mock_kernel = Mock()
    mock_kernel.thread_state = Mock()
    mock_kernel.thread_state.thread_id = "thread-123"
    mock_kernel.user = Mock()
    mock_kernel.user.user_id = "user-456"
    interface.attach_kernel(mock_kernel)

    # Create mock storage
    mock_storage = AsyncMock()

    # Create mock documents with different file sizes
    mock_doc_kb = Mock()
    mock_doc_kb.file_ref = "small.pdf"
    mock_doc_kb.file_id = "file-1"
    mock_doc_kb.mime_type = "application/pdf"
    mock_doc_kb.file_size_raw = 2048  # 2 KB

    mock_doc_mb = Mock()
    mock_doc_mb.file_ref = "large.pdf"
    mock_doc_mb.file_id = "file-2"
    mock_doc_mb.mime_type = "application/pdf"
    mock_doc_mb.file_size_raw = 1572864  # 1.5 MB

    mock_doc_kb_decimal = Mock()
    mock_doc_kb_decimal.file_ref = "medium.pdf"
    mock_doc_kb_decimal.file_id = "file-3"
    mock_doc_kb_decimal.mime_type = "application/pdf"
    mock_doc_kb_decimal.file_size_raw = 512  # 0.5 KB

    mock_storage.get_thread_files = AsyncMock(return_value=[mock_doc_kb, mock_doc_mb, mock_doc_kb_decimal])

    # Set the documents directly to test the summary
    interface._documents = [mock_doc_kb, mock_doc_mb, mock_doc_kb_decimal]

    summary = interface.documents_summary

    # Verify KB formatting
    assert "2.0 KB" in summary
    # Verify MB formatting
    assert "1.5 MB" in summary
    # Verify decimal KB formatting
    assert "0.5 KB" in summary
    # Should NOT contain raw bytes
    assert "bytes" not in summary
