from typing import cast

from fastapi import APIRouter, HTTPException

from agent_platform.core.payloads.upsert_platform_config import UpsertPlatformConfigPayload
from agent_platform.core.platforms import AnyPlatformParameters
from agent_platform.server.api.dependencies import StorageDependency
from agent_platform.server.auth import AuthedUser

router = APIRouter()


@router.post("/", response_model=AnyPlatformParameters)
async def create_platform(
    payload: UpsertPlatformConfigPayload,
    user: AuthedUser,
    storage: StorageDependency,
) -> AnyPlatformParameters:
    """Create a new platform configuration."""
    platform_params = payload.to_platform_parameters()
    await storage.create_platform_params(platform_params)
    # Return the stored platform params with the correct ID
    stored_platform = await storage.get_platform_params(platform_params.platform_id)
    return cast(AnyPlatformParameters, stored_platform)


@router.get("/", response_model=list[AnyPlatformParameters])
async def list_platforms(
    user: AuthedUser,
    storage: StorageDependency,
) -> list[AnyPlatformParameters]:
    """List all platform configurations for the authenticated user."""
    platforms = await storage.list_platform_params()
    return cast(list[AnyPlatformParameters], platforms)


@router.get("/{platform_id}", response_model=AnyPlatformParameters)
async def get_platform(
    platform_id: str,
    user: AuthedUser,
    storage: StorageDependency,
) -> AnyPlatformParameters:
    """Get a specific platform configuration by ID."""
    platform = await storage.get_platform_params(platform_id)
    return cast(AnyPlatformParameters, platform)


@router.put("/{platform_id}", response_model=AnyPlatformParameters)
async def update_platform(
    platform_id: str,
    payload: UpsertPlatformConfigPayload,
    user: AuthedUser,
    storage: StorageDependency,
) -> AnyPlatformParameters:
    """Update an existing platform configuration by ID."""
    existing_params = await storage.get_platform_params(platform_id)

    existing_payload = UpsertPlatformConfigPayload.from_platform_parameters(existing_params, config_id=platform_id)

    merged_credentials: dict | None
    if payload.credentials and existing_payload.credentials:
        merged_credentials = {**existing_payload.credentials, **payload.credentials}
    else:
        merged_credentials = payload.credentials or existing_payload.credentials

    merged_payload = UpsertPlatformConfigPayload(
        id=platform_id,
        name=payload.name or existing_payload.name,
        kind=payload.kind or existing_payload.kind,
        description=payload.description or existing_payload.description,
        credentials=merged_credentials,
        models=payload.models or existing_payload.models,
    )

    platform_params = merged_payload.to_platform_parameters()
    await storage.update_platform_params(
        platform_id,
        platform_params,
    )
    # Return the updated platform params with the correct ID
    updated_platform = await storage.get_platform_params(platform_id)
    return cast(AnyPlatformParameters, updated_platform)


@router.delete("/{platform_id}", status_code=204)
async def delete_platform(
    platform_id: str,
    user: AuthedUser,
    storage: StorageDependency,
) -> None:
    """Delete a platform configuration."""
    from agent_platform.core.configurations.config_validation import ConfigType
    from agent_platform.server.storage.errors import ConfigNotFoundError

    try:
        eval_config = await storage.get_config(ConfigType.GLOBAL_EVAL_PLATFORM_PARAMS_ID)
    except ConfigNotFoundError:
        eval_config = None

    if eval_config and eval_config.config_value == platform_id:
        raise HTTPException(
            status_code=409,
            detail="Platform configuration is set as the global eval platform and cannot be deleted.",
        )
    await storage.delete_platform_params(platform_id)


# TODO: Implement a get_platform_providers endpoint that returns a list of available providers
# for a givent platform based on a set of provided credentials. This depends on the
# client get_available_models method being implemented.
