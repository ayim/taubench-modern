from typing import TYPE_CHECKING

from agent_platform.core.platforms.openai.converters import OpenAIConverters

if TYPE_CHECKING:
    from agent_platform.core.platforms.openai.prompts import OpenAIPrompt
    from agent_platform.core.prompts import Prompt


class LiteLLMConverters(OpenAIConverters):
    """Parsers for the LiteLLM platform."""

    async def convert_prompt(
        self,
        prompt: "Prompt",
        model_id: str | None = None,
    ) -> "OpenAIPrompt":
        """Convert a prompt to OpenAI format, dropping early reasoning for LiteLLM."""
        from dataclasses import replace

        base_prompt = await super().convert_prompt(prompt, model_id)

        # We seem to be needing to do this, else we get spurious errors
        # when using OpenAI via LiteLLM.
        filtered_messages = self._drop_reasoning_items_before_last_user_message(base_prompt.input)

        return replace(base_prompt, input=filtered_messages)
