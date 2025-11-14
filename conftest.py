import pytest

pytest_plugins = [
    "agent_platform.orchestrator.pytest_fixtures",
    "server.tests.integration.integration_fixtures",
]


@pytest.fixture(scope="session", autouse=True)
def _load_dotenv():
    """Ensure environment variables are loaded."""
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass


@pytest.fixture(autouse=True)
async def _cleanup_shutdown_manager():
    """Reset ShutdownManager after each test to prevent task leaks."""
    # Yield to let the test run first
    yield

    # After test completes, drain any registered workers and reset
    from agent_platform.server.shutdown_manager import ShutdownManager

    manager = ShutdownManager.get_instance()

    # If there are any registered workers, drain them
    if manager._drainable_background_tasks:
        await ShutdownManager.drain_background_workers()

    # Reset to clean state for next test
    manager._reset_for_testing()
