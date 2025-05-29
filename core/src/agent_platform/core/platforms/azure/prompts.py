import logging
from dataclasses import dataclass

from agent_platform.core.platforms.azure.configs import AzureOpenAIModelMap
from agent_platform.core.platforms.openai.prompts import OpenAIPrompt

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AzureOpenAIPrompt(OpenAIPrompt):
    """A prompt for the AzureOpenAI platform.

    This class inherits from OpenAIPrompt and overrides the as_platform_request
    method to use AzureOpenAIModelMap instead of OpenAIModelMap.
    """

    def as_platform_request(
        self,
        model: str,
        stream: bool = False,
    ) -> dict:
        """Convert the prompt to an AzureOpenAI request.

        Args:
            model: The Azure OpenAI model to use.
            stream: Whether to return a stream request.

        Returns:
            An AzureOpenAI request.
        """
        model_id = AzureOpenAIModelMap.model_aliases[model]
        logger.info(f"Using AzureOpenAI model: {model} (model_id: {model_id})")
        results_dict = {
            "model": model_id,
            "messages": self.messages or [],
        }

        if any(model.startswith(prefix) for prefix in ["o3-mini", "o1", "o1-mini"]):
            # For o1/o3 models, adjust temperature based on high/low reasoning
            if model.endswith("-high"):
                results_dict["reasoning_effort"] = "high"
                logger.info(f"Using model {model} with high reasoning effort")
            elif model.endswith("-low"):
                results_dict["reasoning_effort"] = "low"
                logger.info(f"Using model {model} with low reasoning effort")
            else:
                logger.info(f"Using model {model} with default reasoning effort")
        else:
            logger.info(f"Using model {model}")

        if self.tools:
            results_dict["tools"] = self.tools
            logger.info(f"Request includes {len(self.tools)} tools")

        if stream:
            results_dict["stream"] = True
            results_dict["stream_options"] = {"include_usage": True}
            logger.info("Streaming enabled for this request")

        return results_dict
