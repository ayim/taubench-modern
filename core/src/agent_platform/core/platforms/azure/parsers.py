from agent_platform.core.platforms.openai.parsers import OpenAIParsers


class AzureOpenAIParsers(OpenAIParsers):
    """Parsers that transform AzureOpenAI types to agent-server prompt types.

    This class inherits all functionality from OpenAIParsers since Azure OpenAI
    responses have the same format as OpenAI responses.
    """
