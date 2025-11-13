"""Groq parsers leverage the OpenAI Responses API parsers."""

from agent_platform.core.platforms.openai.parsers import OpenAIParsers


class GroqParsers(OpenAIParsers):
    """Parsers for the Groq platform.

    The Groq Responses API mirrors OpenAI's Responses API, which allows us to
    reuse the OpenAI parsing logic directly.
    """
