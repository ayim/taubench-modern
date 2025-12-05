import io
import zipfile
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from ruamel.yaml import YAML
from starlette import status

from agent_platform.core.agent_package.config import AgentSpecConfig
from agent_platform.core.agent_package.metadata.action_metadata import ActionPackageMetadata
from agent_platform.core.agent_package.metadata.agent_metadata import AgentPackageMetadata
from agent_platform.core.agent_package.utils import read_file_from_zip, read_package_bytes

_yaml = YAML(typ="safe")


async def read_action_package_metadata(
    path: str | Path | None = None,
    url: str | None = None,
    package_base64: str | bytes | None = None,
) -> ActionPackageMetadata:
    """
    Extract the metadata from an action package.

    * Pass **exactly one** of *path*, *url*, *package_base64*.

    FastAPI detail: any failure raises ``HTTPException`` with descriptive text.

    Arguments:
        path: local path to the action package
        url: URL to the action package
        package_base64: base64-encoded action package

    Returns:
        An ActionPackageMetadata instance.
    """

    blob = await read_package_bytes(path, url, package_base64)

    try:
        with zipfile.ZipFile(io.BytesIO(blob)) as zf:
            # Action packages typically use a different metadata filename
            # Based on Go code patterns, likely something like this
            metadata_filename = "__action_server_metadata__.json"
            metadata_raw = read_file_from_zip(zf, metadata_filename)

            # Try JSON first, then YAML as fallback
            try:
                import json

                metadata_dict = json.loads(metadata_raw.decode())
            except json.JSONDecodeError:
                # Fallback to YAML if JSON fails
                metadata_dict = _yaml.load(metadata_raw.decode())

            return ActionPackageMetadata.model_validate(metadata_dict)

    except zipfile.BadZipFile as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provided bytes are not a valid zip archive",
        ) from exc
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Action package metadata file not found: {exc}",
        ) from exc


async def read_agent_package_metadata(
    path: str | Path | None = None,
    url: str | None = None,
    package_base64: str | bytes | None = None,
) -> AgentPackageMetadata:
    """
    Extract the metadata from an agent package.

    * Pass **exactly one** of *path*, *url*, *package_base64*.

    FastAPI detail: any failure raises ``HTTPException`` with descriptive text.

    Arguments:
        path: local path to the agent package
        url: URL to the agent package
        package_base64: base64-encoded agent package

    Returns:
        An AgentPackageMetadata instance.
    """
    blob = await read_package_bytes(path, url, package_base64)

    try:
        with zipfile.ZipFile(io.BytesIO(blob)) as zf:
            metadata_raw = read_file_from_zip(zf, AgentSpecConfig.metadata_filename)
            metadata: list[dict[str, Any]] = _yaml.load(metadata_raw.decode())
            return AgentPackageMetadata.model_validate(metadata[0])

    except zipfile.BadZipFile as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provided bytes are not a valid zip archive",
        ) from exc
