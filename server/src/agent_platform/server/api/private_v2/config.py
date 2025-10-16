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


@router.post("/")
async def set_config(
    user: AuthedUser,
    payload: ConfigPayload,
) -> dict[str, str]:
    """Set a configuration value by config_type and current_value."""
    logger.info("Setting configuration", config_type=payload.config_type, user_id=user.user_id)

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
        raise HTTPException(status_code=500, detail=str(e)) from e

    result = []
    for _, quota_data in all_quotas.items():
        config_response = ConfigResponse(
            config_type=quota_data["storage_key"],
            config_value=str(quota_data["value"]),
        )
        result.append(config_response)

    return result
