import zipfile
from io import BytesIO
from pathlib import Path
from tempfile import SpooledTemporaryFile
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from agent_platform.core.agent_package.handler.action_package import ActionPackageHandler
from agent_platform.core.agent_package.handler.agent_package import AgentPackageHandler
from agent_platform.core.errors import ErrorCode, PlatformHTTPError


class TestPackageHandlerConstructors:
    @pytest.mark.asyncio
    async def test_agent_package_handler_from_bytes(self, test_agent_package_provider):
        zip_data = test_agent_package_provider("pass-call-center-planner.zip")

        with await AgentPackageHandler.from_bytes(zip_data) as handler:
            assert handler is not None
            await handler.check_if_zip()

    @pytest.mark.asyncio
    async def test_agent_package_handler_from_spooled_file(self, test_agent_package_provider):
        zip_data = test_agent_package_provider("pass-call-center-planner.zip")

        spooled = SpooledTemporaryFile(mode="wb+")
        spooled.write(zip_data)
        spooled.flush()
        spooled.seek(0)

        with await AgentPackageHandler.from_spooled_file(spooled) as handler:
            assert handler is not None
            await handler.check_if_zip()

    @pytest.mark.asyncio
    async def test_agent_package_handler_from_stream(self, test_agent_package_provider):
        zip_data = test_agent_package_provider("pass-call-center-planner.zip")

        async def _stream(chunk_size: int = 64 * 1024):
            for i in range(0, len(zip_data), chunk_size):
                yield zip_data[i : i + chunk_size]

        with await AgentPackageHandler.from_stream(_stream()) as handler:
            assert handler is not None
            await handler.check_if_zip()

    @pytest.mark.asyncio
    async def test_agent_package_handler_invalid_zip(self, test_agent_package_provider):
        zip_data = test_agent_package_provider("fail-incorrect-zip.zip")

        with pytest.raises(PlatformHTTPError, match="not a valid ZIP file"):
            await AgentPackageHandler.from_bytes(zip_data)


