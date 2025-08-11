import io
import zipfile
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status
from ruamel.yaml import YAML

from agent_platform.core.agent_spec.config import AgentSpecConfig
from agent_platform.core.agent_spec.extract_spec import extract_agent_package_data
from agent_platform.core.agent_spec.package.package_hash import (
    blueprint_hash,
    calculate_environment_hash,
)
from agent_platform.core.agent_spec.utils import read_file_from_zip, read_package_bytes

_yaml = YAML(typ="safe")


async def calculate_agent_hash(
    path: str | Path | None = None,
    url: str | None = None,
    package_base64: str | bytes | None = None,
) -> dict[str, Any]:
    """
    Calculate the agent's actions environment hash by extracting all action packages
    and combining all their hashes into a single hash.

    * Pass **exactly one** of *path*, *url*, *package_base64*.

    Args:
        path: local path to the agent package
        url: URL to the agent package
        package_base64: base64-encoded agent package

    Returns:
        16-character hexadecimal hash string representing the combined hash of all action packages
    """
    blob = await read_package_bytes(path, url, package_base64)

    try:
        with zipfile.ZipFile(io.BytesIO(blob)) as zf:
            # Extract agent metadata to get action packages list
            spec_raw = read_file_from_zip(zf, AgentSpecConfig.agent_spec_filename)
            agent_package_parsed = await extract_agent_package_data(spec_raw, zf)

            # Calculate hash for each action package
            packages_hashes: list[str] = []

            for action_package in agent_package_parsed.action_packages:
                try:
                    # The action_package.path is a path to a zip file within the main agent package
                    # We need to read the action package zip from the main zip
                    # then read package.yaml from it

                    # Build the full path within the agent package
                    # (action packages are under "actions" folder)
                    action_package_zip_path = f"actions/{action_package.path}"

                    # Read the action package zip file from the main agent package zip
                    action_package_zip_bytes = read_file_from_zip(zf, action_package_zip_path)

                    try:
                        # Open the action package zip from bytes
                        with zipfile.ZipFile(
                            io.BytesIO(action_package_zip_bytes)
                        ) as action_package_zf:
                            # Build path to the action package's package.yaml file
                            package_yaml_path = "package.yaml"

                            # Read the package.yaml file from the action package zip
                            yaml_raw = read_file_from_zip(action_package_zf, package_yaml_path)

                            # Calculate hash for this action package
                            action_hash, _ = calculate_environment_hash([yaml_raw.decode()])
                            packages_hashes.append(action_hash)
                    except FileNotFoundError:
                        # If package.yaml is not found, skip this action package
                        # This could happen if the action package doesn't have environment
                        # dependencies
                        continue

                except FileNotFoundError:
                    # If package.yaml is not found, skip this action package
                    # This could happen if the action package doesn't have environment dependencies
                    # or if the action package is not a valid zip file
                    continue

            # Combine all action package hashes into a single agent hash
            return {
                "combined_hash": _combine_hashes(packages_hashes),
                "packages_hashes": packages_hashes,
            }

    except zipfile.BadZipFile as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provided bytes are not a valid zip archive",
        ) from exc
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Agent package metadata file not found: {exc}",
        ) from exc


def _combine_hashes(action_hashes: list[str]) -> str:
    """
    Combine multiple action package hashes into a single agent hash.

    Args:
        action_hashes: List of action package hash strings

    Returns:
        16-character hexadecimal hash string
    """
    if not action_hashes:
        return ""

    # Sort hashes to ensure deterministic ordering
    sorted_hashes = sorted(action_hashes)

    # Combine all hashes into a single string
    combined = "".join(sorted_hashes)

    # Calculate SHA256 and return first 16 characters (to match RCC hash format)
    # Convert to blueprint YAML
    blueprint_bytes = combined.encode("utf-8")

    # Calculate hash
    hash_value = blueprint_hash(blueprint_bytes)
    return hash_value
