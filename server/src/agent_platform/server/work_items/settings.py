from dataclasses import dataclass
from os import getenv


@dataclass(frozen=True)
class Settings:
    worker_interval: int = int(getenv("WORKITEMS_WORKER_INTERVAL", "30"))
    max_batch_size: int = int(getenv("WORKITEMS_MAX_BATCH_SIZE", "10"))
    work_item_timeout: float = float(getenv("WORKITEMS_WORK_ITEM_TIMEOUT", "1200"))  # 20 minutes


WORK_ITEMS_SETTINGS = Settings()


def get_workroom_url():
    """The URL set to the SEMA4AI_AGENT_SERVER_WORKROOM_URL env var may or may not have
    a trailing slash. This function ensures that the URL has a trailing slash.
    """
    url = getenv("SEMA4AI_AGENT_SERVER_WORKROOM_URL", "http://localhost:8000")
    if url.endswith("/"):
        return url
    return url + "/"


WORKROOM_URL = get_workroom_url()
TENANT_ID = getenv("SEMA4AI_AGENT_SERVER_TENANT_ID", "no-tenant-id")
