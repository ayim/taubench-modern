from contextlib import asynccontextmanager

from fastapi import FastAPI

from agent_platform.server.constants import SystemPaths
from agent_platform.server.otel import setup_otel
from agent_platform.server.storage.option import get_storage


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_otel()
    SystemPaths.upload_dir.mkdir(parents=True, exist_ok=True)

    await get_storage().setup()
    yield
    await get_storage().teardown()

