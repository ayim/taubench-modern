"""Tests for documents functionality."""

import pytest


@pytest.mark.asyncio
async def test_documents_summary_empty():
    """Test documents summary when there are no documents."""
    from agent_platform.server.kernel.documents import AgentServerDocumentsInterface

    interface = AgentServerDocumentsInterface()

    assert interface.documents_summary == "You have no documents to work with."


@pytest.mark.asyncio
async def test_documents_summary_with_documents():
    """Test documents summary with uploaded documents."""
    from unittest.mock import Mock

    from agent_platform.server.kernel.documents import AgentServerDocumentsInterface

    interface = AgentServerDocumentsInterface()

    # Create mock documents
    mock_doc1 = Mock()
    mock_doc1.file_ref = "test.pdf"
    mock_doc1.file_id = "file-123"
    mock_doc1.mime_type = "application/pdf"
    mock_doc1.file_size_raw = 1024

    mock_doc2 = Mock()
    mock_doc2.file_ref = "report.docx"
    mock_doc2.file_id = "file-456"
    mock_doc2.mime_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    mock_doc2.file_size_raw = None

    interface._documents = [mock_doc1, mock_doc2]

    summary = interface.documents_summary

    assert "### Document: test.pdf" in summary
    assert "MIME Type: application/pdf" in summary
    assert "Size: 1.0 KB" in summary

    assert "### Document: report.docx" in summary
    assert "MIME Type: application/vnd.openxmlformats-officedocument.wordprocessingml.document" in summary
    # file-456 has no size, so it should not appear
    assert "Size:" not in summary.split("### Document: report.docx")[1].split("### Document:")[0]


@pytest.mark.asyncio
async def test_documents_system_prompt_empty():
    """Test documents system prompt when there are no documents."""
    from agent_platform.server.kernel.documents import AgentServerDocumentsInterface

    interface = AgentServerDocumentsInterface()

    assert interface.documents_system_prompt == ""


@pytest.mark.asyncio
async def test_documents_system_prompt_with_documents():
    """Test documents system prompt with uploaded documents."""
    from unittest.mock import Mock

    from agent_platform.server.kernel.documents import AgentServerDocumentsInterface

    interface = AgentServerDocumentsInterface()

    # Create a mock document
    mock_doc = Mock()
    mock_doc.file_ref = "invoice.pdf"
    mock_doc.file_id = "file-789"
    mock_doc.mime_type = "application/pdf"
    mock_doc.file_size_raw = 2048

    interface._documents = [mock_doc]

    prompt = interface.documents_system_prompt

    assert "## Documents Available" in prompt
    assert "parse_document" in prompt
    assert "invoice.pdf" in prompt
    assert "create_data_frame_from_json" in prompt


@pytest.mark.asyncio
async def test_get_document_tools_empty():
    """Test getting document tools when no documents are loaded."""
    from agent_platform.server.kernel.documents import AgentServerDocumentsInterface

    interface = AgentServerDocumentsInterface()

    tools = interface.get_document_tools()

    assert isinstance(tools, tuple)
    assert len(tools) == 0
