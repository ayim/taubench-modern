from agent_server_types import ChatRequest, ChatRole
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig

from sema4ai_agent_server.schema import AgentServerRunnableConfig


def convert_chat_to_langchain(
    request: ChatRequest,
) -> list[HumanMessage | AIMessage | SystemMessage | ToolMessage]:
    """
    Convert a ChatRequest to a list of Langchain messages.
    """
    messages = []
    for message in request.input:
        match message.type:
            case ChatRole.HUMAN:
                messages.append(HumanMessage(content=message.content, id=message.id))
            case ChatRole.AI:
                messages.append(AIMessage(content=message.content, id=message.id))
            case ChatRole.SYSTEM:
                messages.append(SystemMessage(content=message.content, id=message.id))
            case ChatRole.ACTION:
                messages.append(ToolMessage(content=message.content, id=message.id))
            case _:
                pass
    return messages


def get_thread_id_from_config(
    config: AgentServerRunnableConfig | RunnableConfig,
) -> str:
    """
    Get the thread ID from the given config.
    """
    return str(
        getattr(config.get("configurable", {}).get("thread"), "thread_id", None)
        or config.get("configurable", {}).get("thread_id")
        or config.get("metadata", {}).get("thread_id")
        or ""
    )
