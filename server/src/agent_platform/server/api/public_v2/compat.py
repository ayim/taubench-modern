import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from agent_platform.core.agent.agent import Agent
from agent_platform.core.thread import Thread
from agent_platform.core.thread.base import AnyThreadMessageContent, ThreadMessage
from agent_platform.core.thread.content.text import ThreadTextContent
from agent_platform.core.thread.content.tool_usage import ThreadToolUsageContent


class Mode(str, Enum):
    CONVERSATIONAL = "conversational"
    WORKER = "worker"


class Architecture(str, Enum):
    AGENT = "agent"
    PLAN_EXECUTE = "plan_execute"


class Provider(str, Enum):
    OPENAI = "OpenAI"
    AZURE = "Azure"
    AMAZON = "Amazon"
    SNOWFLAKE_CORTEX = "Snowflake Cortex AI"


@dataclass
class LanguageModel:
    provider: Provider
    model: str


class Role(str, Enum):
    AGENT = "agent"
    HUMAN = "human"


class MessageType(str, Enum):
    MESSAGE = "message"
    TOKEN = "token"
    TOOL_REQUEST = "action_request"
    TOOL_RESPONSE = "action_response"
    START_STREAM = "start_stream"
    END_STREAM = "end_stream"


@dataclass
class Message:
    id: str | None
    type: MessageType
    role: Role
    content: str
    channel: str = field(default="chat")


@dataclass
class TokenMessage:
    id: str | None
    type: MessageType
    role: Role
    token: str
    token_sequence: int
    channel: str = field(default="chat")


@dataclass
class ToolCall:
    id: str
    name: str
    args: dict


@dataclass
class ToolRequest:
    action_calls: list[ToolCall]
    id: str | None
    type: MessageType
    role: Role
    content: str
    channel: str = field(default="chat")


@dataclass
class ToolResponse:
    action_call_id: str
    status: str
    result: dict
    id: str | None
    type: MessageType
    role: Role
    content: str
    channel: str = field(default="chat")


@dataclass
class ActionPackage:
    name: str
    organization: str
    version: str
    actions: str


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
        return cls(
            id=agent.agent_id, name=agent.name, description=agent.description, mode=agent.mode
        )


@dataclass(frozen=True)
class ConversationCompat:
    id: str
    name: str
    agent_id: str
    messages: list[Message | ToolRequest | ToolResponse] | None

    @classmethod
    def from_thread_with_messages(cls, thread: Thread) -> "ConversationCompat":
        messages = [
            translate_message_content(content, message)
            for message in thread.messages
            for content in message.content
            if message is not None
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


def translate_message_content(
    content: AnyThreadMessageContent, message: ThreadMessage
) -> Message | ToolRequest | ToolResponse:
    role = Role.HUMAN if message.role == "user" else Role.AGENT

    match content:
        case ThreadTextContent(text=text):
            return Message(
                id=message.message_id,
                type=MessageType.MESSAGE,
                role=role,
                content=text,
            )
        case ThreadToolUsageContent(
            name=name,
            tool_call_id=tool_call_id,
            status=status,
            result=result,
            arguments_raw=arguments_raw,
        ):
            # TODO I am not sure that this is the right way to distinguish response/request
            if status == "finished" and result is not None:
                try:
                    result_content = json.loads(result)
                    # TODO this check is from original code, not sure if needed
                    if not isinstance(result_content, dict):
                        result_content = {}
                except json.JSONDecodeError:
                    result_content = {}

                return ToolResponse(
                    id=message.message_id,
                    type=MessageType.TOOL_RESPONSE,
                    role=role,
                    action_call_id=tool_call_id,
                    status=status,
                    result=result_content,
                    content="",
                )
            else:
                args = json.loads(arguments_raw)
                return ToolRequest(
                    id=message.message_id,
                    type=MessageType.TOOL_REQUEST,
                    role=role,
                    # TODO not sure what we should have here
                    content="",
                    action_calls=[ToolCall(id=tool_call_id, args=args, name=name)],
                )

    raise ValueError("Cannot translate this message type")
