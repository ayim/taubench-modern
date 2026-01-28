"""Agent Package Diff - Compare SpecAgent with deployed Agent.

This module provides functionality to calculate differences between an Agent Package
specification and a Deployed Agent by:
1. Converting SpecAgent to an Agent object
2. Using jsondiff to compare the two Agent model_dumps
3. Converting the jsondiff output to a structured list of DiffResult entries
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog
from jsondiff import diff, symbols

from agent_platform.core.agent_package.diff_utils.types import AgentDiffResult, DiffResult
from agent_platform.core.agent_package.spec import AgentSpecGenerator

if TYPE_CHECKING:
    from agent_platform.core.agent import Agent
    from agent_platform.core.agent.question_group import QuestionGroup
    from agent_platform.core.agent_package.spec import AgentSpecGenerator, SpecAgent
    from agent_platform.core.data_frames.semantic_data_model_types import SemanticDataModel

logger = structlog.get_logger(__name__)

# Fields to exclude from comparison (identity/timestamp fields, reference IDs)
EXCLUDED_FIELDS = frozenset(
    {
        "agent_id",
        "user_id",
        "created_at",
        "updated_at",
        "mcp_server_ids",
        "platform_params_ids",
        "platform_configs",
        "observability_configs",
    }
)


def _normalize_for_comparison(agent_dict: dict[str, Any]) -> dict[str, Any]:
    """Normalize an agent dict for comparison.

    Removes excluded fields and extracts comparable runbook content.

    Args:
        agent_dict: The agent model_dump to normalize.

    Returns:
        Normalized dict suitable for comparison.
    """
    result = {k: v for k, v in agent_dict.items() if k not in EXCLUDED_FIELDS}

    # Only compare runbook raw_text (not content/updated_at which would cause false diffs)
    if "runbook_structured" in result:
        runbook = result.pop("runbook_structured")
        result["runbook"] = runbook.get("raw_text", "") if isinstance(runbook, dict) else ""

    # Remove runtime-specific fields from action_packages (url is set by client for Action Server connectivity)
    # Package should not contain the url field, so we remove it from the comparison.
    if result.get("action_packages"):
        result["action_packages"] = [
            {k: v for k, v in ap.items() if k not in ("url", "api_key")} for ap in result["action_packages"]
        ]

    # Normalize equivalent architecture names
    # agent_platform.architectures.default and agent_platform.architectures.agent are equivalent
    if result.get("agent_architecture") and isinstance(result["agent_architecture"], dict):
        arch_name = result["agent_architecture"].get("name", "")
        if arch_name in ("agent_platform.architectures.default", "agent_platform.architectures.agent"):
            result["agent_architecture"]["name"] = "agent_platform.architectures.default"
        # Remove architecture version from comparison (not part of spec, always defaults to 1.0.0)
        result["agent_architecture"].pop("version", None)

    # Normalize extra.enable_data_frames: None/missing is equivalent to True (default value)
    if "extra" in result and isinstance(result["extra"], dict):
        if result["extra"].get("enable_data_frames") is None:
            result["extra"]["enable_data_frames"] = True
        # Normalize empty strings to None in extra dict (treated as equivalent "no value")
        result["extra"] = {k: (None if v == "" else v) for k, v in result["extra"].items()}

    # Remove None values recursively - jsondiff treats "key: None" differently from "missing key"
    # but for our purposes they should be equivalent
    result = _strip_none_values(result)

    return result


def _strip_none_values(obj: Any) -> Any:
    """Recursively remove None values from dicts.

    This ensures jsondiff doesn't report differences between:
    - {"key": None} and {}
    - {"nested": {"key": None}} and {"nested": {}}
    """
    if isinstance(obj, dict):
        return {k: _strip_none_values(v) for k, v in obj.items() if v is not None}
    elif isinstance(obj, list):
        return [_strip_none_values(item) for item in obj]
    return obj


def _jsondiff_to_diff_results(
    diff_result: dict[Any, Any],
    path_prefix: str = "",
) -> list[DiffResult]:
    """Convert jsondiff output to a list of DiffResult entries.

    Recursively walks the jsondiff structure and creates DiffResult entries
    with dot-notation field paths.

    Args:
        diff_result: The output from jsondiff.diff with syntax='symmetric'.
        path_prefix: Current path prefix for nested fields.

    Returns:
        List of DiffResult entries.
    """
    changes: list[DiffResult] = []

    if not isinstance(diff_result, dict):
        return changes

    for key, value in diff_result.items():
        if key == symbols.insert:
            # Inserted items - can be dict for object keys or list for array items
            if isinstance(value, dict):
                for inserted_key, inserted_value in value.items():
                    field_path = f"{path_prefix}.{inserted_key}" if path_prefix else str(inserted_key)
                    changes.append(
                        DiffResult(
                            change="add",
                            field_path=field_path,
                            deployed_value=None,
                            package_value=inserted_value,
                        )
                    )
            elif isinstance(value, list):
                # Array insertions: [(index, value), ...]
                for item in value:
                    if isinstance(item, tuple) and len(item) == 2:
                        idx, inserted_value = item
                        field_path = f"{path_prefix}[{idx}]" if path_prefix else f"[{idx}]"
                        changes.append(
                            DiffResult(
                                change="add",
                                field_path=field_path,
                                deployed_value=None,
                                package_value=inserted_value,
                            )
                        )
        elif key == symbols.delete:
            # Deleted items - can be dict for object keys or list for array items
            if isinstance(value, dict):
                for deleted_key, deleted_value in value.items():
                    field_path = f"{path_prefix}.{deleted_key}" if path_prefix else str(deleted_key)
                    changes.append(
                        DiffResult(
                            change="delete",
                            field_path=field_path,
                            deployed_value=deleted_value,
                            package_value=None,
                        )
                    )
            elif isinstance(value, list):
                # Array deletions: [(index, value), ...] or [value, ...]
                for item in value:
                    if isinstance(item, tuple) and len(item) == 2:
                        idx, deleted_value = item
                        field_path = f"{path_prefix}[{idx}]" if path_prefix else f"[{idx}]"
                    else:
                        # Just the value without index
                        field_path = path_prefix
                        deleted_value = item
                    changes.append(
                        DiffResult(
                            change="delete",
                            field_path=field_path,
                            deployed_value=deleted_value,
                            package_value=None,
                        )
                    )
        elif isinstance(key, int):
            # Array index change
            field_path = f"{path_prefix}[{key}]" if path_prefix else f"[{key}]"
            if isinstance(value, list):
                # Symmetric diff: [old_value, new_value]
                old_val, new_val = value
                changes.append(
                    DiffResult(
                        change="update",
                        field_path=field_path,
                        deployed_value=old_val,
                        package_value=new_val,
                    )
                )
            elif isinstance(value, dict):
                # Nested changes in array item
                changes.extend(_jsondiff_to_diff_results(value, field_path))
        elif isinstance(value, list):
            # Symmetric diff: [old_value, new_value]
            field_path = f"{path_prefix}.{key}" if path_prefix else str(key)
            old_val, new_val = value
            changes.append(
                DiffResult(
                    change="update",
                    field_path=field_path,
                    deployed_value=old_val,
                    package_value=new_val,
                )
            )
        elif isinstance(value, dict):
            # Nested dict with changes
            field_path = f"{path_prefix}.{key}" if path_prefix else str(key)
            changes.extend(_jsondiff_to_diff_results(value, field_path))

    # Consolidate add+delete pairs at the same path into updates
    changes = _consolidate_add_delete_pairs(changes)
    # Filter out non-changes (where deployed_value == package_value)
    changes = [c for c in changes if c.deployed_value != c.package_value]

    return changes


def _consolidate_add_delete_pairs(changes: list[DiffResult]) -> list[DiffResult]:
    """Consolidate add+delete pairs at the same field_path into update changes.

    When jsondiff reports an add and delete at the same field_path, this is actually
    an update (the value changed). This function combines such pairs into a single
    update change.

    Args:
        changes: List of DiffResult entries to consolidate.

    Returns:
        Consolidated list with add+delete pairs merged into updates.
    """
    # Group changes by field_path
    adds_by_path: dict[str, DiffResult] = {}
    deletes_by_path: dict[str, DiffResult] = {}
    other_changes: list[DiffResult] = []

    for change in changes:
        if change.change == "add":
            adds_by_path[change.field_path] = change
        elif change.change == "delete":
            deletes_by_path[change.field_path] = change
        else:
            other_changes.append(change)

    # Find matching pairs and create updates
    consolidated: list[DiffResult] = list(other_changes)
    matched_paths: set[str] = set()

    for path, add_change in adds_by_path.items():
        if path in deletes_by_path:
            # This is an update: delete + add at same path
            delete_change = deletes_by_path[path]
            consolidated.append(
                DiffResult(
                    change="update",
                    field_path=path,
                    deployed_value=delete_change.deployed_value,
                    package_value=add_change.package_value,
                )
            )
            matched_paths.add(path)
        else:
            # Standalone add
            consolidated.append(add_change)

    # Add standalone deletes (not matched with an add)
    for path, delete_change in deletes_by_path.items():
        if path not in matched_paths:
            consolidated.append(delete_change)

    return consolidated


def _diff_semantic_data_models(
    spec_sdms: list | None,
    deployed_sdms: list[SemanticDataModel] | None,
    spec_sdms_content: dict[str, SemanticDataModel] | None = None,
) -> list[DiffResult]:
    """Calculate differences between semantic data model lists.

    Args:
        spec_sdms: Semantic data models from the spec (name references only).
        deployed_sdms: Deployed semantic data models.
        spec_sdms_content: Optional dictionary mapping SDM names to their full content.

    Returns:
        List of differences found.
    """
    changes: list[DiffResult] = []
    spec_list = spec_sdms or []
    deployed_list = deployed_sdms or []

    spec_names = {sdm.name for sdm in spec_list}
    deployed_names = {sdm.name or "" for sdm in deployed_list}

    # Find added SDMs (in spec but not in deployed)
    for name in spec_names - deployed_names:
        changes.append(
            DiffResult(
                change="add",
                field_path=f"semantic_data_models.{name}",
                deployed_value=None,
                package_value=name,
            )
        )

    # Find deleted SDMs (in deployed but not in spec)
    for name in deployed_names - spec_names:
        changes.append(
            DiffResult(
                change="delete",
                field_path=f"semantic_data_models.{name}",
                deployed_value=name,
                package_value=None,
            )
        )

    # Compare content for SDMs that exist in both
    if spec_sdms_content:
        deployed_by_name = {sdm.name or "": sdm for sdm in deployed_list}
        common_names = spec_names & deployed_names

        for name in common_names:
            spec_content = spec_sdms_content.get(name)
            deployed_content = deployed_by_name.get(name)

            if spec_content and deployed_content:
                # Compare relevant fields only
                spec_normalized = {
                    "name": spec_content.name or "",
                    "description": spec_content.description or "",
                    "columns": spec_content.model_dump().get("columns", []),
                }
                deployed_normalized = {
                    "name": deployed_content.name or "",
                    "description": deployed_content.description or "",
                    "columns": deployed_content.model_dump().get("columns", []),
                }
                if spec_normalized != deployed_normalized:
                    changes.append(
                        DiffResult(
                            change="update",
                            field_path=f"semantic_data_models.{name}",
                            deployed_value="deployed",
                            package_value="spec",
                        )
                    )

    return changes


async def calculate_agent_diff(
    *,
    deployed_agent: Agent,
    deployed_sdms: list[SemanticDataModel] | None = None,
    spec_agent: SpecAgent,
    spec_question_groups: list[QuestionGroup] | None = None,
    spec_runbook: str | None = None,
    spec_sdms: dict[str, SemanticDataModel] | None = None,
) -> AgentDiffResult:
    """Calculate differences between a spec agent and a deployed agent.

    Converts the SpecAgent to an Agent, then uses jsondiff to find all differences.

    Args:
        deployed_agent: The deployed agent from storage.
        deployed_sdms: Optional list of deployed semantic data models for comparison.
        spec_agent: The agent specification from agent-spec.yaml.
        spec_question_groups: Optional list of question groups from conversation guide.
            If not provided, falls back to metadata.question_groups from the spec.
        spec_runbook: Optional runbook content read from the runbook file.
        spec_sdms: Optional dictionary of semantic data models from the package.

    Returns:
        AgentDiffResult containing all differences found.
    """
    # Convert SpecAgent to Agent
    expected_agent = AgentSpecGenerator.to_agent(
        spec_agent=spec_agent,
        spec_runbook=spec_runbook,
        spec_question_groups=spec_question_groups,
    )

    # Get model dumps and normalize
    deployed_dict = _normalize_for_comparison(deployed_agent.model_dump())
    expected_dict = _normalize_for_comparison(expected_agent.model_dump())

    # Calculate diff using jsondiff
    diff_result = diff(deployed_dict, expected_dict, syntax="symmetric")

    # Convert to DiffResult list
    changes = _jsondiff_to_diff_results(diff_result)

    # Handle SDM comparison separately (if provided)
    if spec_agent.semantic_data_models or deployed_sdms:
        sdm_changes = _diff_semantic_data_models(
            spec_sdms=spec_agent.semantic_data_models,
            deployed_sdms=deployed_sdms,
            spec_sdms_content=spec_sdms,
        )
        changes.extend(sdm_changes)

    return AgentDiffResult(is_synced=len(changes) == 0, changes=changes)
