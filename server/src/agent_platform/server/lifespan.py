from contextlib import AsyncExitStack, asynccontextmanager

import structlog
from fastapi import FastAPI
from starlette.applications import Starlette

from agent_platform.core.configurations.quotas import QuotasService
from agent_platform.core.evals.types import Trial
from agent_platform.core.platforms.llms_metadata_loader import llms_metadata_loader
from agent_platform.core.responses.streaming.stream_pipe import ResponseStreamPipe
from agent_platform.server.constants import SystemConfig, SystemPaths
from agent_platform.server.data_retention_policy import start_data_retention_worker
from agent_platform.server.evals.background_worker import (
    WORKER_NAME as EVALS_WORKER_NAME,
)
from agent_platform.server.evals.background_worker import (
    QueueSettings,
    WorkQueue,
)
from agent_platform.server.evals.repository import ScenarioRunTrialRepository
from agent_platform.server.evals.run_scenario import run_evaluations, run_scenario

# Import the data migration function
from agent_platform.server.scripts.migration.auto_migrate import run_automatic_migration
from agent_platform.server.secret_manager.option import SecretService

# Use our new telemetry module instead of the old otel module
from agent_platform.server.shutdown_manager import ShutdownManager
from agent_platform.server.storage import StorageService
from agent_platform.server.telemetry import setup_telemetry
from agent_platform.server.work_items.background_worker import (
    WORKER_NAME as WORK_ITEMS_WORKER_NAME,
)
from agent_platform.server.work_items.background_worker import (
    worker_loop,
)

logger = structlog.get_logger(__name__)


def _start_work_items_background_worker() -> None:
    logger.info("Starting work-items background worker")

    ShutdownManager.register_drainable_background_worker(WORK_ITEMS_WORKER_NAME, worker_loop)


def _start_evals_background_worker() -> None:
    logger.info("Starting evals background worker")

    queue = WorkQueue[Trial](
        repository=ScenarioRunTrialRepository(),
        runner=run_scenario,
        validator=run_evaluations,
        settings=QueueSettings(
            worker_interval=30,
            batch_timeout=14400,
            max_parallel_in_process=10,
        ),
    )

    ShutdownManager.register_drainable_background_worker(EVALS_WORKER_NAME, queue.worker_loop)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Set up our v2 telemetry
    tracer_provider, meter_provider = setup_telemetry()

    # Initialize platform data (LLMs metadata) early in startup
    logger.info("Initializing platform metadata...")
    try:
        llms_metadata_loader.load_data()
        logger.info(
            f"Loaded {llms_metadata_loader.model_count} LLM model metadata entries into memory",
        )
    except Exception as e:
        logger.error(f"Failed to initialize platform metadata: {e!r}", exc_info=e)
        raise

    # Original code
    SystemPaths.upload_dir.mkdir(parents=True, exist_ok=True)

    SecretService.get_instance().setup()
    logger.info("Secret Service initialized")

    await StorageService.get_instance().setup()
    logger.info("Storage Service initialized")

    # Initialize QuotasService singleton with configuration values from storage
    await QuotasService.get_instance()
    logger.info("QuotasService initialized")

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
    if SystemConfig.enable_workitems:
        _start_work_items_background_worker()
    else:
        logger.info("Work-items feature disabled; background worker will not start")

    if SystemConfig.enable_evals:
        _start_evals_background_worker()
    else:
        logger.info("Evals feature disabled; background worker will not start")

    data_retention_task = start_data_retention_worker()

    try:
        yield

    finally:
        # Start graceful shutdown process
        await ShutdownManager.drain_background_workers()

        data_retention_task.cancel()

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
