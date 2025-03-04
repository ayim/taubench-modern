import base64
import json
from dataclasses import FrozenInstanceError
from unittest.mock import MagicMock, patch

import pytest

from agent_server_types_v2.responses.content.document import ResponseDocumentContent


class TestResponseDocumentContent:
    """Tests for the ResponseDocumentContent class."""

    @pytest.fixture
    def valid_base64_document(self) -> str:
        """Create a valid base64 string for testing."""
        # This is just a simple base64 encoded string, not actual document data
        return base64.b64encode(b"test document data").decode("utf-8")

    def test_init_base64(self, valid_base64_document: str) -> None:
        """Test that ResponseDocumentContent initializes with base64 data."""
        content = ResponseDocumentContent(
            mime_type="application/pdf",
            value=valid_base64_document,
            name="test.pdf",
            sub_type="base64",
        )
        assert content.mime_type == "application/pdf"
        assert content.value == valid_base64_document
        assert content.name == "test.pdf"
        assert content.kind == "document"
        assert content.sub_type == "base64"

    def test_init_url(self) -> None:
        """Test that ResponseDocumentContent initializes with a URL."""
        content = ResponseDocumentContent(
            mime_type="application/pdf",
            value="https://example.com/document.pdf",
            name="document.pdf",
            sub_type="url",
        )
        assert content.mime_type == "application/pdf"
        assert content.value == "https://example.com/document.pdf"
        assert content.name == "document.pdf"
        assert content.kind == "document"
        assert content.sub_type == "url"

    def test_init_raw_bytes(self) -> None:
        """Test that ResponseDocumentContent initializes with raw bytes."""
        content = ResponseDocumentContent(
            mime_type="text/plain",
            value=b"test document data",
            name="test.txt",
            sub_type="raw_bytes",
        )
        assert content.mime_type == "text/plain"
        assert content.value == b"test document data"
        assert content.name == "test.txt"
        assert content.kind == "document"
        assert content.sub_type == "raw_bytes"

    def test_init_uploaded_file(self) -> None:
        """Test that ResponseDocumentContent initializes with an UploadedFile."""
        # Mock UploadedFile
        mock_uploaded_file = MagicMock()

        # Patch the UploadedFile type check
        with patch(
            "agent_server_types_v2.responses.content.document.UploadedFile",
            MagicMock,
        ):
            content = ResponseDocumentContent(
                mime_type="application/pdf",
                value=mock_uploaded_file,
                name="uploaded.pdf",
                sub_type="UploadedFile",
            )
            assert content.mime_type == "application/pdf"
            assert content.value == mock_uploaded_file
            assert content.name == "uploaded.pdf"
            assert content.kind == "document"
            assert content.sub_type == "UploadedFile"

    def test_init_empty_value(self) -> None:
        """Test that ResponseDocumentContent raises an error for empty value."""
        with pytest.raises(ValueError, match="Document value cannot be empty"):
            ResponseDocumentContent(
                mime_type="application/pdf",
                value="",
                name="empty.pdf",
                sub_type="url",
            )

    def test_init_invalid_base64(self) -> None:
        """Test that ResponseDocumentContent raises an error for invalid base64."""
        with pytest.raises(
            ValueError,
            match="Document value is not a valid base64 string",
        ):
            ResponseDocumentContent(
                mime_type="application/pdf",
                value="invalid base64!",
                name="invalid.pdf",
                sub_type="base64",
            )

    def test_init_invalid_raw_bytes(self) -> None:
        """Test that ResponseDocumentContent raises an error for invalid raw bytes."""
        with pytest.raises(ValueError, match="Document value must be bytes"):
            ResponseDocumentContent(
                mime_type="text/plain",
                value="not bytes",
                name="invalid.txt",
                sub_type="raw_bytes",
            )

    def test_init_invalid_url(self) -> None:
        """Test that ResponseDocumentContent raises an error for invalid URL."""
        with pytest.raises(
            ValueError,
            match="Document value must be a string and start with http",
        ):
            ResponseDocumentContent(
                mime_type="application/pdf",
                value="invalid-url",
                name="invalid.pdf",
                sub_type="url",
            )

    def test_init_invalid_uploaded_file(self) -> None:
        """Test that ResponseDocumentContent raises an error for
        invalid UploadedFile."""
        with patch(
            "agent_server_types_v2.responses.content.document.UploadedFile",
            MagicMock,
        ):
            with pytest.raises(
                ValueError,
                match="Document value must be an agent-server UploadedFile",
            ):
                ResponseDocumentContent(
                    mime_type="application/pdf",
                    value="not an uploaded file",
                    name="invalid.pdf",
                    sub_type="UploadedFile",
                )

    def test_model_dump(self, valid_base64_document: str) -> None:
        """Test that model_dump returns a dictionary with the document data."""
        content = ResponseDocumentContent(
            mime_type="application/pdf",
            value=valid_base64_document,
            name="test.pdf",
            sub_type="base64",
        )
        data = content.model_dump()
        assert data["kind"] == "document"
        assert data["mime_type"] == "application/pdf"
        assert data["value"] == valid_base64_document
        assert data["name"] == "test.pdf"
        assert data["sub_type"] == "base64"

    def test_model_dump_json(self, valid_base64_document: str) -> None:
        """Test that model_dump_json returns a JSON string."""
        content = ResponseDocumentContent(
            mime_type="application/pdf",
            value=valid_base64_document,
            name="test.pdf",
            sub_type="base64",
        )
        json_str = content.model_dump_json()
        assert isinstance(json_str, str)
        data = json.loads(json_str)
        assert data["kind"] == "document"
        assert data["mime_type"] == "application/pdf"
        assert data["value"] == valid_base64_document
        assert data["name"] == "test.pdf"
        assert data["sub_type"] == "base64"

    def test_model_validate(self, valid_base64_document: str) -> None:
        """Test that model_validate creates a ResponseDocumentContent
        from a dictionary."""
        data = {
            "kind": "document",  # This should be removed by model_validate
            "mime_type": "application/pdf",
            "value": valid_base64_document,
            "name": "test.pdf",
            "sub_type": "base64",
        }
        content = ResponseDocumentContent.model_validate(data)
        assert isinstance(content, ResponseDocumentContent)
        assert content.kind == "document"
        assert content.mime_type == "application/pdf"
        assert content.value == valid_base64_document
        assert content.name == "test.pdf"
        assert content.sub_type == "base64"

    def test_immutability(self, valid_base64_document: str) -> None:
        """Test that ResponseDocumentContent is immutable."""
        content = ResponseDocumentContent(
            mime_type="application/pdf",
            value=valid_base64_document,
            name="test.pdf",
            sub_type="base64",
        )
        with pytest.raises(FrozenInstanceError):
            # This should raise an exception because ResponseDocumentContent is frozen
            content.mime_type = "text/plain"  # type: ignore
