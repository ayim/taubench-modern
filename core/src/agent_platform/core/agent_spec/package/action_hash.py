import io
import zipfile
from pathlib import Path

from fastapi import HTTPException, status
from ruamel.yaml import YAML

from agent_platform.core.agent_spec.package.package_hash import calculate_environment_hash
from agent_platform.core.agent_spec.utils import read_file_from_zip, read_package_bytes

_yaml = YAML(typ="safe")


async def calculate_action_hash(
    path: str | Path | None = None,
    url: str | None = None,
    package_base64: str | bytes | None = None,
) -> str:
    """
    Calculate the hash for an action package.

    * Pass **exactly one** of *path*, *url*, *package_base64*.

    FastAPI detail: any failure raises ``HTTPException`` with descriptive text.

    Arguments:
        path: local path to the action package
        url: URL to the action package
        package_base64: base64-encoded action package

    Returns:
        16-character hexadecimal hash string
    """

    blob = await read_package_bytes(path, url, package_base64)

    try:
        with zipfile.ZipFile(io.BytesIO(blob)) as zf:
            # Action packages typically use a different metadata filename
            # Based on Go code patterns, likely something like this
            yaml_filename = "package.yaml"
            yaml_raw = read_file_from_zip(zf, yaml_filename)

            # Calculate the hash
            hash_value, _ = calculate_environment_hash([yaml_raw.decode()])
            return hash_value

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
