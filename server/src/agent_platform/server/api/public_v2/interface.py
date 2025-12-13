from dataclasses import dataclass, field
from typing import Any

from agent_platform.core.agent.agent import Agent
from agent_platform.core.thread import Thread


@dataclass
class CreateChatRequest:
    name: str


@dataclass
class ChatMessageRequest:
    content: str


@dataclass
class PaginatedResponse:
    next: str | None
    has_more: bool
    data: list[Any]


@dataclass(frozen=True)
class AgentCompat:
    id: str = field()
    name: str = field()
    description: str = field()
    mode: str = field()

    @classmethod
    def from_agent(cls, agent: Agent) -> "AgentCompat":
        return cls(id=agent.agent_id, name=agent.name, description=agent.description, mode=agent.mode)


@dataclass(frozen=True)
class Conversation:
    id: str
    name: str
    agent_id: str

    @classmethod
    def from_thread(cls, thread: Thread) -> "Conversation":
        return cls(id=thread.thread_id, name=thread.name, agent_id=thread.agent_id)
