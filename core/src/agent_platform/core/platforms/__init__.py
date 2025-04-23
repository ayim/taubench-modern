from agent_platform.core.platforms.azure import (
    AzureOpenAIClient,
    AzureOpenAIPlatformParameters,
)
from agent_platform.core.platforms.base import PlatformClient
from agent_platform.core.platforms.bedrock import (
    BedrockClient,
    BedrockPlatformParameters,
)
from agent_platform.core.platforms.cortex import (
    CortexClient,
    CortexPlatformParameters,
)
from agent_platform.core.platforms.google import GoogleClient, GooglePlatformParameters
from agent_platform.core.platforms.openai import (
    OpenAIClient,
    OpenAIPlatformParameters,
)

AnyPlatformParameters = (
    BedrockPlatformParameters
    | CortexPlatformParameters
    | OpenAIPlatformParameters
    | AzureOpenAIPlatformParameters
    | GooglePlatformParameters
)

__all__ = [
    "AnyPlatformParameters",
    "AzureOpenAIClient",
    "BedrockClient",
    "CortexClient",
    "GoogleClient",
    "OpenAIClient",
    "PlatformClient",
]
