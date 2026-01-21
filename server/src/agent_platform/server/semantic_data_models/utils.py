"""Utility functions for semantic data models."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from agent_platform.core.data_frames.semantic_data_model_types import (
        SemanticDataModel,
    )
    from agent_platform.server.storage import BaseStorage


async def _get_existing_semantic_data_model_names(
    storage: BaseStorage,
    exclude_model_id: str | None = None,
) -> set[str]:
    """Get all existing semantic data model names (case-insensitive).

    Args:
        storage: The storage instance to use.
        exclude_model_id: Optional model ID to exclude from the check (for updates).

    Returns:
        A set of existing semantic data model names (case-insensitive).
    """
    all_models = await storage.list_semantic_data_models()
    existing_names = set()
    for model_info in all_models:
        if exclude_model_id is not None and model_info["semantic_data_model_id"] == exclude_model_id:
            continue
        semantic_model = model_info["semantic_data_model"]
        existing_name = semantic_model.get("name", "")
        if existing_name:
            existing_names.add(existing_name.lower())
    return existing_names


async def check_semantic_data_model_name_exists(
    model_name: str,
    exclude_model_id: str | None = None,
    storage: BaseStorage | None = None,
) -> bool:
    """Check if a semantic data model name already exists (case-insensitive).

    Args:
        model_name: The name to check.
        exclude_model_id: Optional model ID to exclude from the check (for updates).
        storage: The storage instance to use for retrieving models. If not provided, the default storage
            instance will be used.

    Returns:
        True if a model with this name exists, False otherwise.
    """
    from agent_platform.server.storage import StorageService

    if storage is None:
        storage = StorageService.get_instance()

    existing_names = await _get_existing_semantic_data_model_names(storage, exclude_model_id)
    return model_name.lower() in existing_names


async def validate_semantic_data_model_name_is_unique(
    model_name: str,
    exclude_model_id: str | None = None,
    storage: BaseStorage | None = None,
) -> None:
    """Validate that a semantic data model name is unique, raising an error if not.

    Use this for strict validation when the user explicitly provides a name.

    Args:
        model_name: The name to validate.
        exclude_model_id: Optional model ID to exclude from the check (for updates).
        storage: The storage instance to use. If not provided, uses the default instance.

    Raises:
        SemanticDataModelWithNameAlreadyExistsError: If a model with this name already exists.
    """
    from agent_platform.server.semantic_data_models.errors import (
        SemanticDataModelWithNameAlreadyExistsError,
    )
    from agent_platform.server.storage import StorageService

    if storage is None:
        storage = StorageService.get_instance()

    if await check_semantic_data_model_name_exists(model_name, exclude_model_id=exclude_model_id, storage=storage):
        raise SemanticDataModelWithNameAlreadyExistsError(model_name)


async def make_semantic_data_model_name_unique(
    model_name: str,
    exclude_model_id: str | None = None,
    storage: BaseStorage | None = None,
) -> str:
    """Make a semantic data model name unique by appending a counter if needed.

    Use this for auto-generated names where you want to ensure uniqueness without
    raising an error.

    Args:
        model_name: The base name to make unique.
        exclude_model_id: Optional model ID to exclude from the check (for updates).
        storage: The storage instance to use. If not provided, uses the default instance.

    Returns:
        A unique name (either the original name or with a counter appended like " (1)").
    """
    from agent_platform.server.storage import StorageService

    if storage is None:
        storage = StorageService.get_instance()

    if not model_name:
        return ""

    existing_names = await _get_existing_semantic_data_model_names(storage, exclude_model_id)
    if model_name.lower() not in existing_names:
        return model_name

    # Try appending (1), (2), etc. until we find a unique name
    counter = 1
    while True:
        candidate_name = f"{model_name} ({counter})"
        if candidate_name.lower() not in existing_names:
            return candidate_name
        counter += 1


async def get_semantic_data_model_by_name(
    model_name: str,
    storage: BaseStorage,
) -> SemanticDataModel | None:
    """Get semantic data model by name.

    Args:
        model_name: The name of the semantic data model to find.
        storage: The storage instance to use.

    Returns:
        The semantic data model (SemanticDataModel TypedDict).
        Returns None if no model with the given name is found.
    """
    all_models = await storage.list_semantic_data_models()
    for model_info in all_models:
        semantic_model = model_info["semantic_data_model"]
        if semantic_model.get("name") == model_name:
            return cast("SemanticDataModel", semantic_model)
    return None
