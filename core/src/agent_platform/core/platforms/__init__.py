from agent_platform.core.platforms.base import PlatformClient
from agent_platform.core.platforms.bedrock import (
    BedrockClient,
    BedrockPlatformParameters,
)
from agent_platform.core.platforms.cortex import (
    CortexClient,
    CortexPlatformParameters,
)
from agent_platform.core.platforms.openai import (
    OpenAIClient,
    OpenAIPlatformParameters,
)

AnyPlatformParameters = (
    BedrockPlatformParameters
    | CortexPlatformParameters
    | OpenAIPlatformParameters
)

__all__ = [
    "BedrockClient",
    "CortexClient",
    "OpenAIClient",
    "PlatformClient",
    "AnyPlatformParameters",
]
