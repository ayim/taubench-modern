"""Tests for the ShutdownManager."""

import asyncio

import pytest
from pyleak import no_event_loop_blocking, no_task_leaks

from agent_platform.server.shutdown_manager import ShutdownManager


class TestShutdownManager:
    """Test the ShutdownManager singleton."""

    def setup_method(self):
        """Reset the shutdown manager before each test."""
        ShutdownManager.get_instance()._reset_for_testing()

    def test_singleton_and_initial_state(self):
        """Test singleton pattern and initial state."""
        manager1 = ShutdownManager.get_instance()
        manager2 = ShutdownManager.get_instance()
        assert manager1 is manager2

        # Test initial state using class methods
        assert ShutdownManager.is_healthy() is True
        assert ShutdownManager.is_draining() is False

    @pytest.mark.asyncio
    async def test_draining_state_transitions_and_idempotency(self):
        """Test draining state transitions, idempotency, and concurrent calls."""
        # Initially healthy
        assert ShutdownManager.is_healthy() is True
        assert ShutdownManager.is_draining() is False

        # Start draining without tasks
        await ShutdownManager.drain_background_workers()
        assert ShutdownManager.is_draining() is True
        assert ShutdownManager.is_healthy() is False

        # Test idempotency - call again
        await ShutdownManager.drain_background_workers()
        assert ShutdownManager.is_draining() is True

        # Test concurrent calls
        tasks = [asyncio.create_task(ShutdownManager.drain_background_workers()) for _ in range(5)]
        await asyncio.gather(*tasks)
        assert ShutdownManager.is_draining() is True

        # Reset back to healthy
        ShutdownManager.get_instance()._reset_for_testing()
        assert ShutdownManager.is_healthy() is True
        assert ShutdownManager.is_draining() is False

    @pytest.mark.asyncio
    async def test_worker_registration_and_draining(self):
        """Test worker registration, unregistration, and draining behavior."""

        # Create worker functions
        async def worker1():
            await asyncio.sleep(0.2)

        async def worker2():
            await asyncio.sleep(0.1)

        async def failing_worker():
            await asyncio.sleep(0.1)
            raise ValueError("Worker failed")

        # Test registration
        ShutdownManager.register_drainable_background_worker("worker1", worker1)
        ShutdownManager.register_drainable_background_worker("worker2", worker2)
        ShutdownManager.register_drainable_background_worker("failing_worker", failing_worker)

        # Verify registration
        manager = ShutdownManager.get_instance()
        assert len(manager._drainable_background_tasks) == 3
        assert len(manager._shutdown_events) == 3
        assert "worker1" in manager._drainable_background_tasks
        assert "worker2" in manager._drainable_background_tasks
        assert "failing_worker" in manager._drainable_background_tasks

        # Test draining waits for workers and handles exceptions
        drain_start = asyncio.get_event_loop().time()
        await ShutdownManager.drain_background_workers()
        drain_end = asyncio.get_event_loop().time()

        # Should have waited for the longest worker (worker1: 0.2s)
        assert drain_end - drain_start >= 0.2
        assert ShutdownManager.is_draining() is True

        # Test unregistration
        ShutdownManager.unregister_drainable_background_worker("worker1")
        assert "worker1" not in manager._drainable_background_tasks
        assert "worker1" not in manager._shutdown_events

    @pytest.mark.asyncio
    async def test_worker_shutdown_checking(self):
        """Test that workers can check if they should shutdown."""
        # Create a worker that checks shutdown state
        shutdown_checked = False

        async def shutdown_aware_worker():
            nonlocal shutdown_checked
            while not ShutdownManager.should_worker_shutdown("test_worker"):
                await asyncio.sleep(0.01)
            shutdown_checked = True

        ShutdownManager.register_drainable_background_worker("test_worker", shutdown_aware_worker)

        # Initially should not be shutting down
        assert not ShutdownManager.should_worker_shutdown("test_worker")

        # Start draining
        await ShutdownManager.drain_background_workers()

        # The worker should have detected the shutdown signal
        assert shutdown_checked

    @pytest.mark.asyncio
    async def test_no_task_leaks_during_normal_operation(self):
        """Test that ShutdownManager doesn't leak asyncio tasks during normal operation."""
        async with no_task_leaks():
            # Create and register workers
            async def worker1():
                await asyncio.sleep(0.1)

            async def worker2():
                await asyncio.sleep(0.05)

            ShutdownManager.register_drainable_background_worker("worker1", worker1)
            ShutdownManager.register_drainable_background_worker("worker2", worker2)

            # Wait for workers to complete naturally
            await asyncio.sleep(0.2)

            # Drain should clean up all tasks
            await ShutdownManager.drain_background_workers()

    @pytest.mark.asyncio
    async def test_no_task_leaks_during_draining(self):
        """Test that draining doesn't leak tasks even with failing workers."""
        async with no_task_leaks():
            # Create workers including one that fails
            async def successful_worker():
                await asyncio.sleep(0.1)

            async def failing_worker():
                await asyncio.sleep(0.05)
                raise ValueError("Worker failed")

            ShutdownManager.register_drainable_background_worker("successful", successful_worker)
            ShutdownManager.register_drainable_background_worker("failing", failing_worker)

            # Drain should handle exceptions and clean up all tasks
            await ShutdownManager.drain_background_workers()

    @pytest.mark.asyncio
    async def test_no_event_loop_blocking_during_draining(self):
        """Test that draining operations don't block the event loop."""
        async with no_event_loop_blocking(threshold=0.1):
            # Create multiple workers
            async def worker():
                await asyncio.sleep(0.05)

            for i in range(5):
                ShutdownManager.register_drainable_background_worker(f"worker_{i}", worker)

            # Draining should not block the event loop
            await ShutdownManager.drain_background_workers()

    @pytest.mark.asyncio
    async def test_concurrent_draining_no_leaks(self):
        """Test that concurrent draining calls don't leak tasks."""
        async with no_task_leaks():
            # Create workers
            async def worker():
                await asyncio.sleep(0.1)

            ShutdownManager.register_drainable_background_worker("worker1", worker)
            ShutdownManager.register_drainable_background_worker("worker2", worker)

            # Multiple concurrent drain calls should be idempotent and not leak
            drain_tasks = [
                asyncio.create_task(ShutdownManager.drain_background_workers()) for _ in range(3)
            ]
            await asyncio.gather(*drain_tasks)

    @pytest.mark.asyncio
    async def test_worker_unregistration_no_leaks(self):
        """Test that unregistering workers doesn't leak tasks."""
        async with no_task_leaks():
            # Create a worker that completes quickly
            async def quick_worker():
                await asyncio.sleep(0.01)

            ShutdownManager.register_drainable_background_worker("quick", quick_worker)

            # Wait for worker to complete
            await asyncio.sleep(0.05)

            # Unregister should clean up properly
            ShutdownManager.unregister_drainable_background_worker("quick")

            # Drain should be safe even with no workers
            await ShutdownManager.drain_background_workers()
