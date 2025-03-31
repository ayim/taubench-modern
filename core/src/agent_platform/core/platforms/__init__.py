from agent_platform.core.platforms.base import PlatformClient
from agent_platform.core.platforms.bedrock import (
    BedrockClient,
    BedrockPlatformParameters,
)

AnyPlatformParameters = BedrockPlatformParameters

__all__ = ["BedrockClient", "PlatformClient", "AnyPlatformParameters"]
