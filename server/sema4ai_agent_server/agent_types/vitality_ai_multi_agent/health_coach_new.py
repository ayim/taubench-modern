from langchain_openai import ChatOpenAI

from sema4ai_agent_server.agent_types.vitality_ai_multi_agent.data_retrieval_specilalist_new import (
    DataRetrievalSpecialist,
)
from sema4ai_agent_server.tools import BaseTool


class HealthCoach(DataRetrievalSpecialist):
    def __init__(self, data_retriever_llm: ChatOpenAI, tools: list[BaseTool]):
        health_coach_objective_instructions = self.load_agent_prompt(
            "health_coach_prompt.md"
        )

        super().__init__(
            data_retriever_llm,
            health_coach_objective_instructions,
            tools,
            "Health Coach",
        )
