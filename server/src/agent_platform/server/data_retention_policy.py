import asyncio
from datetime import timedelta

import structlog

logger = structlog.get_logger(__name__)

_WORKER_INTERVAL = timedelta(hours=1)


async def retention_policy_worker() -> None:
    from agent_platform.core.configurations.quotas import QuotasService
    from agent_platform.server.file_manager import FileManagerService
    from agent_platform.server.storage import StorageService

    quota_service = await QuotasService.get_instance()
    default_retention_period_days = quota_service.get_agent_thread_retention_period()
    default_retention_period = timedelta(days=default_retention_period_days)
    storage = StorageService.get_instance()

    if deleted_threads := await storage.clean_up_stale_threads(default_retention_period):
        logger.info(f"Cleaned up {len(deleted_threads)} stale threads")
        file_manager = FileManagerService.get_instance()
        for item in deleted_threads:
            try:
                await file_manager.rm(file_id=item.file_id, file_path=item.file_path)
            except Exception as e:
                logger.error(
                    f"Error deleting file id={item.file_id}, file path={item.file_path}: {e}",
                    exc_info=e,
                )

    max_cache_size_bytes = quota_service.get_max_cache_size()
    await storage.evict_old_cache_entries_by_size(max_cache_size_bytes)


async def _worker_loop(interval: timedelta = _WORKER_INTERVAL) -> None:
    # The data retention policy worker can wait a bit (no need to do it immediately,
    # we can wait a bit to avoid overwhelming the startup phase).
    two_mins = 120
    await asyncio.sleep(two_mins)
    while True:
        try:
            await retention_policy_worker()
        except Exception as e:
            logger.error(f"Error during data retention worker: {e}", exc_info=e)

        await asyncio.sleep(interval.total_seconds())


def start_data_retention_worker() -> asyncio.Task:
    """
    Clients are expected to call this function to start the data retention worker and
    then cancel the task when they want to shut down the worker.

    Returns:
        A task that can be cancelled to shut down the worker.
    """
    return asyncio.create_task(_worker_loop())
