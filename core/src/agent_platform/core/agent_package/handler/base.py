import asyncio
import base64
import io
import os
import zipfile
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from tempfile import SpooledTemporaryFile
from typing import Self

import httpx
import structlog
from ruamel.yaml import YAML

from agent_platform.core.agent_package.config import AgentPackageConfig
from agent_platform.core.errors import ErrorCode, PlatformHTTPError
from agent_platform.core.utils.stream import CHUNK_SIZE, stream_file_contents

logger = structlog.get_logger(__name__)

# PackageContent is a dictionary mapping file paths to their content.
# Example: {"package.yaml": b"...", "actions.py": b"...", ...}
PackageFilePath = str
PackageFileContent = bytes
PackageContent = dict[PackageFilePath, PackageFileContent]

# 5 MB - arbitrary limit for the max size of a file to keep in memory.
FILE_MAX_SIZE = 1024 * 1024 * 5


class YAMLHandler:
    @property
    def reader(self) -> YAML:
        """Get a configured YAML reader instance for deserialization.

        Returns:
            A YAML reader instance.
        """
        return YAML(typ="safe")

    @property
    def writer(self) -> YAML:
        """Get a configured YAML writer instance for serialization.

        Creates a new instance each time to avoid mutable state issues
        when multiple operations modify YAML settings.
        """
        yaml = YAML(typ="safe")
        yaml.default_flow_style = False
        return yaml


