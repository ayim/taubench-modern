from dataclasses import dataclass
from os import getenv


@dataclass(frozen=True)
class Settings:
    worker_interval: int = int(getenv("WORKITEMS_WORKER_INTERVAL", "30"))
    max_batch_size: int = int(getenv("WORKITEMS_MAX_BATCH_SIZE", "10"))
    work_item_timeout: float = float(getenv("WORKITEMS_WORK_ITEM_TIMEOUT", "14400"))  # 4 hours


WORK_ITEMS_SETTINGS = Settings()
