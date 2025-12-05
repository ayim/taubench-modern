"""In-memory transport implementation using FastAPI TestClient."""

import logging
import tempfile
from http import HTTPStatus
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
import sema4ai_http
from sema4ai.actions import _uris

from sema4ai_docint.agent_server_client.transport.errors import (
    TransportFileRetrievalError,
    TransportNotConnectedError,
    TransportThreadIdRequiredError,
)

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
except ImportError as e:
    raise ImportError("FastAPI must be installed to use the MemoryTransport. ") from e

from .base import TransportBase, TransportResponseWrapper

logger = logging.getLogger(__name__)


class MemoryTransport(TransportBase):
    """In-memory transport implementation using FastAPI TestClient.

    This transport bypasses network overhead entirely by using FastAPI's TestClient
    to make direct in-memory calls to a FastAPI app instance.
    """

    def __init__(
        self,
        base_url: str | None = None,
        agent_id: str | None = None,
        thread_id: str | None = None,
        additional_headers: dict[str, str] | None = None,
        *,
        app: FastAPI,
        **kwargs: Any,
    ):
        """Initialize the transport protocol.

        Args:
            base_url: The base URL of the agent server
            agent_id: The agent ID to attach to this transport instance as context
            thread_id: The thread ID to attach to this transport instance as context
            additional_headers: Additional headers to add to every request
            app: FastAPI app instance to call directly
            **kwargs: Additional transport-specific initialization parameters
        """
        super().__init__(
            base_url=base_url,
            agent_id=agent_id,
            thread_id=thread_id,
            additional_headers=additional_headers,
            **kwargs,
        )
        # For in-memory transport, the agent-server will pass in the private_v2 app, not the
        # top level app, so we cannot use the full v2 api url and must use only the base URL.
        self._api_url = base_url or ""
        self.app = app
        self.client: TestClient | None = None

    def connect(self) -> None:
        self.client = TestClient(
            self.app,
            base_url=self._api_url,
            headers={"user-agent": "python/sema4ai-docint"},
        )

        # Check health endpoint
        self._is_connected = self.is_connected()
        if not self._is_connected:
            raise TransportNotConnectedError()
        logger.info("Memory transport initialized successfully")

    def is_connected(self) -> bool:
        """Check the health of the agent server.

        Raises:
            ValueError: If the health check fails
        """
        if not self.client:
            return False

        response = self.request("GET", "ok")

        if response.status_code != HTTPStatus.OK:
            return False

        return True

    def _request(
        self,
        method: str,
        path: str,
        *,
        content: bytes | str | None = None,
        data: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        if not self.client:
            raise TransportNotConnectedError()

        # Throw if mutually exclusive parameters are provided
        if content is not None and data is not None:
            raise ValueError("content and data cannot be provided together")
        if content is not None and json is not None:
            raise ValueError("content and json cannot be provided together")
        if data is not None and json is not None:
            raise ValueError("data and json cannot be provided together")
        if files is not None and json is not None:
            raise ValueError("files and json cannot be provided together")
        if files is not None and content is not None:
            raise ValueError("files and content cannot be provided together")

        path = TransportBase._clean_path(path)

        # Build full URL path
        url = urljoin(self._api_url, path)

        params = params or {}
        # Add agent_id as query parameter if available and not already set
        if self.agent_id is not None and params.get("agent_id") is None:
            logger.info(f"Adding agent_id to params: {self.agent_id}")
            params.update(agent_id=self.agent_id)

        # Add thread_id as query parameter if available and not already set
        if self.thread_id is not None and params.get("thread_id") is None:
            logger.info(f"Adding thread_id to params: {self.thread_id}")
            params.update(thread_id=self.thread_id)

        # FastAPI TestClient doesn't like the timeout param, so we remove it
        kwargs.pop("timeout", None)

        # Add additional headers
        request_headers = headers.copy() if headers else {}
        if self._additional_headers:
            request_headers = {**self._additional_headers, **request_headers}

        response = self.client.request(
            method,
            url,
            content=content,
            data=data,
            json=json,
            files=files,
            params=params,
            headers=request_headers,
            **kwargs,
        )

        return response

    def request(
        self,
        method: str,
        path: str,
        *,
        content: bytes | str | None = None,
        data: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> TransportResponseWrapper:
        """Make an in-memory request to the agent server.

        Args:
            method: HTTP method (GET, POST, etc.)
            path: API endpoint path
            content: Optional raw request body content
            data: Optional form data payload for the request
            json: Optional JSON payload for the request
            files: Optional files for multipart upload (dict with filename tuples)
            params: Optional query parameters to append to URL
            headers: Optional additional headers
            **kwargs: Additional parameters passed to the underlying client

        Returns:
            TransportResponseWrapper: Transport-agnostic response object

        Raises:
            ConnectionError: If the request fails or returns an error status
        """
        response = self._request(
            method,
            path,
            content=content,
            data=data,
            json=json,
            files=files,
            headers=headers,
            params=params,
            **kwargs,
        )
        return TransportResponseWrapper(response)

    def close(self) -> None:
        """Close the memory transport.

        For memory transport, this closes the TestClient.
        """
        if self.client:
            # TestClient doesn't have an explicit close method,
            # but we can clean up the reference
            self.client = None

    def get_file(self, name: str, thread_id: str | None = None) -> Path:
        """Get a file from the agent server."""
        # This method may be called lazily by the DIService, so we attempt to connect here
        # if we are not already connected

        if not self.is_connected():
            self.connect()

        if self.thread_id is None and thread_id is None:
            raise TransportThreadIdRequiredError()

        thread_id = thread_id or self.thread_id
        response = self.request(
            method="GET",
            path=f"threads/{thread_id}/file-by-ref",
            params={"file_ref": name},
        )
        uploaded_file = response.json()
        file_url = uploaded_file.get("file_url")
        if not file_url:
            raise TransportFileRetrievalError(name, "File URL not found in response")

        parsed_url = urlparse(file_url)
        if parsed_url.scheme == "file":
            # As we are in memory, the path should be accessible to us
            return Path(_uris.to_fs_path(file_url))
        else:
            try:
                download_response = sema4ai_http.get(file_url)
                download_response.raise_for_status()
            except Exception as e:
                raise TransportFileRetrievalError(name, f"Failed to download file: {e!s}") from e
            file_bytes = download_response.response.data
            # Write the file locally for use elsewhere
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_file.write(file_bytes)
                temp_file_path = temp_file.name
            return Path(temp_file_path)
