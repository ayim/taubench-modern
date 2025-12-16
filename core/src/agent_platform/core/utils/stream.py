from collections.abc import AsyncGenerator

CHUNK_SIZE = 8 * 1024  # 8 KB by default


async def stream_file_contents(
    fs_path: str,
    chunk_size: int = CHUNK_SIZE,
) -> AsyncGenerator[bytes]:
    with open(fs_path, "rb") as f:
        while chunk := f.read(chunk_size):
            yield chunk
