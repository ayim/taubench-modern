import pytest

from agent_platform.core.thread.content.attachment import ThreadAttachmentContent


class TestThreadAttachmentContent:
    def test_create_attachment_with_uri_only(self):
        """Ensures that providing only a URI and no base64_data
        treats the attachment as a handle."""
        content = ThreadAttachmentContent(
            name="my-image",
            mime_type="image/png",
            uri="http://example.com/image.png",
        )
        assert content.kind == "attachment"
        assert content.is_handle is True
        assert content.uri == "http://example.com/image.png"
        assert content.base64_data is None

    def test_create_attachment_with_base64_data_only(self):
        """Ensures that providing base64_data (and no URI) treats
        the attachment as an embedded file."""
        base64_str = "iVBORw0KGgoAAAANSUhEUgAAAAUA"  # truncated
        content = ThreadAttachmentContent(
            name="embedded-file",
            mime_type="application/pdf",
            base64_data=base64_str,
        )
        assert content.kind == "attachment"
        assert content.is_handle is False
        assert content.base64_data == base64_str
        assert content.uri is None

    def test_empty_mime_type_raises(self):
        with pytest.raises(ValueError, match="MIME type cannot be empty"):
            ThreadAttachmentContent(
                name="broken-file",
                mime_type="",
                uri="http://example.com/file.dat",
            )

    def test_invalid_base64_data_raises(self):
        with pytest.raises(ValueError, match="Base64 data is not valid"):
            ThreadAttachmentContent(
                name="broken-base64",
                mime_type="application/octet-stream",
                base64_data="Invalid@@@Data###",
            )

    def test_both_uri_and_base64_data_provided(self):
        """
        Technically not disallowed by your class design, but this test ensures
        we handle the scenario as a handle with base64_data also present
        (which might be an edge case).
        """
        # The code won't explicitly raise in this scenario,
        # but let's confirm it interprets as a handle.
        content = ThreadAttachmentContent(
            name="mixed",
            mime_type="image/jpeg",
            uri="http://example.com/file.jpg",
            base64_data="iVBORw0KGgoAAAANSUhEUgAAAAUA",
        )
        assert content.is_handle is True
        # It's up to you if you want to raise in this scenario or allow it.

    def test_as_text_content_generates_correct_xml(self):
        content = ThreadAttachmentContent(
            name="doc",
            mime_type="application/pdf",
            description="A PDF doc",
            uri="http://example.com/doc.pdf",
        )
        text_obj = content.as_text_content()
        assert "application/pdf" in text_obj
        assert "doc" in text_obj
        assert "description=\"A PDF doc\"" in text_obj
        assert "uri=\"http://example.com/doc.pdf\"" in text_obj
