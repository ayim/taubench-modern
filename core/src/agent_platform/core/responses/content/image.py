from base64 import b64decode
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from agent_platform_core.responses.content.base import ResponseMessageContent
from agent_platform_core.utils import assert_literal_value_valid

if TYPE_CHECKING:
    from IPython.display import Image as IPythonImageType
    from PIL.Image import Image as PILImageType


@dataclass(frozen=True)
class ResponseImageContent(ResponseMessageContent):
    """Represents an image generated or referenced in a model's response.

    This class handles image content in various formats (URL, base64, raw bytes),
    with support for different resolutions and image formats. It provides
    validation and conversion utilities for working with image data.
    """

    mime_type: Literal["image/jpeg", "image/png", "image/gif", "image/webp"] = field(
        metadata={"description": "MIME type of the image"},
    )
    """MIME type of the image"""

    value: str | bytes = field(
        metadata={
            "description": "The image data - either a URL or base64 encoded string, "
            "or raw bytes",
        },
    )
    """The image data - either a URL or base64 encoded string, or raw bytes"""

    kind: Literal["image"] = field(
        default="image",
        init=False,
        metadata={"description": "Content kind identifier, always 'image'"},
    )
    """Content kind identifier, always 'image'"""

    sub_type: Literal["url", "base64", "raw_bytes"] = field(
        default="url",
        metadata={
            "description": "Format of the image data - either a URL or base64 encoded "
            "string, or raw bytes",
        },
    )
    """Format of the image data - either a URL or base64 encoded string, or raw bytes"""

    detail: Literal["low_res", "high_res"] = field(
        default="high_res",
        metadata={"description": "Resolution quality of the image"},
    )
    """Resolution quality of the image"""

    def __post_init__(self) -> None:
        """Validates the image content after initialization.

        Performs validation of literal values and ensures the image value is valid.
        For base64 images, validates the base64 encoding.

        Raises:
            AssertionError: If any literal fields don't match their expected values.
            ValueError: If the image value is empty or if base64 data is invalid.
        """
        # Validate literal values
        assert_literal_value_valid(self, "kind")
        assert_literal_value_valid(self, "sub_type")
        assert_literal_value_valid(self, "detail")
        assert_literal_value_valid(self, "mime_type")

        # Check for empty value
        if not self.value:
            raise ValueError("Image value cannot be empty")

        # Validate base64 data if applicable
        if self.sub_type == "base64":
            try:
                b64decode(self.value, validate=True)
            except Exception as e:
                raise ValueError("Image value is not a valid base64 string") from e

        # Validate raw bytes if applicable
        if self.sub_type == "raw_bytes":
            if not isinstance(self.value, bytes):
                raise ValueError("Image value must be bytes")

    @classmethod
    def from_pil_image(cls, image: "PILImageType") -> "ResponseImageContent":
        """Create a ResponseImageContent from a PIL Image.

        Arguments:
            image: The PIL Image to convert to a ResponseImageContent.

        Returns:
            ResponseImageContent: The converted ResponseImageContent.

        Raises:
            ValueError: If the PIL Image is not valid (i.e., it has no filename and
            cannot be saved to bytesio as webp).
        """
        from pathlib import Path

        from PIL.Image import Image as PILImage

        if not isinstance(image, PILImage):
            raise ValueError("Image must be a PIL Image")

        # Make sure the image filename is a valid file (if it's not we could
        # save image to bytesio as webp and use that instead)
        has_valid_filename = (
            hasattr(image, "filename")
            and image.filename is not None
            and Path(image.filename).is_file()
        )

        if not has_valid_filename:
            try:
                from io import BytesIO

                image_bytes_io = BytesIO()
                image.save(image_bytes_io, format="webp", lossless=True)
                image_bytes_io.seek(0)

                # Set the mime type and image bytes
                mime_type = "image/webp"
                image_bytes = image_bytes_io.getvalue()
            except Exception as e:
                raise ValueError("Failed to save image to bytesio as webp") from e
        else:
            # Otherwise, we have a valid file, so use that
            mime_type = image.get_format_mimetype()
            image_bytes = Path(image.filename).read_bytes()

        return cls(
            mime_type=mime_type,
            value=image_bytes,
            sub_type="raw_bytes",
        )

    @classmethod
    def from_ipython_image(cls, image: "IPythonImageType") -> "ResponseImageContent":
        """Create a ResponseImageContent from an IPython Image.

        Arguments:
            image: The IPython Image to convert to a ResponseImageContent.

        Returns:
            ResponseImageContent: The converted ResponseImageContent.

        Raises:
            ValueError: If the IPython Image is not valid (i.e., it has no
            filename or data).
        """
        from mimetypes import guess_type
        from pathlib import Path

        from IPython.display import Image as IPythonImage

        fallback_mime_type = "image/jpeg"

        if not isinstance(image, IPythonImage):
            raise ValueError("Image must be an IPython Image")

        # If we have a valid filename, use that
        has_valid_filename = (
            hasattr(image, "filename")
            and image.filename is not None
            and Path(image.filename).is_file()
        )

        if has_valid_filename:
            mime_type = guess_type(image.filename)[0] or fallback_mime_type
            return cls(
                mime_type=mime_type,
                value=Path(image.filename).read_bytes(),
                sub_type="raw_bytes",
            )

        # If we have a URL, try and use that
        if image.url:
            # We are expecting the format to be set otherwise, we'll
            # have to just guess the mime type
            mime_type = image.format or fallback_mime_type
            if not mime_type.startswith("image/"):
                mime_type = "image/" + mime_type

            return cls(
                mime_type=mime_type,
                value=image.url,
                sub_type="url",
            )

        # If no valid file but we have data, use that directly
        if image.data:
            # IPython images store their format in the format attribute
            mime_type = (
                f"image/{image.format.lower()}" if image.format else fallback_mime_type
            )

            # If the format doesn't start with "image/", add it
            if not mime_type.startswith("image/"):
                mime_type = "image/" + mime_type

            return cls(
                mime_type=mime_type,
                value=image.data,
                sub_type="raw_bytes",
            )

        raise ValueError(
            "IPython Image must either have a valid filename or data content",
        )

    def model_dump(self) -> dict:
        """Returns a dictionary representation suitable for serialization."""
        return {
            **super().model_dump(),
            "mime_type": self.mime_type,
            "value": self.value,
            "sub_type": self.sub_type,
            "detail": self.detail,
        }

    @classmethod
    def model_validate(cls, data: dict) -> "ResponseImageContent":
        """Create an image content from a dictionary."""
        data = data.copy()
        # Remove 'kind' if present since it's not an init parameter
        if "kind" in data:
            data.pop("kind")
        return cls(**data)


ResponseMessageContent.register_content_kind("image", ResponseImageContent)
