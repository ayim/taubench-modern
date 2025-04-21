from contextlib import asynccontextmanager

from fastapi import FastAPI

from agent_platform.server.constants import SystemPaths
from agent_platform.server.otel import setup_otel
from agent_platform.server.storage import StorageService


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_otel()
    SystemPaths.upload_dir.mkdir(parents=True, exist_ok=True)

    await StorageService.get_instance().setup()
    yield
    await StorageService.get_instance().teardown()
