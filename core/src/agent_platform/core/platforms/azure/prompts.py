import logging
from dataclasses import dataclass

from agent_platform.core.platforms.openai.prompts import OpenAIPrompt

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AzureOpenAIPrompt(OpenAIPrompt):
    """A prompt for the AzureOpenAI platform."""
