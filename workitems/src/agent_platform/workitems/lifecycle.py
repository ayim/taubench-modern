import asyncio
import logging
from contextlib import asynccontextmanager

from agent_platform.server.error_handlers import add_exception_handlers
from fastapi import FastAPI

from .api import router as workitems_router
from .config import settings
from .db import instance
from .worker import execute_work_item, run_agent, worker_loop

logger = logging.getLogger(__name__)


def _start_background_worker(app: FastAPI) -> asyncio.Task:
    logger.info("Starting work-items background worker")
    shutdown_event = asyncio.Event()

    # Compose the real work function by plugging in `run_agent`
    async def work_func(session, item) -> bool:
        return await execute_work_item(session, item, run_agent)

    t = asyncio.create_task(worker_loop(instance, settings, shutdown_event, work_func))

    # TODO is this correct?
    t.add_done_callback(lambda _: shutdown_event.set())

    return t


@asynccontextmanager
async def lifecycle(app: FastAPI):
    logger.info("Starting work-items lifecycle")
    app.state.worker = _start_background_worker(app)
    yield
    await on_teardown(app)


def make_workitems_app(
    agent_app: FastAPI | None = None, agent_server_url: str | None = None
) -> FastAPI:
    """Makes the workitems FastAPI app using a FastAPI app for the Agents server or the URL
    of a deployed agent server."""
    # initialize the database
    instance.init_engine(settings.database_url)

    # Make the workitems FastAPI app
    wi_app = FastAPI(lifespan=lifecycle)
    wi_app.include_router(workitems_router)

    # Register the standard agent-server exception handlers
    add_exception_handlers(wi_app)

    if agent_app is None and agent_server_url is None:
        raise ValueError("Either agent_app or agent_server_url must be provided")

    if agent_app is not None and agent_server_url is not None:
        raise ValueError("Only one of agent_app or agent_server_url must be provided")

    # Store the state for either the FastApi app or the agent server url
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
