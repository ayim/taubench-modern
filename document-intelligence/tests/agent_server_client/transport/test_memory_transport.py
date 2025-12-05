"""Tests for the memory transport client using FastAPI dummy server."""

import datetime
from pathlib import Path

import pytest

from sema4ai_docint.agent_server_client.transport.memory import MemoryTransport
from tests.agent_dummy_server import SCHEMA_RESPONSE
from tests.agent_server_client.fast_api_dummy_server import FileResponse

from ..conftest import FastAPIAgentDummyServer


class TestMemoryTransport:
    """Test suite for MemoryTransport using FastAPIAgentDummyServer."""

    @property
    def agent_id(self) -> str:
        return "test_agent_id"

    @property
    def thread_id(self) -> str:
        return "test_thread_id"

    @property
    def user_id(self) -> str:
        return "test_user_id"

    @pytest.fixture
    def memory_transport(
        self, fastapi_agent_dummy_server: FastAPIAgentDummyServer
    ) -> MemoryTransport:
        transport = MemoryTransport(
            base_url="http://test",
            agent_id=self.agent_id,
            thread_id=self.thread_id,
            app=fastapi_agent_dummy_server.get_app(),
        )
        transport.connect()  # This will send a request to the dummy server's ok endpoint
        return transport

    def test_id_param_injection_into_request_url(self, memory_transport: MemoryTransport):
        """Test that the agent_id and thread_id are included as query parameters
        in the request URL."""
        response = memory_transport.request(method="GET", path="ok")
        assert f"agent_id={self.agent_id}" in str(response._response.url)
        assert f"thread_id={self.thread_id}" in str(response._response.url)

    @pytest.mark.parametrize("fastapi_agent_dummy_server", [[SCHEMA_RESPONSE]], indirect=True)
    def test_prompts_generate(
        self,
        fastapi_agent_dummy_server: FastAPIAgentDummyServer,
        memory_transport: MemoryTransport,
    ):
        """Test that the prompts/generate endpoint is correctly called."""
        response = memory_transport.prompts_generate(payload={"prompt": "test prompt"})
        assert response.content[0]["text"] == SCHEMA_RESPONSE

    @property
    def train_ticket_pdf_path(self) -> Path:
        return Path(__file__).parent.parent / "test-data" / "docs" / "train_ticket.pdf"

    @property
    def train_ticket_pdf_file_response(self) -> FileResponse:
        return FileResponse(
            file_id="test-uuid-123",
            file_path=f"file://{self.train_ticket_pdf_path!s}",
            file_ref="train_ticket.pdf",
            file_hash="test-hash-123",
            mime_type="application/pdf",
            file_size_raw=self.train_ticket_pdf_path.stat().st_size,
            embedded=False,
            file_path_expiration=None,
            agent_id=self.agent_id,
            thread_id=self.thread_id,
            user_id=self.user_id,
            file_url=f"file://{self.train_ticket_pdf_path!s}",
            work_item_id=None,
            created_at=datetime.datetime.now(datetime.UTC).isoformat(),
        )

    def test_get_file(
        self,
        fastapi_agent_dummy_server: FastAPIAgentDummyServer,
        memory_transport: MemoryTransport,
    ):
        """Test custom file response injection for both file endpoints."""
        # Set up file response
        fastapi_agent_dummy_server.file_responses["train_ticket.pdf"] = (
            self.train_ticket_pdf_file_response
        )

        # Test custom file response via get_file endpoint
        file_path = memory_transport.get_file("train_ticket.pdf")
        assert file_path.exists()
        assert file_path.read_bytes() == self.train_ticket_pdf_path.read_bytes()

    def test_get_file_establishes_connection_when_not_connected(
        self, fastapi_agent_dummy_server: FastAPIAgentDummyServer
    ):
        """Test that get_file establishes connection if not already connected."""
        # Create transport without calling connect()
        transport = MemoryTransport(
            base_url="http://test",
            agent_id=self.agent_id,
            thread_id=self.thread_id,
            app=fastapi_agent_dummy_server.get_app(),
        )

        # Verify not connected initially
        assert not transport.is_connected()

        # Set up file response
        fastapi_agent_dummy_server.file_responses["test.pdf"] = self.train_ticket_pdf_file_response

        # Call get_file - should establish connection automatically
        file_path = transport.get_file("test.pdf")

        # Verify connection was established
        assert transport.is_connected()
        assert file_path.exists()
