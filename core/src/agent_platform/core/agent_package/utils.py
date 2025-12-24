import base64
import mimetypes
from pathlib import Path
from typing import TYPE_CHECKING

from sema4ai.common.text import slugify

if TYPE_CHECKING:
    from agent_platform.core.agent_package.spec import SpecActionPackageType


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


def create_action_package_path(
    action_package_type: "SpecActionPackageType", organization: str, name: str, version: str
) -> str:
    """Create the action package path used in agent package spec.

    Args:
        action_package_type: Type of the action package ("zip" or "folder").
        organization: Organization name.
        name: Action package name.
        version: Action package version.
    Returns:
        Action package path as a POSIX string.
    """
    if action_package_type == "zip":
        return Path(organization).joinpath(f"{slugify(name)}").joinpath(f"{version}.zip").as_posix()
    elif action_package_type == "folder":
        return Path(organization).joinpath(slugify(name)).as_posix()
