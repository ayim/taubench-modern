from agent_platform.core.platforms.base import PlatformClient
from agent_platform.core.platforms.bedrock import (
    BedrockClient,
    BedrockPlatformParameters,
)
from agent_platform.core.platforms.openai import (
    OpenAIClient,
    OpenAIPlatformParameters,
)

AnyPlatformParameters = BedrockPlatformParameters | OpenAIPlatformParameters

__all__ = [
    "BedrockClient",
    "PlatformClient",
    "AnyPlatformParameters",
    "OpenAIClient",
]
