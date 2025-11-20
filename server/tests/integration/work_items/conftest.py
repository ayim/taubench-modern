from typing import NamedTuple

import pytest


class WorkItemsServerConfig(NamedTuple):
    """Configuration for work items server test environment."""

    storage_type: str  # "sqlite" or "postgres"
    file_management_type: str  # "local" or "cloud"


# ---------------------------------------------------------------------------
# Parameterization Constants
# ---------------------------------------------------------------------------

# Local + storage configurations
all_databases_local = [
    pytest.param(WorkItemsServerConfig("sqlite", "local"), id="sqlite_local"),
    pytest.param(
        WorkItemsServerConfig("postgres", "local"),
        id="postgres_local",
        marks=[pytest.mark.postgresql],
    ),
]

# Cloud + storage configurations
all_databases_cloud = [
    # We don't need to test sqlite in cloud because there is no use case
    pytest.param(
        WorkItemsServerConfig("postgres", "cloud"),
        id="postgres_cloud",
        marks=[pytest.mark.postgresql, pytest.mark.cloud],
    ),
]

all_databases_matrix = all_databases_local + all_databases_cloud


@pytest.fixture(scope="session", autouse=True)
def fast_worker_settings_env():
    """Ensure the background worker runs frequently during the test session."""
    import os

    # Trigger the worker every second so we don't wait 30 s (default)
    os.environ.setdefault("WORKITEMS_WORKER_INTERVAL", "1")
    # Keep the timeout short-ish (60 s instead of 4 hours)
    os.environ.setdefault("SEMA4AI_AGENT_SERVER_WORK_ITEM_TIMEOUT_IN_SECONDS", "60")
