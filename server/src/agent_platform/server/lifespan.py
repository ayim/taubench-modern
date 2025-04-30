from contextlib import asynccontextmanager

from fastapi import FastAPI

from agent_platform.server.constants import SystemPaths
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

    yield

    # Cleanup
    await StorageService.get_instance().teardown()
    # No need to shutdown providers - they'll be garbage collected
