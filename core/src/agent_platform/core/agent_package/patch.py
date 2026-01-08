"""Agent Package Patch - Create partial patches based on model differences.

This module provides functionality to create a patch ZIP containing only the files
that need to be updated based on model-level differences between a deployed Agent
and an incoming Agent Package.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING

from agent_platform.core.agent_package.handler.agent_package import AgentPackageHandler

if TYPE_CHECKING:
    from agent_platform.core.agent import Agent
    from agent_platform.core.agent_package.diff_utils.types import AgentDiffResult
    from agent_platform.core.agent_package.spec import AgentPackageSpecFileFields, SpecAgent
    from agent_platform.core.data_frames.semantic_data_model_types import SemanticDataModel


def _get_changed_file_categories(diff_result: AgentDiffResult) -> set[AgentPackageSpecFileFields]:
    """Analyze diff results and determine which file categories need to be included.

    Args:
        diff_result: The result from calculate_agent_diff.

    Returns:
        Set of file categories.
    """
    from agent_platform.core.agent_package.spec import AgentPackageSpecFileFields, SpecAgent

    categories: set[AgentPackageSpecFileFields] = set()
    for change in diff_result.changes:
        field_path = change.field_path
        # We split the field_path to extract the top-level field affected by the change,
        # so that we can group changes by their main file category (e.g., runbook, conversation_guide, etc).
        root_field = field_path.split(".")[0].split("[")[0]

        # Check for runbook changes (has its own file: runbook.md)
        if root_field in {AgentPackageSpecFileFields.runbook.name, AgentPackageSpecFileFields.runbook_structured.name}:
            categories.add(AgentPackageSpecFileFields.runbook)
            continue

        # Check for question_groups changes (has its own file: conversation-guide.yaml)
        if root_field in {
            AgentPackageSpecFileFields.question_groups.name,
            AgentPackageSpecFileFields.conversation_guide.name,
        }:
            categories.add(AgentPackageSpecFileFields.conversation_guide)
            continue

        # Check for semantic_data_models changes (has its own files: semantic-data-models/*.yaml)
        if root_field == AgentPackageSpecFileFields.semantic_data_models.name:
            categories.add(AgentPackageSpecFileFields.semantic_data_models)
            continue

        # Check for extra.* fields (go to spec)
        if field_path.startswith("extra"):
            categories.add(AgentPackageSpecFileFields.spec)
            continue

        # Check if it's a spec file field (excluding fields with separate files)
        if root_field in SpecAgent.get_fields() and root_field not in AgentPackageSpecFileFields:
            categories.add(AgentPackageSpecFileFields.spec)
            continue

    return categories


def _get_new_action_packages(
    deployed_agent: Agent,
    spec_agent: SpecAgent,
) -> set[tuple[str, str, str]]:
    """Determine which action packages are new in the deployed state.

    Compares action packages by (organization, name, version) tuple.

    Args:
        deployed_agent: The deployed agent from storage.
        spec_agent: The agent specification from the incoming package.

    Returns:
        Set of (organization, name, version) tuples for new action packages.
    """
    deployed_ap_set = {(ap.organization, ap.name, ap.version) for ap in deployed_agent.action_packages}
    incoming_ap_set = {(ap.organization, ap.name, ap.version) for ap in spec_agent.action_packages}
    return deployed_ap_set - incoming_ap_set


async def create_agent_project_patch(
    *,
    deployed_agent: Agent,
    deployed_sdms: list[SemanticDataModel],
    action_packages_uris: list[str] | None = None,
    agent_package_handler: AgentPackageHandler,
) -> AsyncGenerator[bytes, None] | None:
    """Create a patch ZIP containing only the files that differ.

    The patch contains files from the DEPLOYED state that differ from the INCOMING
    state. The client (with the incoming/local state) can then apply this patch
    to update their local files to match the deployed state.

    Action packages are only expanded from URIs when the deployed agent has new
    action packages that the incoming spec doesn't have. This avoids the cost of
    downloading/expanding action packages when they're not needed.

    Args:
        deployed_agent: The deployed agent from storage.
        deployed_sdms: The deployed semantic data models.
        action_packages_uris: Optional list of URIs pointing to action package zip files.
                             Only expanded if new action packages are detected.
        agent_package_handler: Handler for the incoming agent package (local state).

    Returns:
        AsyncGenerator yielding chunks of the patch ZIP file, or None if there are
        no differences (i.e., deployed and incoming states are in sync).
    """
    from agent_platform.core.agent_package.create import expand_action_packages_from_uris
    from agent_platform.core.agent_package.diff import calculate_agent_diff
    from agent_platform.core.agent_package.spec import AgentPackageSpecFileFields, AgentSpecGenerator

    # Extract data from incoming package for model-level comparison
    spec_agent = await agent_package_handler.get_spec_agent()
    spec_runbook = await agent_package_handler.read_runbook()
    spec_question_groups = await agent_package_handler.read_conversation_guide()
    spec_sdms = await agent_package_handler.read_all_semantic_data_models()

    # Calculate model-level diff
    diff_result = await calculate_agent_diff(
        deployed_agent=deployed_agent,
        deployed_sdms=deployed_sdms,
        spec_agent=spec_agent,
        spec_runbook=spec_runbook,
        spec_question_groups=spec_question_groups,
        spec_sdms=spec_sdms,
    )

    # Determine new action packages early (needed for both sync check and later)
    new_action_packages = _get_new_action_packages(deployed_agent, spec_agent)

    # If synced and no new action packages, return None to indicate no content
    if diff_result.is_synced and not new_action_packages:
        return None

    # We create & start writing to a new handler for the patch ZIP file
    patch_handler = AgentPackageHandler.create_empty()

    # Determine which file categories need to be included
    changed_categories = _get_changed_file_categories(diff_result)

    # Generate files from deployed state for changed categories
    if AgentPackageSpecFileFields.spec in changed_categories:
        agent_spec = AgentSpecGenerator.from_agent(
            deployed_agent,
            semantic_data_models=deployed_sdms if deployed_sdms else None,
            action_package_type="folder",
        )
        await patch_handler.write_agent_spec(agent_spec)

    # Write runbook from deployed agent
    if AgentPackageSpecFileFields.runbook in changed_categories:
        await patch_handler.write_runbook(deployed_agent.runbook_structured.raw_text)

    # Write conversation guide from deployed agent
    if AgentPackageSpecFileFields.conversation_guide in changed_categories:
        if deployed_agent.question_groups:
            await patch_handler.write_conversation_guide(deployed_agent.question_groups)

    # Write semantic data models from deployed agent
    if AgentPackageSpecFileFields.semantic_data_models in changed_categories:
        for sdm in deployed_sdms:
            sdm_name = sdm.get("name", "unknown")
            await patch_handler.write_semantic_data_model(sdm, sdm_name)

    # Write new action packages - only expand from URIs if there are new packages
    if new_action_packages and action_packages_uris:
        # Action packages are only expanded from URIs if the deployed agent has new
        # action packages that the agent package does not have
        action_packages_map = await expand_action_packages_from_uris(
            deployed_agent,
            action_packages_uris,
            filter_packages=new_action_packages,
            require_all=False,
        )

        for ap_path, ap_content in action_packages_map.items():
            await patch_handler.write_action_package(ap_path, ap_content)

    return patch_handler.to_stream()
