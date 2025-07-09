import asyncio
from contextlib import AsyncExitStack, asynccontextmanager, suppress

import structlog
from fastapi import FastAPI
from starlette.applications import Starlette

from agent_platform.core.responses.streaming.stream_pipe import ResponseStreamPipe
from agent_platform.server.constants import SystemConfig, SystemPaths

# Import the data migration function
from agent_platform.server.scripts.migration.auto_migrate import run_automatic_migration
from agent_platform.server.storage import StorageService

# Use our new telemetry module instead of the old otel module
from agent_platform.server.telemetry import setup_telemetry
from agent_platform.server.work_items import run_agent, worker_loop

logger = structlog.get_logger(__name__)


def _start_work_items_background_worker() -> tuple[asyncio.Task, asyncio.Event]:
    logger.info("Starting work-items background worker")
    shutdown_event = asyncio.Event()

    def _callback(future: asyncio.Task):
        try:
            if exc := future.exception():
                logger.error(f"Background worker error: {exc}", exc_info=exc)

        except asyncio.CancelledError:
            pass

        logger.info("work-items shut down")

    t = asyncio.create_task(worker_loop(shutdown_event, run_agent))
    t.add_done_callback(_callback)

    return t, shutdown_event


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Set up our v2 telemetry
    tracer_provider, meter_provider = setup_telemetry()

    # Original code
    SystemPaths.upload_dir.mkdir(parents=True, exist_ok=True)
    await StorageService.get_instance().setup()

    # IMPORTANT: Order of operations is critical here!
    # Current sequence: DB Migrations (create v2 tables) -> Data migration (v1 to v2)
    # This works for direct v1->v2 upgrades, but if we introduce additional migration
    # files in the future, customers upgrading from version x->z (skipping y) may
    # encounter issues if the data migration expects a specific DB schema state.

    # Run data migration from v1 to v2 after database setup
    # This is safe to run multiple times and will only migrate if needed
    migration_success = await run_automatic_migration()
    if not migration_success:
        logger.warning("Data migration from v1 to v2 failed, but server will continue")

    # Start the work-items background worker only if enabled in configuration
    work_items_task: asyncio.Task | None = None
    work_items_shutdown_event: asyncio.Event | None = None

    if SystemConfig.enable_workitems:
        work_items_task, work_items_shutdown_event = _start_work_items_background_worker()
    else:
        logger.info("Work-items feature disabled; background worker will not start")

    try:
        yield

    finally:
        # Shut down the background worker only if it was started
        if work_items_shutdown_event is not None and work_items_task is not None:
            logger.info("Shutting down work-items background worker")
            work_items_shutdown_event.set()

            with suppress(asyncio.CancelledError):
                logger.info("Waiting for work-items background worker to shut down")
                await work_items_task

        # Shutdown separate diff pool for ResponseStreamPipe
        logger.info("Shutting down ResponseStreamPipe diff pool")
        ResponseStreamPipe._DIFF_POOL.shutdown(wait=False)

        logger.info("Shutting down storage")
        await StorageService.get_instance().teardown()
        logger.info("Storage shut down")


def create_combined_lifespan(*mcp_apps: Starlette):
    @asynccontextmanager
    async def _combined_lifespan(main_app: FastAPI):
        async with AsyncExitStack() as stack:
            await stack.enter_async_context(lifespan(main_app))
            for app in mcp_apps:
                await stack.enter_async_context(app.router.lifespan_context(main_app))
            yield

    return _combined_lifespan
