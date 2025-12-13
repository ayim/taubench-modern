"""Shutdown manager for graceful server shutdown."""

import asyncio
import logging
from collections.abc import Callable, Coroutine
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ShutdownState(Enum):
    """States for the shutdown manager."""

    HEALTHY = "healthy"
    DRAINING = "draining"


class ShutdownManager:
    """Singleton manager for graceful server shutdown.

    Manages the shutdown state and coordinates graceful shutdown of multiple background workers.
    """

    _instance: "ShutdownManager | None" = None
    _state: ShutdownState = ShutdownState.HEALTHY
    _drainable_background_tasks: dict[str, asyncio.Task]
    _shutdown_events: dict[str, asyncio.Event]
    _shutdown_tasks: dict[str, asyncio.Task]

    def __init__(self):
        """Private constructor. Use get_instance() to get the singleton instance."""
        raise RuntimeError(
            """
            ShutdownManager is a singleton. Use ShutdownManager.get_instance()
            instead of direct instantiation.
            """
        )

    @classmethod
    def _create(cls) -> "ShutdownManager":
        """Private method to create the singleton instance internally."""
        instance = cls.__new__(cls)

        instance._state = ShutdownState.HEALTHY
        instance._drainable_background_tasks = {}
        instance._shutdown_events = {}
        instance._shutdown_tasks = {}

        logger.info(f"ShutdownManager initialized in {instance._state.value} state")
        return instance

    @classmethod
    def get_instance(cls) -> "ShutdownManager":
        """Get the singleton instance of ShutdownManager."""
        if cls._instance is None:
            cls._instance = cls._create()
        return cls._instance

    # Class methods for convenient access to singleton functionality
    @classmethod
    def state(cls) -> ShutdownState:
        """Get the current shutdown state."""
        return cls.get_instance()._state

    @classmethod
    def is_healthy(cls) -> bool:
        """Check if the server is in healthy state."""
        return cls.get_instance()._state == ShutdownState.HEALTHY

    @classmethod
    def is_draining(cls) -> bool:
        """Check if the server is draining."""
        return cls.get_instance()._state == ShutdownState.DRAINING

    @classmethod
    def _get_shutdown_event(cls, worker_name: str) -> asyncio.Event | None:
        """Get the shutdown event for a specific worker.

        Args:
            worker_name: Name of the worker to get the shutdown task for
        """
        instance = cls.get_instance()
        ev = instance._shutdown_events.get(worker_name)
        if ev is None:
            logger.warning(f"Shutdown event requested for unknown (or finished) worker: {worker_name}")

        return ev

    @classmethod
    def get_shutdown_task(cls, worker_name: str) -> asyncio.Task | None:
        """Get the shutdown task for a specific worker. Useful
        for waiting on a worker to shutdown.

        Args:
            worker_name: Name of the worker to get the shutdown task for
        """
        instance = cls.get_instance()
        shutdown_task = instance._shutdown_tasks.get(worker_name)
        if shutdown_task is not None:
            return shutdown_task

        # It's not there, create it now based on the shutdown event
        shutdown_event = instance._get_shutdown_event(worker_name)
        if shutdown_event is None:
            logger.warning(f"Shutdown task requested for unknown (or finished) worker: {worker_name}")
            return None
        shutdown_task = asyncio.create_task(shutdown_event.wait())
        instance._shutdown_tasks[worker_name] = shutdown_task
        return shutdown_task

    @classmethod
    def should_worker_shutdown(cls, worker_name: str) -> bool:
        """Check if a specific worker should shutdown.

        Args:
            worker_name: Name of the worker to check

        Returns:
            True if the worker should shutdown, False otherwise
        """
        shutdown_event = cls._get_shutdown_event(worker_name)
        if shutdown_event is None:
            return False
        return shutdown_event.is_set()

    @classmethod
    def register_drainable_background_worker(
        cls, name: str, worker_func: Callable[[], Coroutine[Any, Any, None]]
    ) -> None:
        """Register a drainable background worker with task creation and shutdown event management.

        Args:
            name: Human-readable name for the worker
            worker_func: The worker function to run
        """
        instance = cls.get_instance()
        # Create a shutdown event for this worker
        shutdown_event = asyncio.Event()
        instance._shutdown_events[name] = shutdown_event

        # Create the task (workers check shutdown via shutdown manager)
        task = asyncio.create_task(worker_func())

        # Add callback to handle cleanup
        task.add_done_callback(cls._create_worker_callback(name))

        # Register the task
        instance._drainable_background_tasks[name] = task

        logger.debug(f"Registered background worker: {name}")

    @classmethod
    def unregister_drainable_background_worker(cls, name: str) -> None:
        """Unregister a completed drainable background worker.

        Args:
            name: Name of the worker to unregister
        """
        instance = cls.get_instance()
        instance._drainable_background_tasks.pop(name, None)
        instance._shutdown_events.pop(name, None)
        instance._shutdown_tasks.pop(name, None)
        logger.debug(f"Unregistered background worker: {name}")

    @classmethod
    async def drain_background_workers(cls) -> None:
        """Start the draining process.

        This will:
        1. Set state to DRAINING
        2. Signal all shutdown events to stop workers
        3. Wait for all registered tasks to complete
        """
        instance = cls.get_instance()
        if instance._state == ShutdownState.DRAINING:
            logger.info("Already in DRAINING state")
            return

        logger.info("Starting graceful shutdown - entering DRAINING state")
        instance._state = ShutdownState.DRAINING

        # Signal all shutdown events to stop workers
        shutdown_events = instance._shutdown_events
        if shutdown_events:
            event_names = list(shutdown_events.keys())
            logger.info(f"Signaling shutdown events for {len(shutdown_events)} workers: {event_names}")
            for shutdown_event in shutdown_events.values():
                shutdown_event.set()

        # Wait for all active tasks to complete
        tasks = instance._drainable_background_tasks
        if tasks:
            task_names = list(tasks.keys())
            task_count = len(tasks)
            logger.info(f"Waiting for {task_count} background tasks to complete: {task_names}")

            # Wait for all tasks to complete, capturing exceptions
            results = await asyncio.gather(*tasks.values(), return_exceptions=True)

            # Check for exceptions in results
            exceptions = [result for result in results if isinstance(result, Exception)]
            if exceptions:
                logger.warning(
                    f"{len(exceptions)} background tasks failed during shutdown: {[str(exc) for exc in exceptions]}"
                )
            else:
                logger.info("All background tasks completed")

        logger.info("Draining complete - ready for shutdown")

    @classmethod
    def _create_worker_callback(cls, name: str):
        """Create a callback function for worker cleanup."""

        def _callback(future: asyncio.Task):
            try:
                if exc := future.exception():
                    logger.error(f"Background worker '{name}' error: {exc}", exc_info=exc)
            except asyncio.CancelledError:
                pass

            # Unregister from shutdown manager when done
            cls.unregister_drainable_background_worker(name)
            logger.info(f"{name} shut down")

        return _callback

    def _reset_for_testing(self) -> None:
        """Reset the shutdown manager to healthy state.

        This should only be used for testing purposes.
        """
        self._state = ShutdownState.HEALTHY
        self._drainable_background_tasks.clear()
        self._shutdown_events.clear()
        self._shutdown_tasks.clear()
        logger.info("ShutdownManager reset to HEALTHY state")
