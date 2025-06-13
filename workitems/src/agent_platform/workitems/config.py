from __future__ import annotations

from dataclasses import dataclass
from os import getenv


@dataclass(frozen=True)
class Settings:
    agent_server_url: str = getenv("AGENT_SERVER_URL", "http://localhost:8000")
    database_url: str = getenv(
        "SEMA4AI_WORKITEMS_DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@localhost/work_items",
    )
    worker_interval: int = int(getenv("WORKITEMS_WORKER_INTERVAL", "60"))


settings = Settings()
