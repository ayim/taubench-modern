from typing import Any

from ruamel.yaml import YAML

from agent_platform.core.agent_package.handler.action_package import ActionPackageHandler
from agent_platform.core.agent_package.handler.agent_package import AgentPackageHandler
from agent_platform.core.agent_package.hash.blueprint_hash import blueprint_hash
from agent_platform.core.agent_package.hash.environment_hash import calculate_environment_hash

_yaml = YAML(typ="safe")


async def calculate_agent_package_hash(handler: AgentPackageHandler) -> dict[str, Any]:
    """
    Calculate the agent's actions environment hash by extracting all action packages
    and combining all their hashes into a single hash.

    Args:
        handler: AgentPackageHandler

    Returns:
        16-character hexadecimal hash string representing the combined hash of all action packages
    """

    spec_agent = await handler.get_spec_agent()

    # Calculate hash for each action package
    packages_hashes: list[str] = []

    for action_package in spec_agent.action_packages:
        try:
            if not action_package.path:
                continue

            # The action_package.path is a path to a zip file within the main agent package
            # We need to read the action package zip from the main zip
            # then read package.yaml from it
            action_packages_zip_bytes = await handler.read_action_package_zip_raw(action_package.path)

            with await ActionPackageHandler.from_bytes(action_packages_zip_bytes) as action_package_handler:
                try:
                    yaml_raw = await action_package_handler.read_package_spec_raw()

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
