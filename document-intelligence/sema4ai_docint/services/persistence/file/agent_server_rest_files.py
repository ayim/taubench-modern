from http import HTTPStatus
from pathlib import Path
from urllib.parse import ParseResult

from pydantic import BaseModel, ConfigDict

from sema4ai_docint.agent_server_client.transport.base import TransportBase

from .chat_file_accessor import ChatFileAccessor


def _parse_file_url(file_url: str) -> Path | ParseResult:
    """
    Detect whether the input string is a local file path or an HTTP(S) URL.

    Args:
        s (str): The input string to check.

    Returns:
        Path: A Path object for local files (including file:// URIs)
        ParseResult: A ParseResult for HTTP(S) URLs

    Raises:
        ValueError: If the input is neither a valid local path nor a URL.
    """
    import os
    from urllib.parse import urlparse
    from urllib.request import url2pathname

    if not isinstance(file_url, str) or not file_url.strip():
        raise ValueError("Input must be a non-empty string.")

    # Check if it's a valid URL
    parsed = urlparse(file_url)

    # Handle HTTP(S) URLs
    if parsed.scheme in ("http", "https") and parsed.netloc:
        return parsed

    # Handle file:// URIs - convert to local path
    if parsed.scheme == "file":
        # url2pathname handles both Unix and Windows file:// URIs correctly
        local_path = url2pathname(parsed.path)
        return Path(local_path)

    # Handle Windows absolute paths (e.g., C:\path\to\file)
    # Check for drive letter pattern: <letter>:<separator>
    min_win_path_length = 3
    is_windows_path = (
        os.name == "nt"
        and len(file_url) >= min_win_path_length
        and file_url[1] == ":"
        and file_url[2] in ("\\", "/")
    )
    if is_windows_path:
        return Path(file_url)

    # Check if it's a valid local path (Unix absolute or relative)
    if os.path.exists(file_url) or os.path.isabs(file_url):
        return Path(file_url)

    raise ValueError(f"Input '{file_url}' is neither a valid local path nor an HTTP(S) URL.")


async def _fetch_file(file_url: str) -> bytes:
    """Reads the file from the remote location."""
    import sema4ai_http

    path_or_url = _parse_file_url(file_url)

    if isinstance(path_or_url, ParseResult):
        response = sema4ai_http.get(path_or_url.geturl())
        response.raise_for_status()
        return response.response.data
    elif isinstance(path_or_url, Path):
        with open(path_or_url, "rb") as f:
            return f.read()
    else:
        raise ValueError(f"Invalid file URL: {file_url}")


class AgentServerChatFileAccessor(ChatFileAccessor):
    """File accessor backed by the REST calls to Agent Server. Not intended
    for use by Sema4.ai Actions and Agents. Use ActionsChatFileAccessor instead."""

    def __init__(self, thread_id: str, transport: TransportBase):
        self._thread_id = thread_id
        self._transport = transport

    async def write_text(self, name: str, content: bytes) -> None:
        resp = self._transport.request(
            method="POST",
            path=f"threads/{self._thread_id}/files",
            files={
                "files": (name, content, "text/plain"),
            },
        )
        resp.raise_for_status()

    async def read_text(self, name: str) -> bytes | None:
        # Return AgentServer "UploadedFile" object.
        response = self._transport.request(
            method="GET",
            path=f"threads/{self._thread_id}/file-by-ref",
            params={"file_ref": name},
        )
        # no such file
        if response.status_code == HTTPStatus.NOT_FOUND:
            return None

        response.raise_for_status()

        uploaded_file = response.json()
        if "file_url" not in uploaded_file:
            raise ValueError(f"File URL not found in response: {uploaded_file}")

        file_url = uploaded_file["file_url"]

        return await _fetch_file(file_url)

    async def list(self) -> list[str]:
        resp = self._transport.request(method="GET", path=f"threads/{self._thread_id}/files")
        resp.raise_for_status()

        # Verify we got a list of UploadedFile
        raw_json = resp.json()
        if not isinstance(raw_json, list):
            raise ValueError(f"expected list of files but got {type(raw_json)}")
        files = [_UploadedFile.model_validate(f) for f in raw_json]

        # Send back just the file names
        return [f.file_ref for f in files]


class _UploadedFile(BaseModel):
    """Represents an uploaded file."""

    # Ignore extra attributes from agent-server, we don't care about them.
    model_config = ConfigDict(extra="ignore")

    file_id: str
    """A unique ID of the file."""

    file_url: str
    """The path of the file."""

    file_ref: str
    """The file name."""
