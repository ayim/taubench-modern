from agent_platform.core.configurations.quotas import QuotasService
from agent_platform.server.storage.option import StorageService


class TestQuotasServiceIntegration:
    async def test_set_and_get_max_parallel_work_items_round_trip(self, storage):
        StorageService.set_for_testing(storage)
        QuotasService._instance = None

        quotas_service = await QuotasService.get_instance()
        default_value = quotas_service.get_max_parallel_work_items_in_process()
        assert default_value == 10

        new_value = "25"
        await quotas_service.set_max_parallel_work_items_in_process(new_value)

        current_value = quotas_service.get_max_parallel_work_items_in_process()
        assert current_value == 25

        QuotasService._instance = None
        fresh_quotas_service = await QuotasService.get_instance()
        persisted_value = fresh_quotas_service.get_max_parallel_work_items_in_process()

        assert persisted_value == 25

    async def test_background_worker_uses_updated_quota_value(self, storage):
        StorageService.set_for_testing(storage)
        QuotasService._instance = None

        quotas_service = await QuotasService.get_instance()
        await quotas_service.set_max_parallel_work_items_in_process("15")

        worker_quotas_service = await QuotasService.get_instance()
        max_batch_size = worker_quotas_service.get_max_parallel_work_items_in_process()

        assert max_batch_size == 15

    async def test_regression__initialize_from_storage(self, storage):
        StorageService.set_for_testing(storage)
        await StorageService.get_instance().set_config(QuotasService.MAX_AGENTS, {"current": "99"})

        QuotasService._instance = None

        quotas_service = await QuotasService.get_instance()
        assert quotas_service.get_max_agents() == 99

    def teardown_method(self):
        QuotasService._instance = None
        StorageService.reset()
