import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .api import router as workitems_router
from .config import settings
from .db import instance
from .worker import worker_loop

logger = logging.getLogger(__name__)


def _start_background_worker(app: FastAPI) -> asyncio.Task:
    shutdown_event = asyncio.Event()

    async def worker() -> None:
        await worker_loop(app.state.workitems.db_manager, shutdown_event)

    t = asyncio.create_task(worker())
    # TODO is this correct?
    t.add_done_callback(lambda _: shutdown_event.set())

    return t


@asynccontextmanager
async def lifecycle(app: FastAPI):
    app.state.worker = _start_background_worker(app)
    yield
    await on_teardown(app)


def make_app() -> FastAPI:
    # initialize the database
    instance.init_engine(settings.database_url)

    app = FastAPI(lifespan=lifecycle)
    app.include_router(workitems_router)

    return app


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
