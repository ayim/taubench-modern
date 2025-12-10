import asyncio
import base64
import zipfile
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from tempfile import SpooledTemporaryFile
from typing import Self

from agent_platform.core.errors import ErrorCode, PlatformHTTPError

# 5 MB - arbitrary limit for the max size of a file to keep in memory.
FILE_MAX_SIZE = 1024 * 1024 * 5


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

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def close(self):
        if not self._spooled_file.closed:
            self._spooled_file.close()

    @staticmethod
    def _get_empty_spooled_file() -> SpooledTemporaryFile:
        return SpooledTemporaryFile(max_size=FILE_MAX_SIZE, mode="wb+")

    @abstractmethod
    async def validate_package_contents(self):
        pass

    async def check_if_zip(self):
        try:
            with zipfile.ZipFile(self._spooled_file, "r") as zf:
                zf.testzip()
        except (zipfile.BadZipFile, RuntimeError) as e:
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
            return zf.namelist()

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
        spooled_file = BasePackageHandler._get_empty_spooled_file()

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
        return await cls.from_bytes(base64.b64decode(data, validate=True))

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
        spooled_file = BasePackageHandler._get_empty_spooled_file()

        # Even though write() is not async, data will be initially written to RAM.
        # If the file spills into filesystem, it will be written to the OS filesystem
        # cache in RAM first and only flushed later.
        async for chunk in stream:
            spooled_file.write(chunk)

        spooled_file.flush()
        spooled_file.seek(0)

        instance = cls(spooled_file)
        await instance.validate()

        return instance
