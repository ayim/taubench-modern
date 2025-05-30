import pytest


@pytest.fixture(scope="session", autouse=True)
def _load_dotenv():
    """Load the .env file."""
    from dotenv import load_dotenv

    load_dotenv()


@pytest.fixture(autouse=True)
def _clear_http_proxy_env(monkeypatch):
    """Remove HTTP proxy environment variables for the duration of the tests."""
    proxy_vars = ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]
    for var in proxy_vars:
        monkeypatch.delenv(var, raising=False)
