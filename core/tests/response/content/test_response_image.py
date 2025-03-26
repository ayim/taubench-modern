import base64
import json
from dataclasses import FrozenInstanceError
from unittest.mock import MagicMock, patch

import pytest

from agent_platform_core.responses.content.image import ResponseImageContent


class TestResponseImageContent:
    """Tests for the ResponseImageContent class."""

    @pytest.fixture
    def valid_base64_image(self) -> str:
        """Create a valid base64 string for testing."""
        # This is just a simple base64 encoded string, not actual image data
        return base64.b64encode(b"test image data").decode("utf-8")

    def test_init_url(self) -> None:
        """Test that ResponseImageContent initializes with a URL."""
        content = ResponseImageContent(
            mime_type="image/jpeg",
            value="https://example.com/image.jpg",
            sub_type="url",
        )
        assert content.mime_type == "image/jpeg"
        assert content.value == "https://example.com/image.jpg"
        assert content.kind == "image"
        assert content.sub_type == "url"
        assert content.detail == "high_res"

    def test_init_base64(self, valid_base64_image: str) -> None:
        """Test that ResponseImageContent initializes with base64 data."""
        content = ResponseImageContent(
            mime_type="image/png",
            value=valid_base64_image,
            sub_type="base64",
        )
        assert content.mime_type == "image/png"
        assert content.value == valid_base64_image
        assert content.kind == "image"
        assert content.sub_type == "base64"
        assert content.detail == "high_res"

    def test_init_raw_bytes(self) -> None:
        """Test that ResponseImageContent initializes with raw bytes."""
        content = ResponseImageContent(
            mime_type="image/gif",
            value=b"test image data",
            sub_type="raw_bytes",
        )
        assert content.mime_type == "image/gif"
        assert content.value == b"test image data"
        assert content.kind == "image"
        assert content.sub_type == "raw_bytes"
        assert content.detail == "high_res"

    def test_init_with_detail(self, valid_base64_image: str) -> None:
        """Test that ResponseImageContent initializes with a detail level."""
        content = ResponseImageContent(
            mime_type="image/png",
            value=valid_base64_image,
            sub_type="base64",
            detail="low_res",
        )
        assert content.mime_type == "image/png"
        assert content.value == valid_base64_image
        assert content.kind == "image"
        assert content.sub_type == "base64"
        assert content.detail == "low_res"

    def test_init_empty_value(self) -> None:
        """Test that ResponseImageContent raises an error for empty value."""
        with pytest.raises(ValueError, match="Image value cannot be empty"):
            ResponseImageContent(
                mime_type="image/jpeg",
                value="",
                sub_type="url",
            )

    def test_init_invalid_base64(self) -> None:
        """Test that ResponseImageContent raises an error for invalid base64."""
        with pytest.raises(
            ValueError,
            match="Image value is not a valid base64 string",
        ):
            ResponseImageContent(
                mime_type="image/png",
                value="invalid base64!",
                sub_type="base64",
            )

    def test_init_invalid_raw_bytes(self) -> None:
        """Test that ResponseImageContent raises an error for invalid raw bytes."""
        with pytest.raises(ValueError, match="Image value must be bytes"):
            ResponseImageContent(
                mime_type="image/gif",
                value="not bytes",
                sub_type="raw_bytes",
            )

    def test_from_pil_image_with_filename(self) -> None:
        """Test from_pil_image with a valid filename."""
        from PIL.Image import Image as PILImage

        # Setup mock PIL Image
        mock_image = MagicMock(PILImage)
        mock_image.filename = "/path/to/image.jpg"
        mock_image.get_format_mimetype = MagicMock(return_value="image/jpeg")

        # Mock Path.is_file to return True
        with patch("pathlib.Path.is_file", return_value=True):
            # Mock Path.read_bytes to return test data
            with patch("pathlib.Path.read_bytes", return_value=b"test image data"):
                content = ResponseImageContent.from_pil_image(mock_image)

                assert content.mime_type == "image/jpeg"
                assert content.value == b"test image data"
                assert content.sub_type == "raw_bytes"

    def test_from_pil_image_without_filename(self) -> None:
        """Test from_pil_image without a valid filename."""
        from PIL.Image import Image as PILImage

        # Setup mock PIL Image
        mock_image = MagicMock(spec=PILImage)
        mock_image.filename = None

        # Mock BytesIO
        mock_bytesio = MagicMock()
        mock_bytesio.getvalue.return_value = b"test webp data"

        # Mock BytesIO constructor
        with patch("io.BytesIO", return_value=mock_bytesio):
            content = ResponseImageContent.from_pil_image(mock_image)

            assert content.mime_type == "image/webp"
            assert content.value == b"test webp data"
            assert content.sub_type == "raw_bytes"

    def test_from_ipython_image_with_filename(
        self,
    ) -> None:
        """Test from_ipython_image with a valid filename."""
        from IPython.display import Image as IPythonImage

        # Setup mock IPython Image
        mock_image = MagicMock(spec=IPythonImage)
        mock_image.filename = "/path/to/image.jpg"

        # Mock Path.is_file to return True
        with patch("pathlib.Path.is_file", return_value=True):
            # Mock Path.read_bytes to return test data
            with patch("pathlib.Path.read_bytes", return_value=b"test image data"):
                # Mock guess_type to return image/jpeg
                with patch("mimetypes.guess_type", return_value=["image/jpeg", None]):
                    content = ResponseImageContent.from_ipython_image(mock_image)

                    assert content.mime_type == "image/jpeg"
                    assert content.value == b"test image data"
                    assert content.sub_type == "raw_bytes"

    def test_from_ipython_image_with_url(self) -> None:
        """Test from_ipython_image with a URL."""
        from IPython.display import Image as IPythonImage

        # Setup mock IPython Image
        mock_image = MagicMock(spec=IPythonImage)
        mock_image.filename = None
        mock_image.url = "https://example.com/image.jpg"
        mock_image.format = "jpeg"

        content = ResponseImageContent.from_ipython_image(mock_image)

        assert content.mime_type == "image/jpeg"
        assert content.value == "https://example.com/image.jpg"
        assert content.sub_type == "url"

    def test_from_ipython_image_with_data(self) -> None:
        """Test from_ipython_image with data."""
        from IPython.display import Image as IPythonImage

        # Setup mock IPython Image
        mock_image = MagicMock(spec=IPythonImage)
        mock_image.filename = None
        mock_image.url = None
        mock_image.data = b"test image data"
        mock_image.format = "png"

        content = ResponseImageContent.from_ipython_image(mock_image)

        assert content.mime_type == "image/png"
        assert content.value == b"test image data"
        assert content.sub_type == "raw_bytes"

    def test_from_ipython_image_invalid(self) -> None:
        """Test from_ipython_image with invalid data."""
        from IPython.display import Image as IPythonImage

        # Setup mock IPython Image
        mock_image = MagicMock(spec=IPythonImage)
        mock_image.filename = None
        mock_image.url = None
        mock_image.data = None

        with pytest.raises(
            ValueError,
            match="IPython Image must either have a valid filename or data content",
        ):
            ResponseImageContent.from_ipython_image(mock_image)

    def test_model_dump(self) -> None:
        """Test that model_dump returns a dictionary with the image data."""
        content = ResponseImageContent(
            mime_type="image/jpeg",
            value="https://example.com/image.jpg",
            sub_type="url",
        )
        data = content.model_dump()
        assert data["kind"] == "image"
        assert data["mime_type"] == "image/jpeg"
        assert data["value"] == "https://example.com/image.jpg"
        assert data["sub_type"] == "url"
        assert data["detail"] == "high_res"

    def test_model_dump_json(self) -> None:
        """Test that model_dump_json returns a JSON string."""
        content = ResponseImageContent(
            mime_type="image/jpeg",
            value="https://example.com/image.jpg",
            sub_type="url",
        )
        json_str = content.model_dump_json()
        assert isinstance(json_str, str)
        data = json.loads(json_str)
        assert data["kind"] == "image"
        assert data["mime_type"] == "image/jpeg"
        assert data["value"] == "https://example.com/image.jpg"
        assert data["sub_type"] == "url"
        assert data["detail"] == "high_res"

    def test_model_validate(self) -> None:
        """Test that model_validate creates a ResponseImageContent from a dictionary."""
        data = {
            "kind": "image",  # This should be removed by model_validate
            "mime_type": "image/jpeg",
            "value": "https://example.com/image.jpg",
            "sub_type": "url",
            "detail": "high_res",
        }
        content = ResponseImageContent.model_validate(data)
        assert isinstance(content, ResponseImageContent)
        assert content.kind == "image"
        assert content.mime_type == "image/jpeg"
        assert content.value == "https://example.com/image.jpg"
        assert content.sub_type == "url"
        assert content.detail == "high_res"

    def test_immutability(self) -> None:
        """Test that ResponseImageContent is immutable."""
        content = ResponseImageContent(
            mime_type="image/jpeg",
            value="https://example.com/image.jpg",
            sub_type="url",
        )
        with pytest.raises(FrozenInstanceError):
            # This should raise an exception because ResponseImageContent is frozen
            content.mime_type = "image/png"  # type: ignore
