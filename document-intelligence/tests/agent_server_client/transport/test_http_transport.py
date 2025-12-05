from unittest.mock import MagicMock, patch

import pytest

from sema4ai_docint.agent_server_client.transport.http import HTTPTransport
from tests.agent_dummy_server import SCHEMA_RESPONSE, AgentDummyServer


class TestHTTPTransport:
    @property
    def agent_id(self) -> str:
        return "test_agent_id"

    @property
    def thread_id(self) -> str:
        return "test_thread_id"

    @pytest.fixture
    def http_transport(self, agent_dummy_server: AgentDummyServer) -> HTTPTransport:
        transport = HTTPTransport(
            agent_id=self.agent_id,
            thread_id=self.thread_id,
        )
        transport.connect()  # This will send a request to the dummy server's ok endpoint
        return transport

    def test_get_api_url(self, http_transport: HTTPTransport, agent_dummy_server: AgentDummyServer):
        """Tests that the API URL is correctly constructed via environment variable. This
        test is avoiding PID file lookup as that is not normally how it will work in production.

        Note: The dummy server fixture sets the SEMA4AI_AGENTS_SERVICE_URL environment variable
        to the dummy server's port.
        """
        assert http_transport.api_url == f"http://localhost:{agent_dummy_server.get_port()}/api/v2/"

    def test_agent_id_in_request_url(
        self, agent_dummy_server: AgentDummyServer, http_transport: HTTPTransport
    ):
        """Test that the agent_id is included as a query parameter in the request URL."""
        with patch(
            "sema4ai_docint.agent_server_client.transport.http.sema4ai_http"
        ) as mock_sema4ai_http:
            # Create a mock response object that looks like sema4ai_http.ResponseWrapper
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.status = 200
            mock_response.raise_for_status.return_value = None

            # Create a mock HTTP method (e.g., get, post, etc.)
            mock_http_method = MagicMock(return_value=mock_response)
            mock_sema4ai_http.get = mock_http_method

            # Make a test request using the http_transport
            http_transport.request(
                method="GET", path="test-endpoint", params={"some_param": "value"}
            )

            # Verify that the sema4ai_http method was called
            mock_http_method.assert_called_once()

            # Get the actual call arguments
            call_args = mock_http_method.call_args
            actual_url = call_args[0][0]  # First positional argument should be the URL

            # Verify that the agent_id is included in the URL as a query parameter
            assert f"agent_id={self.agent_id}" in actual_url, (
                f"Expected agent_id={self.agent_id} to be in URL: {actual_url}"
            )

            # Verify the original param is also there
            assert "some_param=value" in actual_url, (
                f"Expected some_param=value to be in URL: {actual_url}"
            )

    def test_default_params(
        self, agent_dummy_server: AgentDummyServer, http_transport: HTTPTransport
    ):
        """Test that the agent_id is included as a query parameter in the request URL."""
        with patch(
            "sema4ai_docint.agent_server_client.transport.http.sema4ai_http"
        ) as mock_sema4ai_http:
            # Create a mock response object that looks like sema4ai_http.ResponseWrapper
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.status = 200
            mock_response.raise_for_status.return_value = None

            # Create a mock HTTP method (e.g., get, post, etc.)
            mock_http_method = MagicMock(return_value=mock_response)
            mock_sema4ai_http.get = mock_http_method

            # Make a test request using the http_transport
            http_transport.request(method="GET", path="test-endpoint")

            # Verify that the sema4ai_http method was called
            mock_http_method.assert_called_once()

            # Get the actual call arguments
            call_args = mock_http_method.call_args
            actual_url = call_args[0][0]  # First positional argument should be the URL

            # Verify that the agent_id is included in the URL as a query parameter
            assert f"agent_id={self.agent_id}" in actual_url, (
                f"Expected agent_id={self.agent_id} to be in URL: {actual_url}"
            )

            # Verify that the thread_id is included in the URL as a query parameter
            assert f"thread_id={self.thread_id}" in actual_url, (
                f"Expected thread_id={self.thread_id} to be in URL: {actual_url}"
            )

    @pytest.mark.parametrize("agent_dummy_server", [[SCHEMA_RESPONSE]], indirect=True)
    def test_prompts_generate(
        self, agent_dummy_server: AgentDummyServer, http_transport: HTTPTransport
    ):
        """Test that the prompts/generate endpoint is correctly called."""
        response = http_transport.prompts_generate(payload={"prompt": "test prompt"})
        assert response.content[0]["text"] == SCHEMA_RESPONSE
