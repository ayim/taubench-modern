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
