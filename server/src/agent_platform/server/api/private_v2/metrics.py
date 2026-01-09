import asyncio

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from agent_platform.server.api.dependencies import StorageDependency

router = APIRouter()


class MetricsResponse(BaseModel):
    model_config = ConfigDict(json_schema_mode_override="serialization")

    agent_count: int = Field(description="The total number of agents", serialization_alias="agentCount")
    thread_count: int = Field(description="The total number of threads", serialization_alias="threadCount")
    conversational_agent_count: int = Field(
        description="The total number of conversational agents", serialization_alias="conversationalAgentCount"
    )
    worker_agent_count: int = Field(
        description="The total number of worker agents", serialization_alias="workerAgentCount"
    )
    message_count: int = Field(description="The total number of messages", serialization_alias="messageCount")
    generate_sql_count: int = Field(
        description="The total number of calls to generate_sql", serialization_alias="generateSqlCount"
    )


@router.get("")
async def metrics(storage: StorageDependency) -> MetricsResponse:
    (
        agent_count,
        thread_count,
        conversational_agent_count,
        worker_agent_count,
        message_count,
        generate_sql_count,
    ) = await asyncio.gather(
        storage.count_agents(),
        storage.count_threads(),
        storage.count_agents_by_mode("conversational"),
        storage.count_agents_by_mode("worker"),
        storage.count_messages(),
        count_sql_generation_threads(storage),
    )

    return MetricsResponse(
        agent_count=agent_count,
        thread_count=thread_count,
        conversational_agent_count=conversational_agent_count,
        worker_agent_count=worker_agent_count,
        message_count=message_count,
        generate_sql_count=generate_sql_count,
    )


async def count_sql_generation_threads(storage: StorageDependency) -> int:
    from agent_platform.server.sql_generation.preinstalled_agent import get_sql_generation_agent

    sql_generation_agent = await get_sql_generation_agent(storage)
    if sql_generation_agent is None:
        return 0

    agent_id = sql_generation_agent.agent_id
    return await storage.count_threads_for_agent(agent_id)
