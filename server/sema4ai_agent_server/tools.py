from langchain.tools.retriever import create_retriever_tool
from langchain_core.tools import BaseTool

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


# NOTE Both Studio and ACE use a single action server per agent. This action
# server has all actions across all the action packages. So, we just
# use the url and api_key from the first action package to populate all tools.
#
# Action server already performs whitelist filtering on the action packages,
# we we don't have to.
#
# This solution is a stop-gap measure for GA to fix the duplicate action
# issues and solve the problem of whitelist filtering not working. If the
# model of action package execution changes in the future, this code will
# need to be updated.
def get_tools_from_action_packages(
    action_packages: list[ActionPackage], dynamic_headers: dict | None = None
) -> list[BaseTool]:
    if not action_packages:
        return []

    action_package = action_packages[0]
    url, api_key = action_package.url, action_package.api_key.get_secret_value()
    return _get_action_server_tools(url, api_key, dynamic_headers or {})


def _get_action_server_tools(
    url: str, api_key: str, dynamic_headers: dict
) -> list[BaseTool]:
    return ActionServerToolkit(
        url=url, api_key=api_key, additional_headers=dynamic_headers
    ).get_tools()
