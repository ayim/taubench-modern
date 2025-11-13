"""Groq converters reuse the OpenAI Responses API converters."""

from dataclasses import fields

from agent_platform.core.platforms.groq.prompts import GroqPrompt
from agent_platform.core.platforms.openai.converters import OpenAIConverters
from agent_platform.core.platforms.openai.prompts import OpenAIPrompt
from agent_platform.core.prompts import Prompt


class GroqConverters(OpenAIConverters):
    """Converters for the Groq platform."""

    async def convert_prompt(
        self,
        prompt: Prompt,
        model_id: str | None = None,
    ) -> GroqPrompt:
        """Convert a prompt to the Groq-specific prompt dataclass."""
        openai_prompt = await super().convert_prompt(prompt, model_id=model_id)
        return self._to_groq_prompt(openai_prompt)

    def _to_groq_prompt(self, prompt: OpenAIPrompt) -> GroqPrompt:
        prompt_kwargs = {field.name: getattr(prompt, field.name) for field in fields(OpenAIPrompt)}
        return GroqPrompt(**prompt_kwargs)
