import httpx
import pytest

from sema4ai_docint.agent_server_client.transport.base import (
    TransportBase,
    TransportResponseWrapper,
)
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


async def _assert_basic_crud(accessor: AgentServerChatFileAccessor) -> None:
    assert await accessor.list() == []
    await accessor.write_text("a.txt", b"hello")
    assert sorted(await accessor.list()) == ["a.txt"]
    assert await accessor.read_text("a.txt") == b"hello"
    assert await accessor.read_text("missing.txt") is None


class _StubHTTPTransport(TransportBase):
    """Minimal synchronous TransportBase stub for unit testing thread file operations."""

    def __init__(self, *, thread_id: str, base_url: str = "http://test/api/v2/", upload_dir):
        super().__init__(base_url=base_url, thread_id=thread_id)
        self._upload_dir = upload_dir
        self._files: dict[str, bytes] = {}

    def connect(self) -> None:  # pragma: no cover
        self._is_connected = True

    def is_connected(self) -> bool:  # pragma: no cover
        return True

    def close(self) -> None:  # pragma: no cover
        return None

    def get_file(self, name: str, thread_id: str | None = None):
        from contextlib import contextmanager
        from pathlib import Path

        @contextmanager
        def _get_file():
            _ = thread_id
            if name not in self._files:
                raise FileNotFoundError(name)
            yield Path(self._upload_dir / name)

        return _get_file()

    def request(  # type: ignore[override]
        self,
        method: str,
        path: str,
        *,
        content=None,
        data=None,
        json=None,
        files=None,
        params=None,
        headers=None,
        **kwargs,
    ) -> TransportResponseWrapper:
        path = self._clean_path(path)
        req = httpx.Request(method, f"http://test/{path}")

        if method == "POST" and path == f"threads/{self.thread_id}/files":
            assert files is not None
            file_tuple = files["files"]
            file_ref, file_bytes, _mime_type = file_tuple
            assert isinstance(file_ref, str)
            assert isinstance(file_bytes, bytes | bytearray)
            self._files[file_ref] = bytes(file_bytes)

            # Persist to local disk so _fetch_file can read file:// URIs.
            dest = self._upload_dir / file_ref
            dest.write_bytes(self._files[file_ref])

            return TransportResponseWrapper(httpx.Response(200, json=[], request=req))

        if method == "GET" and path == f"threads/{self.thread_id}/files":
            payload = [
                {
                    "file_id": f"file-{i}",
                    "file_ref": ref,
                    "file_url": (self._upload_dir / ref).as_uri(),
                }
                for i, ref in enumerate(self._files.keys())
            ]
            return TransportResponseWrapper(httpx.Response(200, json=payload, request=req))

        if method == "GET" and path == f"threads/{self.thread_id}/file-by-ref":
            assert params is not None
            assert "file_ref" in params
            ref = params["file_ref"]
            if ref not in self._files:
                return TransportResponseWrapper(
                    httpx.Response(404, json={"detail": "not found"}, request=req)
                )
            return TransportResponseWrapper(
                httpx.Response(
                    200,
                    json={
                        "file_ref": ref,
                        "file_url": (self._upload_dir / ref).as_uri(),
                        "file_id": "file-1",
                    },
                    request=req,
                )
            )

        raise AssertionError(f"Unexpected request: {method} {path}")


class _StubDirectThreadFilesTransport:
    """Stub direct transport that implements the thread-file methods."""

    def __init__(self, upload_dir):
        self._upload_dir = upload_dir
        self._files: dict[str, bytes] = {}

    async def upload_file_bytes(
        self,
        *,
        thread_id: str,
        file_ref: str,
        content: bytes,
        mime_type: str = "text/plain",
    ) -> None:
        _ = (thread_id, mime_type)
        self._files[file_ref] = content
        (self._upload_dir / file_ref).write_bytes(content)

    async def list_file_refs(self, *, thread_id: str) -> list[str]:
        _ = thread_id
        return list(self._files.keys())

    async def get_file_url(self, *, thread_id: str, file_ref: str) -> str | None:
        _ = thread_id
        if file_ref not in self._files:
            return None
        return (self._upload_dir / file_ref).as_uri()


@pytest.mark.asyncio
async def test_file_crud_operations_with_stub_http(tmp_path):
    thread_id = "thread-123"
    transport = _StubHTTPTransport(thread_id=thread_id, upload_dir=tmp_path)
    accessor = AgentServerChatFileAccessor(thread_id=thread_id, transport=transport)

    await _assert_basic_crud(accessor)


@pytest.mark.asyncio
async def test_file_crud_operations_with_direct_transport(tmp_path):
    thread_id = "thread-123"
    direct_transport = _StubDirectThreadFilesTransport(upload_dir=tmp_path)
    accessor = AgentServerChatFileAccessor(thread_id=thread_id, transport=direct_transport)

    await _assert_basic_crud(accessor)
