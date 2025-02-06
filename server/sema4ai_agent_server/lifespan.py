from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from sema4ai_agent_server.storage.option import get_storage
from sema4ai_agent_server.storage.v2.option_v2 import get_storage_v2


@asynccontextmanager
async def lifespan(app: FastAPI):
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.UnicodeDecoder(),
            structlog.stdlib.render_to_log_kwargs,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    await get_storage().setup()
    await get_storage_v2().setup_v2()
    yield
    await get_storage().teardown()
    await get_storage_v2().teardown_v2()