class BasePackageHandler(ABC):
    """
    Handles read and write operations on a temporary spooled zip.
    It uses `SpooledTemporaryFile` as an underlying storage, which uses RAM storage
    by default and moves to disk when the file exceeds a certain size.

    BasePackageHandler can be created from byte data, base64 or async stream (AsyncGenerator).
    It supports a "with" clause, which will close the underlying spooled file upon exiting.
    """

    def __init__(self, spooled_file: SpooledTemporaryFile):
        self._spooled_file = spooled_file
        self._spooled_zip_writer: zipfile.ZipFile | None = None
        self._write_lock = asyncio.Lock()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def close(self):
        if self._spooled_zip_writer is not None:
            self._spooled_zip_writer.close()
            self._spooled_zip_writer = None
        if not self._spooled_file.closed:
            self._spooled_file.close()

    def get_spooled_file_size(self) -> int:
        """Returns the size of the spooled file in bytes."""
        self._spooled_file.seek(0, io.SEEK_END)
        size = self._spooled_file.tell()
        self._spooled_file.seek(0)

        return size

    @staticmethod
    def get_empty_spooled_file() -> SpooledTemporaryFile:
        return SpooledTemporaryFile(max_size=FILE_MAX_SIZE, mode="wb+")

    @staticmethod
    def _validate_package_size(package_size: int):
        if package_size > AgentPackageConfig.max_size_bytes:
            size_in_mb = package_size / 1_000_000
            max_size_mb = AgentPackageConfig.max_size_bytes / 1_000_000
            raise PlatformHTTPError(
                error_code=ErrorCode.UNPROCESSABLE_ENTITY,
                message=f"Package exceeds {max_size_mb:.1f}MB limit ({size_in_mb:.1f}MB)",
            )

    @abstractmethod
    async def validate_package_contents(self):
        pass

    async def check_if_zip(self):
        try:
            with zipfile.ZipFile(self._spooled_file, "r") as zf:
                zf.testzip()
        except (zipfile.BadZipFile, RuntimeError) as e:
            logger.error("Package is not a valid ZIP file", error=str(e))
            raise PlatformHTTPError(
                error_code=ErrorCode.UNPROCESSABLE_ENTITY,
                message="Agent Package is not a valid ZIP file",
            ) from e

    async def read_file(self, file_path: str) -> bytes:
        with zipfile.ZipFile(self._spooled_file, "r") as zf:
            file_data = await asyncio.to_thread(lambda: zf.read(file_path))
            return file_data

    async def list_files(self) -> list[str]:
        with zipfile.ZipFile(self._spooled_file, "r") as zf:
            file_list = zf.namelist()
            return file_list

    async def file_exists(self, file_path: str) -> bool:
        return file_path in await self.list_files()

    async def validate(self):
        """
        Checks if the Package is a valid ZIP file and runs Package-specific validation,
        implemented in subclasses.

        If not, an exception is raised (appropriate for a failed check).
        """
        await self.check_if_zip()
        await self.validate_package_contents()

    @classmethod
    def create_empty(cls) -> Self:
        """Create an empty handler.

        Unlike from_bytes/from_stream, this does not validate the package contents,
        making it suitable for constructing new packages from scratch.

        Returns:
            Handler instance ready for writing files.
        """
        spooled_file = cls.get_empty_spooled_file()
        return cls(spooled_file)

    @classmethod
    async def from_spooled_file(cls, spooled_file: SpooledTemporaryFile) -> Self:
        instance = cls(spooled_file)
        await instance.validate()
        return instance

    @classmethod
    async def from_bytes(cls, data: bytes) -> Self:
        """Create AgentPackageHandler from byte data.

        Args:
            data: Byte data of Agent Package zip.

        Returns:
            AgentPackageHandler instance.
        """
        spooled_file = cls.get_empty_spooled_file()

        await asyncio.to_thread(lambda: spooled_file.write(data))

        # Making sure the contents land in the file (if spilled into the disc)
        # before allowing clients to interact with it.
        spooled_file.flush()
        spooled_file.seek(0)

        instance = cls(spooled_file)
        await instance.validate()
        return instance

    # @deprecated
    # base64 should be dropped as one of the ingress ways of uploading Packages.
    # This is kept here just for backward compatibility.
    # DO NOT USE FOR NEW ENDPOINTS!
    @classmethod
    async def from_base64(cls, data: str) -> Self:
        """
        @deprecated
        Constructs an instance of AgentPackageHandler from a base64-encoded string.

        Args:
            data: base64 string encoding an Agent Package zip.

        Returns:
            AgentPackageHandler instance.
        """
        try:
            return await cls.from_bytes(base64.b64decode(data, validate=True))
        except Exception as exc:
            raise PlatformHTTPError(
                error_code=ErrorCode.UNPROCESSABLE_ENTITY,
                message=f"Failed to decode base64 Package: {exc}",
            ) from exc

    @classmethod
    async def from_stream(cls, stream: AsyncGenerator[bytes, None]) -> Self:
        """
        Creates an instance of `AgentPackageHandler` asynchronously by reading data
        from the provided asynchronous byte stream.

        Args:
            stream: AsyncGenerator stream of bytes.

        Returns:
            AgentPackageHandler instance.
        """
        spooled_file = cls.get_empty_spooled_file()

        # Even though write() is not async, data will be initially written to RAM.
        # If the file spills into filesystem, it will be written to the OS filesystem
        # cache in RAM first and only flushed later.
        total_bytes = 0
        async for chunk in stream:
            total_bytes += len(chunk)
            cls._validate_package_size(total_bytes)
            spooled_file.write(chunk)

        spooled_file.flush()
        spooled_file.seek(0)

        instance = cls(spooled_file)
        await instance.validate()
        return instance

    async def to_stream(self, chunk_size: int = CHUNK_SIZE) -> AsyncGenerator[bytes, None]:
        """Stream the zip file contents as chunks.

        This is useful for streaming responses where we don't want to load
        the entire package into memory at once.

        Args:
            chunk_size: Size of each chunk to yield. Defaults to 8KB.

        Yields:
            Bytes chunks from the zip file.
        """
        self.flush_writer()

        self._spooled_file.seek(0)
        total_bytes = 0
        while chunk := self._spooled_file.read(chunk_size):
            total_bytes += len(chunk)
            yield chunk

    @classmethod
    async def from_file_path(cls, fs_path: str) -> Self:
        """
        Creates a package handler from the given FS path.

        Args:
            fs_path: The filesystem path of the package.

        Returns:
            A BasePackageHandler object.

        Raises:
            PlatformHTTPError: If the file cannot be accessed, file is too large or the file read
            fails.
        """
        try:
            # Validate file size before streaming
            file_size = await asyncio.to_thread(os.path.getsize, fs_path)
            cls._validate_package_size(file_size)
            return await cls.from_stream(stream_file_contents(fs_path))
        except FileNotFoundError:
            logger.error("Package file not found")
            raise PlatformHTTPError(
                error_code=ErrorCode.UNPROCESSABLE_ENTITY,
                message=f"Package file not found at path: {fs_path}",
            ) from None
        except PermissionError:
            logger.error("Permission denied reading package file")
            raise PlatformHTTPError(
                error_code=ErrorCode.UNPROCESSABLE_ENTITY,
                message=f"Permission denied reading package file at path: {fs_path}",
            ) from None
        except IsADirectoryError:
            logger.error("Package path is a directory, not a file")
            raise PlatformHTTPError(
                error_code=ErrorCode.UNPROCESSABLE_ENTITY,
                message=f"Package path is a directory, not a file: {fs_path}",
            ) from None
        except OSError as e:
            logger.error("Failed to read package file", error=str(e))
            raise PlatformHTTPError(
                error_code=ErrorCode.UNPROCESSABLE_ENTITY,
                message=f"Failed to read package file at path: {fs_path}. Error: {e}",
            ) from e

    @classmethod
    async def from_url(cls, url: str) -> Self:
        """
        Fetches the package contents from the given URL and returns a BasePackageHandler object.

        Args:
            url: The URL of the package.

        Returns:
            A BasePackageHandler object.

        Raises:
            PlatformHTTPError: If the package is too large or the package cannot be read from the
            URL.
        """
        try:
            async with httpx.AsyncClient() as client:
                async with client.stream("GET", url) as response:
                    response.raise_for_status()

                    # Check Content-Length header if available
                    content_length = response.headers.get("Content-Length")
                    if content_length:
                        try:
                            package_size = int(content_length)
                            cls._validate_package_size(package_size)
                        except ValueError:
                            # Content-Length header is not a valid integer, ignore it
                            logger.error("Content-Length header is not a valid integer, ignoring")

                    # Convert async iterator to async generator for from_stream
                    async def stream_generator() -> AsyncGenerator[bytes, None]:
                        async for chunk in response.aiter_bytes(chunk_size=CHUNK_SIZE):
                            yield chunk

                    return await cls.from_stream(stream_generator())
        except httpx.RequestError as e:
            logger.error("Failed to stream package file from URL", error=str(e))
            raise PlatformHTTPError(
                error_code=ErrorCode.UNPROCESSABLE_ENTITY,
                message=f"Failed to stream package file from URI: {url}. Error: {e}",
            ) from e
        except httpx.HTTPStatusError as e:
            code = e.response.status_code
            logger.error("Failed to fetch package file from URL", http_status=code)
            raise PlatformHTTPError(
                error_code=ErrorCode.UNPROCESSABLE_ENTITY,
                message=f"Failed to fetch package file from URI: {url}. HTTP error: {code}",
            ) from e

    @classmethod
    async def from_uri(cls, uri: str) -> Self:
        """
        Fetches the package contents from the given URI and returns a BasePackageHandler object.

        Supports file://, http://, and https:// URI schemes.

        Args:
            uri: The URI of the action package.

        Returns:
            A BasePackageHandler object.

        Raises:
            PlatformHTTPError: If the URI scheme is not supported, the URI is invalid or
            package read fails.
        """
        from urllib.parse import urlparse

        try:
            parsed = urlparse(uri)
        except ValueError as e:
            logger.error("Invalid package URI", error=str(e))
            raise PlatformHTTPError(
                error_code=ErrorCode.UNPROCESSABLE_ENTITY,
                message=f"Invalid package URI: {e}",
            ) from e

        if parsed.scheme == "file":
            from agent_platform.server.file_manager.utils import url_to_fs_path

            # Convert file:// URI to filesystem path, handling Windows paths correctly
            fs_path = url_to_fs_path(uri)
            return await cls.from_file_path(fs_path)
        elif parsed.scheme in ("http", "https"):
            return await cls.from_url(parsed.geturl())
        else:
            logger.error("Unsupported URI scheme", scheme=parsed.scheme)
            raise PlatformHTTPError(
                error_code=ErrorCode.UNPROCESSABLE_ENTITY,
                message=f"Unsupported URI scheme: {parsed.scheme} in package",
            )

    async def _read_existing_zip_files(self) -> PackageContent:
        """
        Read all files from the existing zip in the spooled file.

        Returns:
            Dictionary mapping filenames to their content bytes.
            Returns empty dict if spooled file is empty or not a valid zip.
        """

        def _read_files_sync() -> PackageContent:
            # Check if there's existing content in the spooled file
            content_size = self.get_spooled_file_size()

            if content_size == 0:
                return {}

            try:
                with zipfile.ZipFile(self._spooled_file, "r") as existing_zip:
                    files = {filename: existing_zip.read(filename) for filename in existing_zip.namelist()}
                    return files
            except (zipfile.BadZipFile, RuntimeError) as e:
                # If it's not a valid zip, ignore and start fresh
                logger.error("Could not read existing zip content, starting fresh", error=str(e))
                return {}

        return await asyncio.to_thread(_read_files_sync)

    async def _create_new_zip_writer(self, preserve_files: PackageContent) -> zipfile.ZipFile:
        """
        Create a new ZIP writer, optionally preserving existing files.

        Args:
            preserve_files: Dictionary of files to preserve in the new zip.

        Returns:
            New ZipFile writer instance.
        """

        def _create_writer_sync() -> zipfile.ZipFile:
            # Create new ZIP writer (overwrites spooled file)
            self._spooled_file.seek(0)
            self._spooled_file.truncate()
            writer = zipfile.ZipFile(self._spooled_file, mode="w", compression=zipfile.ZIP_DEFLATED)

            # Copy preserved files to the new zip
            if preserve_files:
                for filename, content in preserve_files.items():
                    writer.writestr(filename, content)

            return writer

        return await asyncio.to_thread(_create_writer_sync)

    async def _get_spooled_zip_writer(self) -> zipfile.ZipFile:
        """
        Get or create a ZipFile writer for the spooled file.

        If there's existing content, preserves it by copying files to the new ZIP.
        """
        if self._spooled_zip_writer is None:
            existing_files = await self._read_existing_zip_files()
            self._spooled_zip_writer = await self._create_new_zip_writer(existing_files)
        return self._spooled_zip_writer

    async def write_file(self, filename: str, content: bytes | str) -> None:
        """
        Write a file to the internal zip archive.

        Works for both new ZIPs and existing ZIPs loaded via from_bytes/from_stream.
        If a file with the same name exists, it will be replaced.

        This method is protected by a lock to ensure thread-safe writes when called
        concurrently, as ZipFile is not thread-safe for writing.

        Args:
            filename: The path/name of the file within the zip.
            content: The content to write (bytes or string).
        """
        async with self._write_lock:
            self._spooled_zip_writer = await self._get_spooled_zip_writer()
            await asyncio.to_thread(self._spooled_zip_writer.writestr, filename, content)

    def flush_writer(self) -> None:
        """
        Flush and close the zip writer to make written files readable.

        This should be called after writing files and before trying to read them back.
        Note: Subsequent writes will trigger content preservation to avoid data loss.
        """
        if self._spooled_zip_writer is not None:
            self._spooled_zip_writer.close()
            self._spooled_zip_writer = None

    def to_zip_bytes(self) -> bytes:
        """Get the complete zip file as bytes."""
        if self._spooled_zip_writer is not None:
            self._spooled_zip_writer.close()
            self._spooled_zip_writer = None

        self._spooled_file.seek(0)
        zip_bytes = self._spooled_file.read()
        return zip_bytes
