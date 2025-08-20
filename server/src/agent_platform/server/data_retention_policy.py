import asyncio
from datetime import timedelta

import structlog

from agent_platform.core.configurations.quotas import QuotasService
from agent_platform.server.file_manager import FileManagerService
from agent_platform.server.storage import StorageService

logger = structlog.get_logger(__name__)

WORKER_INTERVAL = timedelta(hours=1)


async def retention_policy_worker():
    quota_service = await QuotasService.get_instance()
    default_retention_period_days = quota_service.get_agent_thread_retention_period()
    default_retention_period = timedelta(days=default_retention_period_days)

    if not (
        deleted_threads := await StorageService.get_instance().clean_up_stale_threads(
            default_retention_period
        )
    ):
        return

    file_manager = FileManagerService.get_instance()
    for item in deleted_threads:
        try:
            await file_manager.rm(file_id=item.file_id, file_path=item.file_path)
        except Exception as e:
            logger.error(
                f"Error deleting file id={item.file_id}, file path={item.file_path}: {e}",
                exc_info=e,
            )


async def _worker_loop():
    while True:
        try:
            await retention_policy_worker()
        except Exception as e:
            logger.error(f"Error during data retention worker: {e}", exc_info=e)

        await asyncio.sleep(WORKER_INTERVAL.total_seconds())


def start_data_retention_worker() -> asyncio.Task:
    return asyncio.create_task(_worker_loop())
