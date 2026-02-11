from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent_platform.server.api.dependencies import StorageDependency


async def resolve_global_eval_model(
    storage: "StorageDependency",
) -> tuple[str, dict | None]:
    from agent_platform.core.configurations.config_validation import ConfigType
    from agent_platform.server.storage.errors import (
        ConfigNotFoundError,
        InvalidUUIDError,
        PlatformConfigNotFoundError,
    )

    try:
        eval_config = await storage.get_config(ConfigType.DEFAULT_LLM_PLATFORM_PARAMS_ID)
    except ConfigNotFoundError:
        return ("", None)

    config_value = eval_config.config_value
    if not isinstance(config_value, str):
        raise ValueError("DEFAULT_LLM_PLATFORM_PARAMS_ID config_value must be a string")

    config_value = config_value.strip()
    if config_value == "":
        return ("", None)

    try:
        platform_params = await storage.get_platform_params(config_value)
    except (InvalidUUIDError, PlatformConfigNotFoundError):
        return (config_value, None)

    return ("", platform_params.model_dump())
