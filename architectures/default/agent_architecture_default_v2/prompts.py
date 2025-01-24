from typing import Type

from agent_server_types import (
    Agent,
    AgentReasoning,
)
from langchain_core.messages import AnyMessage

from agent_architecture import (
    BaseInputSpec,
    PredefinedChatPromptTemplate,
)

BASE_PROMPT_MESSAGES = [
    (
        "system",
        """You are an assistant with the following name: {agent_name}.
The current date and time is: {current_datetime}.
{knowledge_files}
Your instructions are:
{runbook}""",
    ),
    ("placeholder", "{messages}"),
]


class ToolsAgentInputSpec(BaseInputSpec):
    agent_name: str
    current_datetime: str
    knowledge_files: str
    runbook: str
    messages: list[AnyMessage]


class ToolsAgentBasePromptTemplate(PredefinedChatPromptTemplate):
    """The base prompt template used for the nodes in the tools agent graph."""

    input_spec: Type[ToolsAgentInputSpec] = ToolsAgentInputSpec


class ExecutePromptTemplate(ToolsAgentBasePromptTemplate):
    """The prompt template used for the execute nodes in the agent graph."""

    def create_template_messages(self, agent: Agent = None) -> list[tuple[str, str]]:
        return BASE_PROMPT_MESSAGES


class ReasoningPromptTemplate(ToolsAgentBasePromptTemplate):
    """The prompt template used for the reasoning nodes in the agent graph."""

    def create_template_messages(self, agent: Agent = None) -> list[tuple[str, str]]:
        if agent is None:
            reasoning_level = AgentReasoning.ENABLED
        else:
            reasoning_level = agent.advanced_config.reasoning
        match reasoning_level:
            case AgentReasoning.ENABLED:
                reasoning_addendum = """
Focus on the most important aspects of your reasoning.
        """.strip()
            case AgentReasoning.VERBOSE:
                reasoning_addendum = """
If you are thinking about calling tools, also explain what parameters you are \
thinking of using and why.
        """.strip()

        prompt = f"""
Think about your next response based on the conversation so far and \
{"succinctly " if reasoning_level == AgentReasoning.ENABLED else ""}explain why you are thinking \
to respond in this way. {reasoning_addendum} ONLY PROVIDE REASONING.
        """.strip()

        return BASE_PROMPT_MESSAGES + [("system", prompt)]
