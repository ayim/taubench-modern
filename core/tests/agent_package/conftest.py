# core/tests/agent_package/conftest.py
from pathlib import Path

import pytest


@pytest.fixture
def test_agent_package_provider():
    def _get_zip_bytes(filename: str) -> bytes:
        return (Path(__file__).parent / "test-data" / "test-agents" / filename).read_bytes()

    return _get_zip_bytes
