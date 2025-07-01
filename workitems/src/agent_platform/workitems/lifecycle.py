import asyncio
import logging
from collections.abc import Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI

from agent_platform.server.error_handlers import add_exception_handlers
from agent_platform.workitems.agents import AgentClient
from agent_platform.workitems.agents.client import FastAPIAgentClient, HttpAgentClient

from .api import router as workitems_router
from .config import settings
from .db import instance
from .worker import run_agent, worker_loop

logger = logging.getLogger(__name__)


def _start_background_worker(
    app: FastAPI, agent_client: AgentClient
) -> tuple[asyncio.Task, asyncio.Event]:
    logger.info("Starting work-items background worker")
    shutdown_event = asyncio.Event()

    def _callback(future: asyncio.Task):
        try:
            if exc := future.exception():
                logger.error(f"Background worker error: {exc}", exc_info=exc)

        except asyncio.CancelledError:
            pass

        logger.info("work-items shut down")

    t = asyncio.create_task(
        worker_loop(instance, settings, shutdown_event, agent_client, run_agent)
    )
    t.add_done_callback(_callback)

    return t, shutdown_event


def _create_lifecycle_function(
    agent_app: FastAPI | None = None, agent_server_url: str | None = None
) -> Callable:
    """Create a lifecycle function with the agent configuration captured."""

    @asynccontextmanager
    async def lifecycle(app: FastAPI):
        logger.info("Starting work-items lifecycle")

        # Create agent client directly using the captured configuration
        if agent_app is not None:
            logger.info(f"Using agent app over ASGI: {agent_app}")
            agent_client = FastAPIAgentClient(agent_app)
        elif agent_server_url is not None:
            logger.info(f"Using agent server url over HTTP: {agent_server_url}")
            agent_client = HttpAgentClient(agent_server_url)
        else:
            raise ValueError("Either agent_app or agent_server_url must be provided")

        app.state.worker = _start_background_worker(app, agent_client)
        yield
        await on_teardown(app)

    return lifecycle


def make_workitems_app(
    agent_app: FastAPI | None = None, agent_server_url: str | None = None
) -> FastAPI:
    """Makes the workitems FastAPI app using a FastAPI app for the Agents server or the URL
    of a deployed agent server."""
    # initialize the database
    instance.init_engine(settings.database_url)

    # Create lifecycle function with captured configuration
    lifecycle = _create_lifecycle_function(agent_app, agent_server_url)

    # Make the workitems FastAPI app
    wi_app = FastAPI(lifespan=lifecycle)
    wi_app.include_router(workitems_router)

    # Register the standard agent-server exception handlers
    add_exception_handlers(wi_app)

    # Store the state for compatibility (if any code needs it later)
    wi_app.state.agent_app = agent_app
    wi_app.state.agent_server_url = agent_server_url

    return wi_app


async def on_teardown(app: FastAPI) -> None:
    """
    Stop the background worker against the given FastAPI app.
    """
    # Pull off the state
    if hasattr(app, "state") and hasattr(app.state, "worker"):
        # Try to gracefully shutdown the worker
        logger.info("Stopping work-items background worker")
        app.state.worker.cancel()

    logger.info("work-items shut down")
