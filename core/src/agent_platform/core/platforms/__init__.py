from agent_platform.core.platforms.azure import (
    AzureOpenAIClient,
    AzureOpenAIPlatformParameters,
)
from agent_platform.core.platforms.azure_foundry import (
    AzureFoundryClient,
    AzureFoundryPlatformParameters,
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
from agent_platform.core.platforms.groq import (
    GroqClient,
    GroqPlatformParameters,
)
from agent_platform.core.platforms.litellm import (
    LiteLLMClient,
    LiteLLMPlatformParameters,
)
from agent_platform.core.platforms.openai import (
    OpenAIClient,
    OpenAIPlatformParameters,
)
from agent_platform.core.platforms.reducto import (
    ReductoClient,
    ReductoPlatformParameters,
)

AnyPlatformParameters = (
    BedrockPlatformParameters
    | CortexPlatformParameters
    | LiteLLMPlatformParameters
    | OpenAIPlatformParameters
    | AzureOpenAIPlatformParameters
    | AzureFoundryPlatformParameters
    | GooglePlatformParameters
    | GroqPlatformParameters
    | ReductoPlatformParameters
)

__all__ = [
    "AnyPlatformParameters",
    "AzureFoundryClient",
    "AzureFoundryPlatformParameters",
    "AzureOpenAIClient",
    "BedrockClient",
    "CortexClient",
    "GoogleClient",
    "GroqClient",
    "LiteLLMClient",
    "OpenAIClient",
    "PlatformClient",
    "ReductoClient",
]
