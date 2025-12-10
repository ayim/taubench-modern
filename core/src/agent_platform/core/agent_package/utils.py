import base64
from pathlib import Path

import httpx
from fastapi import HTTPException, status

from agent_platform.core.agent_package.config import AgentPackageConfig


async def read_package_bytes(
    path: str | Path | None,
    url: str | None,
    package_base64: str | bytes | None,
) -> bytes:
    """Load the zip file bytes, enforcing a single source."""
    expected_source_count = 1
    chosen = [path, url, package_base64].count(None)
    if chosen != (3 - expected_source_count):  # Should have exactly one source
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Specify exactly one of 'path', 'url', or 'package_base64'",
        )

    if path is not None:
        p = Path(path).expanduser()
        if not p.is_file():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"{p} not found",
            )
        return p.read_bytes()

    if url is not None:
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
                resp = await client.get(url)
                if resp.status_code != status.HTTP_200_OK:
                    raise HTTPException(
                        status_code=resp.status_code,
                        detail=f"Failed to download package: HTTP {resp.status_code}",
                    )
                if len(resp.content) > AgentPackageConfig.max_size_bytes:
                    size_in_mb = len(resp.content) / 1_000_000
                    max_size_mb = AgentPackageConfig.max_size_bytes / 1_000_000
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=(f"Package exceeds {max_size_mb:.1f}MB limit ({size_in_mb:.1f}MB)"),
                    )
                return resp.content
        except httpx.RequestError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Network error while downloading package: {exc}",
            ) from exc

    # base-64 branch
    try:
        if package_base64 is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Base-64 encoded package is required",
            )
        return base64.b64decode(package_base64)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid base-64 encoded package",
        ) from exc
