import mimetypes
import re
import sys
from urllib.parse import unquote, urlparse

from fastapi import UploadFile

from agent_platform.core.files import FileData

IS_WIN = sys.platform == "win32"
RE_DRIVE_LETTER_PATH = re.compile(r"^\/[a-zA-Z]:")


def normalize_drive(path: str) -> str:
    """Normalize windows drive letters to lowercase."""
    if len(path) >= 2 and path[0].isalpha() and path[1] == ":":  # noqa: PLR2004
        return path[0].lower() + path[1:]
    return path


def url_to_fs_path(file_url: str) -> str:
    """Returns the filesystem path of the given URI.
    Will handle UNC paths and normalize windows drive letters to lower-case.
    Also uses the platform specific path separator. Will *not* validate the
    path for invalid characters and semantics.
    Will validate the scheme of this URI.

    Examples:
        - UNC path: file://shares/c$/far/boo
        - Windows drive letter: file:///C:/far/boo
        - Regular path: file:///path/to/file
    """
    # scheme://netloc/path;parameters?query#fragment
    scheme, netloc, path, _params, _query, _fragment = urlparse(file_url)

    if scheme != "file":
        raise ValueError(f"Invalid file URL scheme: {file_url}")

    path = unquote(path)

    if netloc and path:
        # UNC path: file://shares/c$/far/boo
        value = f"//{netloc}{path}"

    elif RE_DRIVE_LETTER_PATH.match(path):
        # windows drive letter: file:///C:/far/boo
        value = path[1].lower() + path[2:]

    else:
        # Other path
        value = path

    if IS_WIN:
        value = value.replace("/", "\\")
        value = normalize_drive(value)

    return value


# TODO: review/refactor this code once time permits.


def guess_mimetype(file_name: str, file_bytes: bytes) -> str:  # noqa: PLR0911
    """Guess the mime-type of a file based on its name or bytes."""
    # Guess based on the file extension
    mime_type, _ = mimetypes.guess_type(file_name)

    # Return detected mime type from mimetypes guess, unless it's None
    if mime_type:
        return mime_type

    # Signature-based detection for common types
    if file_bytes.startswith(b"%PDF"):
        return "application/pdf"
    elif file_bytes.startswith(
        (b"\x50\x4b\x03\x04", b"\x50\x4b\x05\x06", b"\x50\x4b\x07\x08"),
    ):
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    elif file_bytes.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        return "application/msword"
    elif file_bytes.startswith(b"\x09\x00\xff\x00\x06\x00"):
        return "application/vnd.ms-excel"

    # Check for CSV-like plain text content (commas, tabs, newlines)
    decoded = file_bytes[:1024].decode("utf-8", errors="ignore")
    if all(char in decoded for char in (",", "\n")) or all(
        char in decoded for char in ("\t", "\n")
    ):
        return "text/csv"
    elif decoded.isprintable() or decoded == "":
        return "text/plain"

    return "application/octet-stream"


def convert_to_file_data(file: UploadFile) -> FileData:
    """Convert file to FileData."""
    file_data = file.file.read()
    file_name = file.filename
    file_size = len(file_data)
    # Check if file_name is a valid string
    if not isinstance(file_name, str):
        raise TypeError(f"Expected string for file name, got {type(file_name)}")

    mimetype = guess_mimetype(file_name, file_data)
    return FileData.model_validate(
        {
            "content": file_data,
            "file_name": file_name,
            "mime_type": mimetype,
            "file_size": file_size,
        },
    )
