import base64
import mimetypes


def convert_image_bytes_to_base64(image_data: bytes, filename: str) -> str:
    """Convert image bytes to a base64 data URI.

    Args:
        image_data: Raw image bytes.
        filename: Original filename (used to determine MIME type).

    Returns:
        Data URI string (e.g., "data:image/svg+xml;base64,...").

    Raises:
        ValueError: If the file type is unsupported.
    """
    # Extract extension from filename
    ext = ""
    if "." in filename:
        ext = "." + filename.rsplit(".", 1)[-1].lower()

    mime_type = mimetypes.types_map.get(ext, "")

    if not mime_type:
        raise ValueError(f"Unsupported file type: {ext}")

    base64_string = base64.b64encode(image_data).decode("utf-8")
    return f"data:{mime_type};base64,{base64_string}"
