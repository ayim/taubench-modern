from unittest.mock import patch

import pytest
from IPython.display import Image as IPythonImage
from PIL import Image as PILImage
from PIL import UnidentifiedImageError

from agent_platform.core.prompts.content.image import PromptImageContent


@pytest.fixture
def sample_image_path(tmp_path):
    """Creates a temporary test image file."""
    img_path = tmp_path / "test_image.png"
    # Create a small test image
    img = PILImage.new("RGB", (100, 100), color="red")
    img.save(img_path)
    return img_path


@pytest.fixture
def sample_pil_image(sample_image_path):
    """Returns a PIL Image for testing."""
    return PILImage.open(sample_image_path)


@pytest.fixture
def sample_ipython_image(sample_image_path):
    """Returns an IPython Image for testing."""
    return IPythonImage(filename=str(sample_image_path))


class TestPromptImageContent:
    #
    # Basic Initialization Tests
    #
    def test_init_with_url(self):
        """Test initialization with a URL."""
        content = PromptImageContent(
            mime_type="image/jpeg",
            value="https://picsum.photos/200/300",
            sub_type="url",
        )
        assert content.mime_type == "image/jpeg"
        assert content.value == "https://picsum.photos/200/300"
        assert content.sub_type == "url"
        assert content.kind == "image"  # default is always 'image'
        assert content.detail == "high_res"  # default

    def test_init_with_empty_value(self):
        """Test initialization with empty value."""
        with pytest.raises(ValueError, match="Image value cannot be empty"):
            PromptImageContent(mime_type="image/jpeg", value="", sub_type="url")

    def test_init_with_base64(self):
        """Test initialization with valid base64 data."""
        base64_value = (
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lE"
            "QVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
        )
        content = PromptImageContent(
            mime_type="image/png",
            value=base64_value,
            sub_type="base64",
        )
        assert content.mime_type == "image/png"
        assert content.value == base64_value
        assert content.sub_type == "base64"
        assert content.kind == "image"

    def test_init_with_invalid_base64(self):
        """Test initialization with invalid base64 data."""
        with pytest.raises(
            ValueError,
            match="Image value is not a valid base64 string",
        ):
            PromptImageContent(
                mime_type="image/png",
                value="not_valid_base64",
                sub_type="base64",
            )

    def test_init_with_raw_bytes_success(self):
        """Test initialization with valid raw bytes."""
        dummy_bytes = b"\x89PNG\r\n\x1a\n"  # Some plausible PNG header
        content = PromptImageContent(
            mime_type="image/png",
            value=dummy_bytes,
            sub_type="raw_bytes",
        )
        assert content.value == dummy_bytes
        assert content.sub_type == "raw_bytes"
        assert content.kind == "image"

    def test_init_with_raw_bytes_invalid_type(self):
        """Test initialization with 'raw_bytes' sub_type but non-bytes value."""
        with pytest.raises(ValueError, match="Image value must be bytes"):
            PromptImageContent(
                mime_type="image/png",
                value="not_bytes",
                sub_type="raw_bytes",
            )

    #
    # Literal Field Validation Tests
    #
    @pytest.mark.parametrize("invalid_mime", ["image/xyz", "text/html", "video/mp4"])
    def test_init_with_invalid_mime_type(self, invalid_mime):
        """Test initialization with invalid MIME type."""
        with pytest.raises(ValueError, match="Invalid value for 'mime_type'"):
            PromptImageContent(
                mime_type=invalid_mime,
                value="https://picsum.photos/200/300",
                sub_type="url",
            )

    def test_init_with_invalid_sub_type_literal(self):
        """Test initialization with invalid 'sub_type' literal."""
        with pytest.raises(ValueError, match="Invalid value for 'sub_type'"):
            PromptImageContent(
                mime_type="image/jpeg",
                value="some_url",
                sub_type="invalid_subtype",
            )

    def test_init_with_invalid_detail_literal(self):
        """Test initialization with invalid 'detail' literal."""
        with pytest.raises(ValueError, match="Invalid value for 'detail'"):
            PromptImageContent(
                mime_type="image/jpeg",
                value="some_url",
                sub_type="url",
                detail="medium_res",  # not valid
            )

    def test_init_with_low_res_detail(self):
        """Test initialization with a valid 'low_res' detail."""
        content = PromptImageContent(
            mime_type="image/jpeg",
            value="some_url",
            sub_type="url",
            detail="low_res",
        )
        assert content.detail == "low_res"

    def test_default_detail_is_high_res(self):
        """Test the default detail is 'high_res'."""
        content = PromptImageContent(
            mime_type="image/jpeg",
            value="some_url",
            sub_type="url",
        )
        assert content.detail == "high_res"

    #
    # from_pil_image Tests
    #
    def test_from_pil_image_with_valid_filename(self, sample_pil_image):
        """Test creation from a PIL Image with a valid filename."""
        # sample_pil_image is backed by a real file (test_image.png).
        content = PromptImageContent.from_pil_image(sample_pil_image)
        # The guessed MIME from PIL might be image/png
        assert content.mime_type == "image/png"
        assert isinstance(content.value, bytes)
        assert content.sub_type == "raw_bytes"

    def test_from_pil_image_without_filename_saves_as_webp(self):
        """Test creation from a PIL Image that has no filename attribute."""
        img = PILImage.new("RGB", (50, 50), color="blue")
        # This image has no valid filename. Should save as webp internally.
        content = PromptImageContent.from_pil_image(img)
        assert content.mime_type == "image/webp"
        assert isinstance(content.value, bytes)
        assert content.sub_type == "raw_bytes"

    def test_from_pil_image_non_pil_object_raises_error(self):
        """Test passing a non-PIL object to from_pil_image."""
        with pytest.raises(ValueError, match="Image must be a PIL Image"):
            PromptImageContent.from_pil_image("not_a_pil_image")

    @patch("PIL.Image.Image.save", side_effect=UnidentifiedImageError("Mock error"))
    def test_from_pil_image_save_error(self, mock_save):
        """Test failure to save PIL image to BytesIO as webp raises ValueError."""
        img = PILImage.new("RGB", (50, 50), color="blue")
        # Force a failure in .save()
        with pytest.raises(ValueError, match="Failed to save image to bytesio as webp"):
            PromptImageContent.from_pil_image(img)

    #
    # from_ipython_image Tests
    #
    def test_from_ipython_image_with_valid_filename(self, sample_ipython_image):
        """Test creation from an IPython Image with a valid filename."""
        content = PromptImageContent.from_ipython_image(sample_ipython_image)
        assert content.mime_type == "image/png"
        assert isinstance(content.value, bytes)
        assert content.sub_type == "raw_bytes"

    def test_from_ipython_image_with_data_no_filename(self):
        """Test creation from IPython Image that has data but no valid filename."""
        # Provide raw bytes and a format.
        data = b"fake_image_data"
        ipy_img = IPythonImage(data=data, format="PNG")
        content = PromptImageContent.from_ipython_image(ipy_img)
        assert content.mime_type == "image/png"
        assert content.value == data
        assert content.sub_type == "raw_bytes"

    def test_from_ipython_image_with_data_no_format_fallback(self):
        """Test fallback MIME type when no format is specified."""
        data = b"fake_image_data"
        ipy_img = IPythonImage(data=data, format=None)
        content = PromptImageContent.from_ipython_image(ipy_img)
        # Should default to "image/jpeg" if no format is specified
        # BUT, looks like IPythonImage.format is defaulted to "png"
        # if no format is specified.
        assert content.mime_type == "image/png"
        assert content.value == data
        assert content.sub_type == "raw_bytes"

    def test_from_ipython_image_url_no_format_raises_error(self):
        """Test IPython Image with no valid filename or data."""
        ipy_img = IPythonImage(url="https://picsum.photos/200/300")
        with pytest.raises(ValueError, match="Invalid value for 'mime_type'"):
            PromptImageContent.from_ipython_image(ipy_img)

    def test_from_ipython_image_url_with_format(self):
        """Test IPython Image with no valid filename or data."""
        ipy_img = IPythonImage(url="https://picsum.photos/200/300", format="jpeg")
        content = PromptImageContent.from_ipython_image(ipy_img)
        assert content.mime_type == "image/jpeg"
        assert content.value == "https://picsum.photos/200/300"
        assert content.sub_type == "url"

    def test_from_ipython_image_non_ipy_object_raises_error(self):
        """Test passing a non-IPython display object."""
        with pytest.raises(ValueError, match="Image must be an IPython Image"):
            PromptImageContent.from_ipython_image("not_an_ipython_image")
