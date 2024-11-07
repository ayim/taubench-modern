import os
from contextlib import contextmanager
from dataclasses import dataclass
from functools import lru_cache
from typing import Generator, Optional

import structlog
from agent_server_types import Agent, LangsmithCredentials, Thread
from langchain_core.tracers.context import tracing_v2_callback_var
from langchain_core.tracers.langchain import LangChainTracer
from langsmith import Client
from langsmith.schemas import TracerSession
from langsmith.utils import LangSmithNotFoundError

from sema4ai_agent_server.storage.option import get_storage

logger = structlog.get_logger(__name__)


# Using a dataclass instead of Pydantic's BaseModel, because `Client` is
# implemented in Pydantic 1, and we are using Pydantic 2, which leads to an error.
@dataclass
class Langsmith:
    client: Client
    project: TracerSession


def _tracing_enabled_in_env() -> bool:
    return os.getenv("LANGCHAIN_TRACING_V2") == "true"


def _get_credentials_from_env() -> Optional[LangsmithCredentials]:
    api_key = os.getenv("LANGCHAIN_API_KEY")
    if not api_key:
        logger.error("LANGCHAIN_API_KEY not set.")
        return None

    api_url = os.getenv("LANGCHAIN_ENDPOINT")
    if not api_url:
        logger.error("LANGCHAIN_ENDPOINT not set.")
        return None

    project_name = os.getenv("LANGCHAIN_PROJECT")
    if not project_name:
        logger.error("LANGCHAIN_PROJECT not set.")
        return None

    return LangsmithCredentials(
        api_key=api_key, api_url=api_url, project_name=project_name
    )


def _get_credentials_from_agent(agent: Agent) -> Optional[LangsmithCredentials]:
    if agent.advanced_config.langsmith is None:
        return None
    return agent.advanced_config.langsmith


def get_langsmith(agent: Agent) -> Optional[Langsmith]:
    """
    Environment credentials take precedence over agent credentials.
    """

    if _tracing_enabled_in_env():
        credentials = _get_credentials_from_env()
    else:
        credentials = _get_credentials_from_agent(agent)

    if not credentials:
        logger.info("Not using langsmith")
        return None

    client = Client(
        api_key=credentials.api_key.get_secret_value(),
        api_url=credentials.api_url,
    )
    try:
        project = _get_or_create_project(client, credentials.project_name)
    except Exception:
        logger.info("Not using langsmith")
        logger.exception("Failed to get or create langsmith project")
        return None

    return Langsmith(client=client, project=project)


@lru_cache()
def _get_or_create_project(client: Client, project_name: str) -> TracerSession:
    try:
        return client.read_project(project_name=project_name)
    except LangSmithNotFoundError:
        return client.create_project(project_name)


async def save_langsmith_thread_url(langsmith: Langsmith, thread: Thread) -> None:
    """Save the langsmith URL to the thread metadata if it is not already present."""

    url = (
        f"{langsmith.client._host_url}/o/{langsmith.project.tenant_id}/"
        f"projects/p/{langsmith.project.id}/t/{thread.thread_id}/"
    )
    metadata = thread.metadata or {}
    existing_urls = metadata.get("langsmith_urls", [])
    if url not in existing_urls:
        existing_urls.append(url)
        metadata["langsmith_urls"] = existing_urls
        await get_storage().put_thread(
            user_id=thread.user_id,
            thread_id=thread.thread_id,
            agent_id=thread.agent_id,
            name=thread.name,
            metadata=metadata,
            created_at=thread.created_at,
        )


# Ideally, we'd be using langsmith's `tracing_context` context manager, but currently
# it's broken in such a way that project_name is ignored. The context manager below
# is an adaptation of `tracing_v2_enabled` that allows project_name to be set.
@contextmanager
def trace(
    ls: Optional[Langsmith] = None, tags: Optional[list[str]] = None
) -> Generator[LangChainTracer, None, None]:
    """
    Instruct LangChain to log all runs in context to LangSmith.
    If ls is None, runs won't be logged.
    """

    project_name = ls.project.name if ls else None
    client = ls.client if ls else None
    cb = (
        LangChainTracer(project_name=project_name, tags=tags, client=client)
        if ls is not None
        else None
    )

    try:
        tracing_v2_callback_var.set(cb)
        yield cb
    finally:
        tracing_v2_callback_var.set(None)
