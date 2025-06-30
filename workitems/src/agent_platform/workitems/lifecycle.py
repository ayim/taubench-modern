import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from agent_platform.server.error_handlers import add_exception_handlers

from .api import router as workitems_router
from .config import settings
from .db import instance
from .worker import run_agent, worker_loop

logger = logging.getLogger(__name__)


def _start_background_worker(app: FastAPI) -> tuple[asyncio.Task, asyncio.Event]:
    logger.info("Starting work-items background worker")
    shutdown_event = asyncio.Event()

    def _callback(future: asyncio.Task):
        try:
            if exc := future.exception():
                logger.error(f"Background worker error: {exc}", exc_info=exc)

        except asyncio.CancelledError:
            pass

        logger.info("work-items shut down")

    t = asyncio.create_task(worker_loop(instance, settings, shutdown_event, run_agent))
    t.add_done_callback(_callback)

    return t, shutdown_event


@asynccontextmanager
async def lifecycle(app: FastAPI):
    logger.info("Starting work-items lifecycle")
    background_worker, shutdown_event = _start_background_worker(app)
    logger.debug("Worker life-cycle started.")

    yield

    logger.info("Shutting down work-items shut down")
    shutdown_event.set()


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
