import pytest

from sema4ai_docint.agent_server_client.transport.http import HTTPTransport
from sema4ai_docint.agent_server_client.transport.memory import MemoryTransport
from sema4ai_docint.services.persistence.file import AgentServerChatFileAccessor
from tests.agent_server_client.fast_api_dummy_server import FastAPIAgentDummyServer


@pytest.mark.asyncio
class TestAgentServerFileAccessor:
    async def test_file_crud_operations(self, agent_server_cli, agent_id, thread_id):
        api_url = f"http://localhost:{agent_server_cli.get_http_port()}/api/v2/"
        transport = HTTPTransport(agent_id=agent_id, api_url=api_url)
        transport.connect()

        accessor = AgentServerChatFileAccessor(thread_id=thread_id, transport=transport)

        # List the files
        files = await accessor.list()
        assert len(files) == 0, "Expected no files in the thread"

        # Write a file
        await accessor.write_text("test_file.txt", b"Hello, world!")

        # List the files again
        files = await accessor.list()
        assert len(files) == 1, "Expected one file in the thread"
        assert files[0] == "test_file.txt", "Expected file to be named test_file.txt"

        # Read the file
        content = await accessor.read_text("test_file.txt")
        assert content == b"Hello, world!", "Expected file content to be 'Hello, world!'"

    async def test_file_crud_operations_with_memory_transport(self, agent_id, thread_id):
        """Test file CRUD operations using MemoryTransport with FastAPIAgentDummyServer."""
        # Create a dummy server with file management endpoints
        server = FastAPIAgentDummyServer()
        app = server.get_app()

        # Create MemoryTransport with the server's app
        transport = MemoryTransport(
            base_url="http://test",
            agent_id=agent_id,
            thread_id=thread_id,
            app=app,
        )
        transport.connect()

        accessor = AgentServerChatFileAccessor(thread_id=thread_id, transport=transport)

        # List the files (should be empty)
        files = await accessor.list()
        assert len(files) == 0, "Expected no files in the thread"

        # Write a file
        await accessor.write_text("test_file.txt", b"Hello, world!")

        # List the files again
        files = await accessor.list()
        assert len(files) == 1, "Expected one file in the thread"
        assert files[0] == "test_file.txt", "Expected file to be named test_file.txt"

        # Read the file
        content = await accessor.read_text("test_file.txt")
        assert content == b"Hello, world!", "Expected file content to be 'Hello, world!'"

        # Write another file
        await accessor.write_text("test_file2.txt", b"Second file content")

        # List should now have 2 files
        files = await accessor.list()
        assert len(files) == 2, "Expected two files in the thread"
        assert "test_file.txt" in files
        assert "test_file2.txt" in files

        # Read the second file
        content2 = await accessor.read_text("test_file2.txt")
        assert content2 == b"Second file content"

        # Test reading non-existent file
        content_none = await accessor.read_text("nonexistent.txt")
        assert content_none is None, "Expected None for non-existent file"
