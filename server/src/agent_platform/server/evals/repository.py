from collections.abc import Sequence

from agent_platform.core.evals.types import Trial, TrialStatus
from agent_platform.server.constants import EVALS_SYSTEM_USER_SUB
from agent_platform.server.evals.background_worker import TaskRepository
from agent_platform.server.storage.option import StorageService


# TODO I need to update user id, i.e. system user id
class ScenarioRunTrialRepository(TaskRepository[Trial]):
    def __init__(self) -> None:
        self.storage = StorageService.get_instance()

    async def get_pending_task_ids(self, max_batch_size: int) -> Sequence[str]:
        return await self.storage.get_pending_trial_ids(max_batch_size)

    async def get_tasks_by_ids(self, task_ids: Sequence[str]) -> Sequence[Trial]:
        return await self.storage.get_trials_by_ids(list(task_ids))

    async def mark_incomplete_tasks_as_error(self, task_ids: Sequence[str]) -> None:
        await self.storage.mark_trials_as_failed(list(task_ids))

    async def get_task(self, task: Trial) -> Trial | None:
        try:
            return await self.storage.get_trial(task.trial_id)
        except Exception:
            return None

    async def set_status_if_not_canceled(self, task: Trial, status: str, error: str | None) -> None:
        try:
            system_user_id = await self.storage.get_system_user_id()
        except Exception:
            system_user, _ = await self.storage.get_or_create_user(EVALS_SYSTEM_USER_SUB)
            system_user_id = system_user.user_id

        await self.storage.update_trial_status_if_not_canceled(
            task.trial_id, system_user_id, TrialStatus(status), error
        )
