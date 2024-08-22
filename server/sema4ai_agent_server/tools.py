from langchain.tools.retriever import create_retriever_tool

from sema4ai_agent_server.action_server import ActionServerToolkit
from sema4ai_agent_server.schema import MODEL, ActionPackage
from sema4ai_agent_server.storage.embed import get_vector_store


def get_retriever(agent_id: str, thread_id: str, model: MODEL):
    return get_vector_store(model).as_retriever(
        search_kwargs={"filter": {"owner_id": {"$in": [agent_id, thread_id]}}}
    )


def get_retrieval_tool(agent_id: str, thread_id: str, model: MODEL):
    description = """Can be used to look up information that was uploaded to this agent.
    If the user is referencing particular files, that is often a good hint that information may be here.
    If the user asks a vague question, they are likely meaning to look up info from this retriever, and you should call it!"""
    return create_retriever_tool(
        get_retriever(agent_id, thread_id, model),
        "Retriever",
        description,
    )


def get_action_server(action_package: ActionPackage):
    toolkit = ActionServerToolkit(
        url=action_package.url,
        api_key=action_package.api_key.get_secret_value(),
        additional_headers=action_package.additional_headers,
    )
    return toolkit.get_tools(whitelist=action_package.whitelist)