class TestURIPackageHandlerConstructors:
    @pytest.mark.asyncio
    async def test_fetch_local_action_package(self, tmp_path: Path):
        """Test fetching a local action package from the file system."""
        # Create a valid ZIP file with package.yaml inside
        test_file = tmp_path / "test_package.zip"
        package_yaml_content = b"name: Test Package\ndescription: A test action package\nversion: 1.0.0"

        with zipfile.ZipFile(test_file, "w", zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.writestr("package.yaml", package_yaml_content)

        # Construct file URI - both Windows and Unix use file:/// (three slashes)
        # On Windows: file:///C:/path/to/file
        # On Unix: file:///path/to/file
        file_path = test_file.resolve()
        file_path_posix = file_path.as_posix()

        # Construct the file URI with three slashes for absolute paths
        # On Unix, as_posix() returns /path, so file:///path works
        # On Windows, as_posix() returns C:/path, so we need file:///C:/path
        if file_path_posix.startswith("/"):
            file_uri = f"file://{file_path_posix}"
        else:
            # Windows path - add leading slash
            file_uri = f"file:///{file_path_posix}"

        with await ActionPackageHandler.from_uri(file_uri) as handler:
            # Verify the content matches
            assert handler is not None
            result_content = await handler.read_file("package.yaml")
            assert result_content == package_yaml_content
            assert len(result_content) == len(package_yaml_content)

    @pytest.mark.asyncio
    async def test_fetch_remote_action_package(self):
        """Test fetching a remote action package from HTTP URL."""
        # Create a valid ZIP file in memory with package.yaml inside
        package_yaml_content = b"name: Remote Test Package\ndescription: A remote test action package\nversion: 1.0.0"

        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.writestr("package.yaml", package_yaml_content)
        test_content = zip_buffer.getvalue()

        # Create a mock response that streams the content in chunks
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        # Create an async iterator for the test content
        async def async_chunk_generator():
            # Yield the content in chunks to simulate streaming
            chunk_size = 8 * 1024
            for i in range(0, len(test_content), chunk_size):
                yield test_content[i : i + chunk_size]

        # Mock aiter_bytes as a callable that returns our async generator
        # aiter_bytes is called with chunk_size parameter, but we'll ignore it in the mock
        mock_response.aiter_bytes = lambda chunk_size=None: async_chunk_generator()

        # Create a mock stream context manager
        mock_stream = AsyncMock()
        mock_stream.__aenter__ = AsyncMock(return_value=mock_response)
        mock_stream.__aexit__ = AsyncMock(return_value=None)

        # Create a mock client
        mock_client = MagicMock()
        mock_client.stream = MagicMock(return_value=mock_stream)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        # Mock httpx.AsyncClient to return our mock client
        with patch("agent_platform.core.agent_package.handler.base.httpx.AsyncClient") as mock_async_client:
            mock_async_client.return_value = mock_client

            test_url = "https://example.com/action-package.zip"

            with await ActionPackageHandler.from_uri(test_url) as handler:
                # Verify the mock was called correctly
                mock_async_client.assert_called_once()
                mock_client.stream.assert_called_once_with("GET", test_url)
                mock_response.raise_for_status.assert_called_once()

                # Verify the content matches
                assert handler is not None
                result_content = await handler.read_file("package.yaml")
                assert result_content == package_yaml_content
                assert len(result_content) == len(package_yaml_content)

    @pytest.mark.asyncio
    async def test_fetch_action_package_unsupported_scheme(self):
        """Test that an error is raised when an unsupported URI scheme is used."""
        # Test with an unsupported scheme (e.g., ftp://)
        unsupported_uri = "ftp://example.com/package.zip"

        with pytest.raises(PlatformHTTPError) as exc_info:
            with await ActionPackageHandler.from_uri(unsupported_uri):
                pass  # This line should not be reached

        assert exc_info.value.response.error_code == ErrorCode.UNPROCESSABLE_ENTITY
        assert "Unsupported URI scheme: ftp" in str(exc_info.value)
        assert "in package" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_fetch_action_package_invalid_uri(self):
        """Test that an error is raised when an invalid URI is provided."""
        # Use an invalid IPv6 URL format that causes urlparse to raise ValueError
        invalid_uri = "http://[invalid"

        with pytest.raises(PlatformHTTPError) as exc_info:
            with await ActionPackageHandler.from_uri(invalid_uri):
                pass  # This line should not be reached

        assert exc_info.value.response.error_code == ErrorCode.UNPROCESSABLE_ENTITY
        assert "Invalid package URI" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_fetch_local_action_package_file_not_found(self, tmp_path: Path):
        """Test that FileNotFoundError is raised when file doesn't exist."""
        # Create a file URI for a non-existent file
        non_existent_file = tmp_path / "non_existent.zip"
        file_path = non_existent_file.resolve()
        file_path_posix = file_path.as_posix()

        if file_path_posix.startswith("/"):
            file_uri = f"file://{file_path_posix}"
        else:
            file_uri = f"file:///{file_path_posix}"

        with pytest.raises(PlatformHTTPError) as exc_info:
            with await ActionPackageHandler.from_uri(file_uri):
                pass  # This line should not be reached

        assert exc_info.value.response.error_code == ErrorCode.UNPROCESSABLE_ENTITY
        assert "Package file not found at path" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_fetch_local_action_package_is_directory(self, tmp_path: Path):
        """Test that an error is raised when path is a directory.

        Note: On Windows, this raises PermissionError, while on Unix it raises IsADirectoryError.
        Both are handled and converted to PlatformHTTPError with appropriate messages.
        """
        # Create a directory and use it as the URI
        test_dir = tmp_path / "test_dir"
        test_dir.mkdir()
        file_path = test_dir.resolve()
        file_path_posix = file_path.as_posix()

        if file_path_posix.startswith("/"):
            file_uri = f"file://{file_path_posix}"
        else:
            file_uri = f"file:///{file_path_posix}"

        with pytest.raises(PlatformHTTPError) as exc_info:
            with await ActionPackageHandler.from_uri(file_uri):
                pass  # This line should not be reached

        assert exc_info.value.response.error_code == ErrorCode.UNPROCESSABLE_ENTITY
        # On Windows, this raises PermissionError, on Unix it raises IsADirectoryError
        # Both are valid - we just need to ensure an error is raised
        error_message = str(exc_info.value)
        assert (
            "Package path is a directory, not a file" in error_message
            or "Permission denied" in error_message
            or "Failed to read package file" in error_message
        )

    @pytest.mark.asyncio
    async def test_fetch_remote_action_package_timeout_error(self):
        """Test that httpx.ReadTimeout (a RequestError) is properly handled."""
        test_url = "https://example.com/action-package.zip"

        # Create a mock that raises httpx.ReadTimeout (a subclass of RequestError)
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        # Create a mock stream that raises ReadTimeout
        mock_stream = AsyncMock()
        timeout_error = httpx.ReadTimeout("Read timeout", request=MagicMock())
        mock_stream.__aenter__ = AsyncMock(side_effect=timeout_error)
        mock_stream.__aexit__ = AsyncMock(return_value=None)

        mock_client.stream = MagicMock(return_value=mock_stream)

        with patch("agent_platform.core.agent_package.handler.base.httpx.AsyncClient") as mock_async_client:
            mock_async_client.return_value = mock_client

            with pytest.raises(PlatformHTTPError) as exc_info:
                with await ActionPackageHandler.from_uri(test_url):
                    pass  # This line should not be reached

            assert exc_info.value.response.error_code == ErrorCode.UNPROCESSABLE_ENTITY
            assert "Failed to stream package file from URI" in str(exc_info.value)
            assert test_url in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_fetch_remote_action_package_connection_error(self):
        """Test that connection errors (RequestError) are properly handled."""
        test_url = "https://example.com/action-package.zip"

        # Create a mock that raises httpx.ConnectError (a subclass of RequestError)
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        # Create a mock stream that raises ConnectError
        mock_stream = AsyncMock()
        connection_error = httpx.ConnectError("Connection refused", request=MagicMock())
        mock_stream.__aenter__ = AsyncMock(side_effect=connection_error)
        mock_stream.__aexit__ = AsyncMock(return_value=None)

        mock_client.stream = MagicMock(return_value=mock_stream)

        with patch("agent_platform.core.agent_package.handler.base.httpx.AsyncClient") as mock_async_client:
            mock_async_client.return_value = mock_client

            with pytest.raises(PlatformHTTPError) as exc_info:
                with await ActionPackageHandler.from_uri(test_url):
                    pass  # This line should not be reached

            assert exc_info.value.response.error_code == ErrorCode.UNPROCESSABLE_ENTITY
            assert "Failed to stream package file from URI" in str(exc_info.value)
            assert test_url in str(exc_info.value)
