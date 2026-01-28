from collections.abc import AsyncGenerator

import structlog

from agent_platform.core.agent import Agent
from agent_platform.core.agent_package.handler.action_package import ActionPackageHandler as ActionPackageHandlerForURI
from agent_platform.core.agent_package.handler.action_package import ActionPackageMap
from agent_platform.core.agent_package.handler.agent_package import AgentPackageHandler
from agent_platform.core.agent_package.spec import AgentSpecGenerator
from agent_platform.core.data_frames.semantic_data_model_types import SemanticDataModel

logger = structlog.get_logger(__name__)


async def expand_action_packages_from_uris(
    agent: Agent,
    action_packages_uris: list[str],
    *,
    filter_packages: set[tuple[str, str, str]] | None = None,
    require_all: bool = True,
) -> ActionPackageMap:
    """Expand action packages from a list of URIs.

    Each URI points to an action package zip file. Supported URI schemes:
    - file://path/to/action_package.zip
    - http://example.com/action_package.zip
    - https://example.com/action_package.zip

    The action packages are matched to the agent's action package definitions by name
    and version. The organization is taken from the agent's definition since action
    packages don't contain organization information in their metadata.

    Args:
        agent: The agent to extract action packages for. Used to match action packages
               by name/version and provide organization info.
        action_packages_uris: List of URIs pointing to action package zip files.
        filter_packages: Optional set of (organization, name, version) tuples. If provided,
                        only action packages matching these tuples will be expanded.
                        Packages not in this set will be skipped.
        require_all: If True (default), validates that all agent action packages are present
                    in the URIs. If False, missing packages are allowed.

    Returns:
        A dictionary mapping action package paths to their expanded contents.
        Each action package's contents is a dict mapping file paths to their bytes.
        Example: {"Sema4.ai/browsing": {"package.yaml": b"...", "actions.py": b"...", ...}}

    Raises:
        PlatformHTTPError: If a URI is invalid, the package cannot be fetched,
                          the package can't be matched to an agent action package,
                          or (when require_all=True) required action packages are missing.
    """
    from agent_platform.core.agent_package.utils import create_action_package_path
    from agent_platform.core.errors import ErrorCode, PlatformHTTPError

    # If no URIs provided, return empty map
    if not action_packages_uris:
        logger.warning("No action package URIs provided, empty map between agent and action packages")
        return {}

    # Build a lookup map for agent's action packages by (name, version)
    # The organization is stored in the agent's action package definition, not the package metadata
    agent_ap_lookup: dict[tuple[str, str], tuple[str, str, str]] = {}
    for ap in agent.action_packages:
        key = (ap.name, ap.version)
        agent_ap_lookup[key] = (ap.organization, ap.name, ap.version)

    action_packages_map: ActionPackageMap = {}
    matched_keys: set[tuple[str, str]] = set()

    for uri in action_packages_uris:
        # Use ActionPackageHandler.from_uri to fetch the package
        with await ActionPackageHandlerForURI.from_uri(uri) as handler:
            # Read package.yaml to get name and version
            # package.yaml is guaranteed to have the correct version, unlike metadata
            # which may be missing action_package_version in older Action Server packages
            try:
                package_spec = await handler.read_package_spec()
                name = package_spec.name or None
                version = package_spec.version or None
                if not name or not version:
                    raise PlatformHTTPError(
                        error_code=ErrorCode.UNPROCESSABLE_ENTITY,
                        message=f"Invalid action package spec (package.yaml) from '{uri}'",
                    )
            except Exception as e:
                logger.error(
                    "Failed to read action package spec",
                    uri=uri,
                    error=str(e),
                )
                raise PlatformHTTPError(
                    error_code=ErrorCode.UNPROCESSABLE_ENTITY,
                    message=f"Failed to read action package spec from '{uri}': {e}",
                ) from e

            # Match this action package to an agent's action package definition
            lookup_key = (name, version)
            if lookup_key not in agent_ap_lookup:
                logger.error(
                    "Action package not found in agent definition",
                    uri=uri,
                    name=name,
                    version=version,
                )
                raise PlatformHTTPError(
                    error_code=ErrorCode.UNPROCESSABLE_ENTITY,
                    message=(
                        f"Action package '{name}' (version {version}) from URI '{uri}' "
                        "is not defined in the agent's action packages."
                    ),
                )

            organization, matched_name, matched_version = agent_ap_lookup[lookup_key]

            # If filtering is enabled, skip packages not in the filter set
            if filter_packages is not None:
                if (organization, matched_name, matched_version) not in filter_packages:
                    logger.debug(
                        "Skipping action package not in filter set",
                        uri=uri,
                        organization=organization,
                        name=matched_name,
                        version=matched_version,
                    )
                    continue

            matched_keys.add(lookup_key)

            # Create folder-style path using the organization from the agent definition
            action_package_folder_path = create_action_package_path(
                "folder", organization, matched_name, matched_version
            )

            # Read all files from the action package (files in nested folders are included)
            file_list = await handler.list_files()
            expanded_contents: dict[str, bytes] = {}

            for file_path in file_list:
                # Skip directory entries (they end with /), only read actual files
                # Files in nested folders like "folder/subfolder/file.py" are still read
                if not file_path.endswith("/"):
                    file_content = await handler.read_file(file_path)
                    expanded_contents[file_path] = file_content

            action_packages_map[action_package_folder_path] = expanded_contents

    # Validate that all action packages defined in the agent are present (unless filtering)
    if require_all and filter_packages is None:
        required_keys = set(agent_ap_lookup.keys())
        missing_keys = required_keys - matched_keys
        if missing_keys:
            missing_descriptions = [f"{name} (version {version})" for name, version in sorted(missing_keys)]
            logger.error(
                "Missing required action packages",
                missing_count=len(missing_keys),
                missing=missing_descriptions,
            )
            raise PlatformHTTPError(
                error_code=ErrorCode.UNPROCESSABLE_ENTITY,
                message=f"Missing required action packages: {', '.join(missing_descriptions)}",
            )
    return action_packages_map


async def create_agent_project_zip(
    agent: Agent, semantic_data_models: list[SemanticDataModel], action_packages_map: ActionPackageMap | None = None
) -> AsyncGenerator[bytes, None]:
    """
    Create an agent project zip file from an agent and semantic data models.

    Args:
        agent: The agent to generate the zip file for.
        semantic_data_models: The semantic data models to include in the zip file.

    Returns:
        The zip file bytes.
    """
    # Generate agent-spec.yaml with semantic data models
    agent_spec = AgentSpecGenerator.from_agent(
        agent, semantic_data_models=semantic_data_models if semantic_data_models else None, action_package_type="folder"
    )

    # Create a handler with a spooled file for building the package
    spooled_file = AgentPackageHandler.get_empty_spooled_file()
    handler = AgentPackageHandler(spooled_file)

    # Write semantic data models
    for sdm in semantic_data_models:
        sdm_filename = sdm.name or "unknown"
        await handler.write_semantic_data_model(sdm, sdm_filename)

    # Write all content to the handler's zip file
    await handler.write_agent_spec(agent_spec)
    await handler.write_runbook(agent.runbook_structured.raw_text)
    await handler.write_conversation_guide(agent.question_groups)

    # Write action packages
    if action_packages_map:
        for action_package_path, action_package_content in action_packages_map.items():
            await handler.write_action_package(action_package_path, action_package_content)

    return handler.to_stream()
