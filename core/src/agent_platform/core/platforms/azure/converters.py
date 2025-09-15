from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

from agent_platform.core.platforms.openai.converters import OpenAIConverters


class AzureOpenAIConverters(OpenAIConverters):
    """Converters that transform agent-server prompt types to AzureOpenAI types.

    Nothing need (at the moment) to be done here, just inherit from OpenAIConverters.
    """

    pass
