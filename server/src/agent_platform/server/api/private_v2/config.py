from dataclasses import dataclass

from fastapi import APIRouter, HTTPException
from structlog import get_logger

from agent_platform.core.configurations.config_validation import ConfigType
from agent_platform.core.configurations.quotas import QuotasService
from agent_platform.server.auth import AuthedUser

router = APIRouter()
logger = get_logger(__name__)


@dataclass
class ConfigPayload:
    """Payload for setting configuration values."""

    config_type: ConfigType
    current_value: str


@dataclass
class ConfigResponse:
    """Response for individual configuration values."""

    config_type: ConfigType
    config_value: str
    description: str


@router.post("/")
async def set_config(
    user: AuthedUser,
    payload: ConfigPayload,
) -> dict[str, str]:
    """Set a configuration value by config_type and current_value."""
    logger.info("Setting configuration", config_type=payload.config_type, user_id=user.user_id)

    if payload.config_type is ConfigType.GLOBAL_EVAL_PLATFORM_PARAMS_ID:
        from agent_platform.server.storage import StorageService

        storage = StorageService.get_instance()
        current_value = payload.current_value
        if current_value is not None and current_value.strip() == "":
            current_value = ""
        if current_value is not None:
            from uuid import UUID

            try:
                UUID(current_value)
            except ValueError as e:
                raise HTTPException(
                    status_code=422, detail="Global eval platform params ID must be a valid UUID"
                ) from e
        await storage.set_config(payload.config_type, current_value)
    else:
        if payload.current_value is None:
            raise HTTPException(status_code=422, detail="current_value cannot be null")
        quotas_service = await QuotasService.get_instance()
        await quotas_service.set_config(payload.config_type, payload.current_value)

    return {
        "message": "Configuration set successfully",
        "config_type": payload.config_type,
    }


@router.get("/")
async def get_all_configs(
    user: AuthedUser,
) -> list[ConfigResponse]:
    """Get all configuration values."""
    logger.info("Retrieving all configurations", user_id=user.user_id)

    try:
        quotas_service = await QuotasService.get_instance()
        all_quotas = quotas_service.get_all_configs()
    except Exception as e:
        logger.error("Failed to get all configurations", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve configuration") from e

    configs = [
        ConfigResponse(
            config_type=quota_data["storage_key"],
            config_value=str(quota_data["value"]),
            description=quota_data["description"],
        )
        for quota_data in all_quotas.values()
    ]

    eval_platform_params_description = "Default platform configuration used for evaluation runs."
    eval_platform_params_value = ""
    try:
        from agent_platform.server.storage import StorageService
        from agent_platform.server.storage.errors import ConfigNotFoundError

        storage = StorageService.get_instance()
        eval_config = await storage.get_config(ConfigType.GLOBAL_EVAL_PLATFORM_PARAMS_ID)
        eval_platform_params_value = eval_config.config_value
    except ConfigNotFoundError:
        eval_platform_params_value = ""
    except Exception as e:
        logger.error("Failed to get global eval platform params configuration", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve configuration") from e

    configs.append(
        ConfigResponse(
            config_type=ConfigType.GLOBAL_EVAL_PLATFORM_PARAMS_ID,
            config_value=eval_platform_params_value,
            description=eval_platform_params_description,
        )
    )

    return configs
