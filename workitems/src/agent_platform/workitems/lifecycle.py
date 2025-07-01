import asyncio
import logging
from contextlib import asynccontextmanager, suppress

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


def workitems_db_is_available_sync() -> bool:
    """
    Returns True if the database is available, False otherwise.
    """
    from sqlalchemy import create_engine, text
    from sqlalchemy.exc import OperationalError

    try:
        engine = create_engine(settings.database_url)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except OperationalError as e:
        logger.warning("Postgres check failed", exc_info=e)
        return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    agent_app = app.state._state["agent_app"] if "agent_app" in app.state._state else None
    agent_server_url = (
        app.state._state["agent_server_url"] if "agent_server_url" in app.state._state else None
    )

    # Create agent client directly using the captured configuration
    if agent_app is not None:
        logger.info(f"Using agent app over ASGI: {agent_app}")
        agent_client = FastAPIAgentClient(agent_app)
    elif agent_server_url is not None:
        logger.info(f"Using agent server url over HTTP: {agent_server_url}")
        agent_client = HttpAgentClient(agent_server_url)
    else:
        raise ValueError("Either agent_app or agent_server_url must be provided")

    worker_task, shutdown_event = _start_background_worker(app, agent_client)

    yield

    logger.info("Shutting down work-items background worker")
    shutdown_event.set()
    with suppress(asyncio.CancelledError):
        await worker_task


def make_workitems_app(
    agent_app: FastAPI | None = None, agent_server_url: str | None = None
) -> FastAPI:
    """Makes the workitems FastAPI app using a FastAPI app for the Agents server or the URL
    of a deployed agent server."""
    # initialize the database
    instance.init_engine(settings.database_url)

    # Make the workitems FastAPI app
    wi_app = FastAPI(lifespan=lifespan)
    wi_app.include_router(workitems_router)

    # Register the standard agent-server exception handlers
    add_exception_handlers(wi_app)

    # Store the state for compatibility (if any code needs it later)
    wi_app.state.agent_app = agent_app
    wi_app.state.agent_server_url = agent_server_url

    return wi_app
