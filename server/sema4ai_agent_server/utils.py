from agent_server_types import ChatRequest, ChatRole
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage


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
