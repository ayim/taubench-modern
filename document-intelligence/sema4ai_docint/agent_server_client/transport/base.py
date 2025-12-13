"""Transport protocol base class for AgentServerClient."""

import json
from abc import ABC, abstractmethod
from http import HTTPStatus
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urljoin

import httpx
import sema4ai_http
from pydantic import BaseModel, Field

from sema4ai_docint.agent_server_client.transport.errors import TransportResponseConversionError


class TransportResponseWrapper:
    """A transport-agnostic response wrapper that provides common API functionality similar
    to other http libraries.

    All attributes of the response object are available via the response property or
    from the reponse itself.
    """

    def __init__(
        self,
        # Update with other transport types as they are added
        response: sema4ai_http.ResponseWrapper | httpx.Response,
    ):
        self._response = response

    @property
    def status(self) -> int:
        return self._response.status_code

    @property
    def status_code(self) -> int:
        return self._response.status_code

    @property
    def text(self) -> str:
        if isinstance(self._response, sema4ai_http.ResponseWrapper):
            return self._response.data.decode(errors="replace")
        elif isinstance(self._response, httpx.Response):
            return self._response.text
        else:
            raise ValueError(f"Unsupported response type: {type(self._response)}")

    def raise_for_status(self) -> None:
        self._response.raise_for_status()

    def ok(self) -> bool:
        return self._response.status_code < HTTPStatus.BAD_REQUEST

    def json(self) -> Any:
        return self._response.json()


class ResponseMessage(BaseModel):
    """A response message from the agent server's prompts/generate endpoint."""

    content: list[dict[str, Any]] = Field(
        default_factory=list, description="The contents of the model's response"
    )
    role: Literal["agent"] = Field(default="agent", description="The role of the message sender")
    raw_response: Any | None = Field(default=None, description="The raw response from the model")
    stop_reason: str | None = Field(default=None, description="The reason why the response stopped")
    usage: dict[str, Any] = Field(default_factory=dict, description="Token usage statistics")
    metrics: dict[str, Any] = Field(
        default_factory=dict,
        description="Model performance metrics and timing information",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata about the response generation",
    )
    additional_response_fields: dict[str, Any] = Field(
        default_factory=dict,
        description="Provider-specific response fields not covered by other attributes",
    )


class TransportBase(ABC):
    """Abstract base class defining the transport protocol interface.

    This protocol defines how the AgentServerClient communicates with
    the agent server, allowing for different transport implementations
    (HTTP, IPC, etc.).
    """

    def __init__(
        self,
        base_url: str | None = None,
        agent_id: str | None = None,
        thread_id: str | None = None,
        additional_headers: dict[str, str] | None = None,
        **kwargs: Any,
    ):
        """Initialize the transport protocol.

        Args:
            base_url: The base URL of the agent server
            agent_id: The agent ID to attach to this transport instance as context
            thread_id: The thread ID to attach to this transport instance as context
            additional_headers: Additional headers to add to every request
            **kwargs: Additional transport-specific initialization parameters
        """
        self._agent_id = agent_id
        self._thread_id = thread_id
        self._api_url = self._build_agent_server_v2_url(base_url or "")
        self._is_connected = False
        self._additional_headers = additional_headers

    @staticmethod
    def _build_agent_server_v2_url(base_url: str) -> str:
        """
        Builds the base url for the private-v2 API on agent server from the base url
        of the agent server.
        """
        # Ensure base_url ends with a slash for proper joining
        if not base_url.endswith("/"):
            base_url += "/"
        # carefully using urljoin to not lose any original path on base_url
        return urljoin(base_url, "api/v2/")

    @staticmethod
    def _clean_path(path: str) -> str:
        """
        Cleans the path by removing any leading slashes as that would cause urljoin to
        escape the path down to the root of the server.
        """
        return path.lstrip("/")

    @abstractmethod
    def connect(
        self,
    ) -> None:
        """Connects to the agent server based on initialization parameters.

        Raises:
            TransportConnectionError: If the transport cannot be initialized or connected
        """

    @abstractmethod
    def is_connected(self) -> bool:
        """Check if the transport is connected to the agent server.

        Returns:
            bool: True if connected, False otherwise

        Raises:
            TransportConnectionError: If the transport is not connected
        """

    @abstractmethod
    def close(self) -> None:
        """Close the transport and clean up resources.

        This method should be called when the transport is no longer needed.
        """

    @property
    def api_url(self) -> str:
        """The full API URL including the host and base path (e.g., "http://localhost:8000/api/v2").

        Returns:
            str: The API URL
        """
        return self._api_url

    @property
    def agent_id(self) -> str | None:
        """The agent ID attached to this transport instance.

        Returns:
            str | None: The agent ID if attached, None otherwise
        """
        return self._agent_id

    @property
    def thread_id(self) -> str | None:
        """The thread ID attached to this transport instance.

        Returns:
            str | None: The thread ID if attached, None otherwise
        """
        return self._thread_id

    @abstractmethod
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
        """Make a request to the agent server.

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
            ResponseMessage: Transport-agnostic response object

        Raises:
            TransportConnectionError: If the request fails
        """

    def prompts_generate(self, payload: dict[str, Any]) -> ResponseMessage:
        """Generate a prompt response using the in-memory agent server.

        Args:
            payload: The prompt payload containing prompt specification

        Returns:
            ResponseMessage: Transport-agnostic response object with the generated content

        Raises:
            ConnectionError: If the request fails
        """
        response = self.request(
            path="prompts/generate",
            method="POST",
            json=payload,
        )
        return self._convert_to_response_message(response)

    def _convert_to_response_message(self, response: TransportResponseWrapper) -> ResponseMessage:
        """Convert a TransportResponseWrapper response to our ResponseMessage.

        Args:
            response: The TransportResponseWrapper response object

        Returns:
            ResponseMessage: Our transport-agnostic response message
        """
        # Parse the JSON response from the agent server
        try:
            response_data = response.json()
        except (json.JSONDecodeError, AttributeError) as e:
            # If we can't marshal the response to JSON, there must be a problem
            raise TransportResponseConversionError(response.text) from e

        # Extract fields that match ResponseMessage structure
        return ResponseMessage(
            content=response_data.get("content", []),
            role=response_data.get("role", "agent"),
            raw_response=response,  # Store the full response
            stop_reason=response_data.get("stop_reason"),
            usage=response_data.get("usage", {}),
            metrics=response_data.get("metrics", {}),
            metadata=response_data.get("metadata", {}),
            additional_response_fields=response_data.get("additional_response_fields", {}),
        )

    @abstractmethod
    def get_file(self, name: str, thread_id: str | None = None) -> Path:
        """Get a file from the agent server.

        Args:
            name: The name of the file to get
            thread_id: The thread ID to get the file from
                If not provided, the thread ID attached to the transport instance will be used.

        Returns:
            Path: The path to the file

        Raises:
            TransportConnectionError: If the file cannot be retrieved
        """
