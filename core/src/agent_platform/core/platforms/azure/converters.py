from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

from agent_platform.core.platforms.azure.prompts import AzureOpenAIPrompt
from agent_platform.core.platforms.openai.converters import OpenAIConverters
from agent_platform.core.prompts import Prompt


class AzureOpenAIConverters(OpenAIConverters):
    """Converters that transform agent-server prompt types to AzureOpenAI types.

    This class inherits from OpenAIConverters and overrides only the methods that need
    Azure-specific customization.
    """

    async def convert_prompt(
        self,
        prompt: Prompt,
        model_id: str | None = None,
    ) -> AzureOpenAIPrompt:
        """Convert a prompt to AzureOpenAI format.

        Args:
            prompt: The prompt to convert.

        Returns:
            The converted prompt.
        """
        if model_id is None:
            raise ValueError(
                "Azure OpenAI requires a model_id to be provided to convert a prompt."
                "\nThere are some model-specific changes such as a lack of "
                "system messages for some models.",
            )

        # Convert messages and system instruction
        messages = await self._convert_messages(prompt.finalized_messages)
        system = await self._convert_system_instruction_to_openai(
            prompt.system_instruction,
            model_id,
        )

        # Add system message at the beginning if present
        all_messages = list(messages)
        if system and len(system) > 0:
            all_messages.insert(0, system[0])

        # Convert tools if present
        tools = None
        if prompt.tools:
            tools = await self._convert_tools(prompt.tools)

        return AzureOpenAIPrompt(
            messages=all_messages,
            tools=tools,
            temperature=prompt.temperature or 0.0,
            top_p=prompt.top_p or 1.0,
            max_tokens=prompt.max_output_tokens or 4096,
        )
