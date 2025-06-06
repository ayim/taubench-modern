from contextlib import AsyncExitStack, asynccontextmanager

from fastapi import FastAPI
from starlette.applications import Starlette

from agent_platform.server.constants import SystemPaths

# Import the data migration function
from agent_platform.server.scripts.migration.auto_migrate import run_automatic_migration
from agent_platform.server.storage import StorageService

# Use our new telemetry module instead of the old otel module
from agent_platform.server.telemetry import setup_telemetry


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
        # Log the failure but don't crash the server - the migration module
        # already logs detailed error information
        import structlog

        logger = structlog.get_logger(__name__)
        logger.warning("Data migration from v1 to v2 failed, but server will continue")

    yield

    # Cleanup
    await StorageService.get_instance().teardown()
    # No need to shutdown providers - they'll be garbage collected


def create_combined_lifespan(mcp_app: Starlette):
    @asynccontextmanager
    async def _combined_lifespan(main_app: FastAPI):
        async with AsyncExitStack() as stack:
            await stack.enter_async_context(lifespan(main_app))
            await stack.enter_async_context(mcp_app.router.lifespan_context(main_app))
            yield

    return _combined_lifespan
