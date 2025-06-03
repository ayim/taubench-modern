from dataclasses import dataclass, field

from agent_platform.core.agent.agent import Agent
from agent_platform.core.thread import Thread
from agent_platform.core.thread.base import ThreadMessage


@dataclass(frozen=True)
class AgentCompat:
    id: str = field()
    name: str = field()
    description: str = field()
    mode: str = field()

    @classmethod
    def from_agent(cls, agent: Agent) -> "AgentCompat":
        return cls(
            id=agent.agent_id, name=agent.name, description=agent.description, mode=agent.mode
        )


@dataclass(frozen=True)
class ConversationCompat:
    id: str
    name: str
    agent_id: str
    messages: list[dict] | None

    @classmethod
    def from_thread_with_messages(cls, thread: Thread) -> "ConversationCompat":
        messages = [
            translate_message(message) for message in thread.messages if message is not None
        ]
        return cls(
            id=thread.thread_id,
            name=thread.name,
            agent_id=thread.agent_id,
            messages=messages,
        )

    @classmethod
    def from_thread(cls, thread: Thread) -> "ConversationCompat":
        return cls(id=thread.thread_id, name=thread.name, agent_id=thread.agent_id, messages=None)


def translate_message(message: ThreadMessage) -> dict:
    # TODO not sure how to translate this
    return {}
