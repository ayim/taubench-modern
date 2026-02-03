from dataclasses import dataclass

import structlog

from agent_platform.core.agent.question_group import QuestionGroup
from agent_platform.core.agent_package.handler.agent_package import AgentPackageHandler
from agent_platform.core.agent_package.spec import SpecAgent
from agent_platform.core.semantic_data_model.types import SemanticDataModel

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class ReadAgentPackageResult:
    spec_agent: SpecAgent
    runbook: str
    question_groups: list[QuestionGroup]
    semantic_data_models_map: dict[str, SemanticDataModel]


async def read_agent_package(handler: AgentPackageHandler) -> ReadAgentPackageResult:
    """
    Provides a collective information about the Agent Package, in a form of ReadAgentPackageResult.

    :param handler: AgentPackageHandler representing the Agent Package.
    :return: ReadAgentPackageResult containing collective information about the Agent Package.
    """
    spec_agent = await handler.get_spec_agent()

    runbook = await handler.read_runbook()
    question_groups = await handler.read_conversation_guide()
    semantic_data_models = await handler.read_all_semantic_data_models()

    return ReadAgentPackageResult(
        spec_agent=spec_agent,
        runbook=runbook,
        question_groups=question_groups,
        semantic_data_models_map=semantic_data_models,
    )
