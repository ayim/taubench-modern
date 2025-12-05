"""HTTP transport implementation for AgentServerClient."""

import json
import logging
import os
import platform
from collections.abc import Callable
from http import HTTPStatus
from math import e
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urljoin

import sema4ai_http
from sema4ai.actions._action import get_current_requests_contexts
from sema4ai.actions.chat import get_file

from sema4ai_docint.agent_server_client.transport.errors import (
    TransportMissingBaseUrlError,
    TransportNotConnectedError,
)

from .base import TransportBase, TransportResponseWrapper

# Constants for HTTP context handling
AGENT_ID_INVOCATION_CONTEXT_NAME = "agent_id"
AGENT_ID_HEADER_NAME = "X-INVOKED_BY_ASSISTANT_ID"

logger = logging.getLogger(__name__)


class HTTPTransport(TransportBase):
    """HTTP transport implementation for communicating with the agent server."""

    def __init__(
        self,
        agent_id: str | None = None,
        thread_id: str | None = None,
        api_url: str | None = None,
        additional_headers: dict[str, str] | None = None,
        **kwargs: Any,
    ):
        super().__init__(
            agent_id=agent_id,
            thread_id=thread_id,
            additional_headers=additional_headers,
            **kwargs,
        )
        # Using the HttpTransport, we want to look for the agent server url in other places.
        self._api_url = api_url or self._find_api_url()
        self._is_cloud = False  # Default to False, can be set based on environment detection

    def _find_api_url(self) -> str:
        """Determine the correct API URL by checking environment variable.
        Returns:
            str: The full API URL including base path.

        Raises:
            TransportMissingBaseUrlError: if the agent server URL cannot be determined.
        """
        # Try to check environment variable
        if service_url := os.getenv("SEMA4AI_AGENTS_SERVICE_URL"):
            logger.info(
                f"Using base URL found from environment variable "
                f"(SEMA4AI_AGENTS_SERVICE_URL): {service_url}"
            )
            return TransportBase._build_agent_server_v2_url(service_url)

        # Try reading from agent-server.pid file - use OS-specific paths
        pid_file_path = HTTPTransport._get_pid_file_path()
        logger.info(f"Looking for PID file at: {pid_file_path}")

        try:
            if os.path.exists(pid_file_path):
                with open(pid_file_path) as f:
                    content = f.read()
                    server_info = json.loads(content)
                    if isinstance(server_info, dict) and (base_url := server_info.get("base_url")):
                        logger.info(f"Using base URL found from PID file: {base_url}")
                        return TransportBase._build_agent_server_v2_url(base_url)
        except (OSError, json.JSONDecodeError):
            logger.warning(f"Error reading PID file: {pid_file_path}, {e!s}")
            pass

        # Could not connect to API server or find the PID file
        raise TransportMissingBaseUrlError()

    @staticmethod
    def _get_pid_file_path() -> str:
        """Get the path to the agent-server.pid file based on the operating system.

        Returns:
            str: Path to the PID file
        """
        home_dir = os.path.expanduser("~")

        # Determine OS-specific path
        if platform.system() == "Windows":
            # Windows path: C:\Users\<username>\AppData\Local\sema4ai\sema4ai-studio\
            # agent-server.pid
            return os.path.join(
                home_dir,
                "AppData",
                "Local",
                "sema4ai",
                "sema4ai-studio",
                "agent-server.pid",
            )
        else:
            # macOS/Linux path: ~/.sema4ai/sema4ai-studio/agent-server.pid
            return os.path.join(home_dir, ".sema4ai", "sema4ai-studio", "agent-server.pid")

    def connect(self) -> None:
        """Connect to the agent server."""
        self.is_connected()
        if not self._is_connected:
            raise TransportNotConnectedError()

    def is_connected(self) -> bool:
        """Check if the transport is connected to the agent server.

        Returns:
            bool: True if connected, False otherwise
        """
        response = self._request(path="/ok", method="GET")
        if response.status_code != HTTPStatus.OK:
            self._is_connected = False
            return False
        else:
            self._is_connected = True
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
    ) -> sema4ai_http.ResponseWrapper:
        """Make an HTTP request to the agent server."""
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

        # Append the path onto the base url
        url = urljoin(self.api_url, path)

        # Make sure params is initialized
        params = params or {}

        # Add agent_id as query parameter if available and not already set
        if self.agent_id is not None and params.get("agent_id") is None:
            logger.info(f"Adding agent_id to params: {self.agent_id}")
            params.update({"agent_id": self.agent_id})

        # Add thread_id as query parameter if available and not already set
        if self.thread_id is not None and params.get("thread_id") is None:
            logger.info(f"Adding thread_id to params: {self.thread_id}")
            params.update(thread_id=self.thread_id)

        # Update headers
        request_headers = headers.copy() if headers else {}
        request_headers["x-action-invocation-context"] = self._get_invocation_context()
        if self._additional_headers:
            request_headers = {**self._additional_headers, **request_headers}

        # Get the right method from sema4ai_http
        try:
            sema4ai_http_method: Callable[..., sema4ai_http.ResponseWrapper] = getattr(
                sema4ai_http, method.lower()
            )
        except AttributeError as e:
            raise ValueError(f"Unsupported HTTP method: {method}") from e

        # Construct url with params
        url = urljoin(url, "?" + urlencode(params)) if params else url

        logger.info(f"Executing {method.upper()} request to {url}")

        # When using files, we need to use fields parameter for multipart/form-data
        # urllib3 (used by sema4ai_http) uses 'fields' for both form data and file uploads
        fields_param = files if files is not None else data

        response = sema4ai_http_method(
            url,
            body=content,
            fields=fields_param,
            headers=request_headers,
            json=json,
            **kwargs,
        )
        response.raise_for_status()

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
        """Make an HTTP request to the agent server.

        Args:
            method: HTTP method (GET, POST, etc.)
            path: API endpoint path
            content: Optional raw request body content
            data: Optional form data payload for the request
            json: Optional JSON payload for the request
            files: Optional files for multipart upload (dict with filename tuples)
            params: Optional query parameters to append to URL
            headers: Optional additional headers
            **kwargs: Additional transport-specific parameters

        Returns:
            TransportResponseWrapper: Transport-agnostic response object

        Raises:
            ConnectionError: If the request fails or returns an error status
        """
        if not self._is_connected:
            raise TransportNotConnectedError()

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

    @property
    def is_cloud_environment(self) -> bool:
        """Check if the transport is operating in a cloud environment.

        Returns:
            bool: True if in cloud environment, False otherwise
        """
        return self._is_cloud

    @property
    def agent_id(self) -> str | None:
        """Get the agent ID for HTTP transport context.

        First checks if an agent_id was explicitly provided during initialization.
        If not, attempts to get it from the HTTP request context.

        Returns:
            str | None: The agent ID if available, None otherwise
        """
        # If agent_id was explicitly provided, use that
        if self._agent_id is not None:
            return self._agent_id

        # Otherwise, try to get from HTTP request context
        return self._get_agent_id_from_context()

    def _get_agent_id_from_context(self) -> str | None:
        """Get agent ID from HTTP request context.

        Returns:
            str | None: The agent ID from context, None if not available
        """
        request_contexts = get_current_requests_contexts()
        if not request_contexts:
            return None

        # In ACE, we have the agent_id in the invocation context
        if request_contexts.invocation_context:
            if (
                isinstance(request_contexts.invocation_context.value, dict)
                and AGENT_ID_INVOCATION_CONTEXT_NAME in request_contexts.invocation_context.value
            ):
                return str(
                    request_contexts.invocation_context.value[AGENT_ID_INVOCATION_CONTEXT_NAME]
                )

        # In Studio, the Router is not in the mix to fill in the InvocationContext.
        # Look at the request headers directly.
        request = request_contexts._request
        if request:
            if AGENT_ID_HEADER_NAME in request.headers:
                return request.headers[AGENT_ID_HEADER_NAME]

        return None

    def _get_invocation_context(self) -> str:
        """Get the invocation context for HTTP transport.

        Returns:
            str: The invocation context data as JSON string
        """
        request_contexts = get_current_requests_contexts()
        if request_contexts is None or request_contexts.invocation_context is None:
            return "{}"  # The value is the x-action-invocation-context to be used in the header
        return request_contexts.invocation_context.initial_data

    def get_file(self, name: str, thread_id: str | None = None) -> Path:
        """Get a file from the agent server."""
        return get_file(name)

    def close(self) -> None:
        """Close the HTTP transport.

        For HTTP, this is a no-op as connections are stateless.
        """
        pass
