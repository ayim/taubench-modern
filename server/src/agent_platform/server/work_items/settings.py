from dataclasses import dataclass
from os import getenv


@dataclass(frozen=True)
class Settings:
    worker_interval: int = int(getenv("WORKITEMS_WORKER_INTERVAL", "30"))
    max_batch_size: int = int(getenv("WORKITEMS_MAX_BATCH_SIZE", "10"))
    work_item_timeout: float = float(getenv("WORKITEMS_WORK_ITEM_TIMEOUT", "14400"))  # 4 hours


WORK_ITEMS_SETTINGS = Settings()


def get_workroom_url() -> str | None:
    """The URL set to the SEMA4AI_AGENT_SERVER_WORKROOM_URL env var may or may not have
    a trailing slash. This function ensures that if the URL is set, it has a trailing slash.
    """
    url = getenv("SEMA4AI_AGENT_SERVER_WORKROOM_URL")
    if url:
        if url.endswith("/"):
            return url
        return url + "/"
    return None


WORKSPACE_ID = getenv("SEMA4AI_AGENT_SERVER_WORKSPACE_ID", "no-workspace-id")
