from dataclasses import dataclass
from os import getenv
from typing import Literal


def _execution_mode() -> Literal["batch", "slots"]:
    # Default to batch mode
    val = getenv("WORKITEMS_EXECUTION_MODE", "batch").strip().lower()
    if val not in ["batch", "slots"]:
        raise ValueError(f"Invalid work-item execution mode: {val}")
    return val  # type: ignore[return-value]


def _txn_log() -> bool:
    val = getenv("WORKITEMS_TRANSACTION_LOG", "false").strip().lower()
    if val not in ["true", "false"]:
        raise ValueError(f"Invalid work-item transaction log: {val}")
    return val == "true"


@dataclass(frozen=True)
class Settings:
    worker_interval: int = int(getenv("WORKITEMS_WORKER_INTERVAL", "10"))
    max_batch_size: int = int(getenv("WORKITEMS_MAX_BATCH_SIZE", "10"))
    execution_mode: Literal["batch", "slots"] = _execution_mode()
    enable_transaction_log: bool = _txn_log()


WORK_ITEMS_SETTINGS = Settings()
