import pytest


@pytest.fixture(scope="session", autouse=True)
def _load_dotenv():
    """Load the .env file."""
    from dotenv import load_dotenv
    load_dotenv()
