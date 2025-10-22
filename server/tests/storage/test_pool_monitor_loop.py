import asyncio


class _DummyPool:
    def __init__(self):
        self._stats = "stats"
        self.requested_times = 0

    def get_stats(self):
        self.requested_times += 1
        return self._stats

    def status(self):
        self.requested_times += 1
        return self._stats


class _DummyEngine:
    def __init__(self):
        self.pool = _DummyPool()


class _DummyStorage:
    def __init__(self):
        self._pool = _DummyPool()
        self._sa_engine = _DummyEngine()

    async def get_pool(self):
        return self._pool

    async def get_sa_engine(self):
        return self._sa_engine


async def test_pool_monitor_loop():
    from agent_platform.server.storage.option import StorageService
    from agent_platform.server.storage.pool_monitor import PoolMonitorSettings, pool_monitor_loop

    shutdown_event = asyncio.Event()
    dummy_storage_instance = _DummyStorage()

    default_settings = PoolMonitorSettings.get_default_instance()
    try:
        StorageService.set_for_testing(dummy_storage_instance)  # type: ignore
        PoolMonitorSettings.set_instance(PoolMonitorSettings(check_interval=0.1))  # type: ignore

        task = asyncio.create_task(pool_monitor_loop(shutdown_event))
        await asyncio.sleep(1)

        assert dummy_storage_instance._pool.requested_times == 10
        assert dummy_storage_instance._sa_engine.pool.requested_times == 10

        shutdown_event.set()
        await task
        assert dummy_storage_instance._pool.requested_times == 10
        assert dummy_storage_instance._sa_engine.pool.requested_times == 10

        assert task.exception() is None
    finally:
        PoolMonitorSettings.set_instance(default_settings)
        StorageService.reset()
