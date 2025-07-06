import asyncio

import httpx
import pytest
from httpx import AsyncClient

from agent_platform.server.app import create_app
from agent_platform.server.constants import SystemConfig


@pytest.mark.asyncio
async def test_work_items_disabled(monkeypatch):
    """When SystemConfig.enable_workitems is False the endpoints should return 403 and
    the background worker should not start."""

    # ------------------------------------------------------------------
    # 1. Patch the background worker starter so we can detect if it is called
    # ------------------------------------------------------------------
    worker_called = False

    def _fake_start_worker():  # type: ignore[override] - signature match not important
        nonlocal worker_called
        worker_called = True
        # Return dummy objects to satisfy the expected return type if ever called
        return asyncio.create_task(asyncio.sleep(0)), asyncio.Event()

    monkeypatch.setattr(
        "agent_platform.server.lifespan._start_work_items_background_worker", _fake_start_worker
    )

    # ------------------------------------------------------------------
    # 2. Disable the feature flag for the duration of this test
    # ------------------------------------------------------------------
    original_instance = SystemConfig._instances.get(SystemConfig)
    try:
        SystemConfig.set_instance(SystemConfig(enable_workitems=False))

        # ------------------------------------------------------------------
        # 3. Create the app and issue a request to a work-items endpoint
        # ------------------------------------------------------------------
        app = create_app()
        async with AsyncClient(
            transport=httpx.ASGITransport(app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/v2/work-items/")

        # ------------------------------------------------------------------
        # 4. Verify the response shape
        # ------------------------------------------------------------------
        assert response.status_code == 403
        body = response.json()
        assert "error" in body
        assert body["error"]["code"] == "forbidden"
        assert body["error"]["message"] == "Work items feature is disabled"

        # ------------------------------------------------------------------
        # 5. Ensure background worker never started
        # ------------------------------------------------------------------
        assert worker_called is False
    finally:
        # ------------------------------------------------------------------
        # 6. Restore original SystemConfig instance so other tests are unaffected
        # ------------------------------------------------------------------
        if original_instance is not None:
            SystemConfig.set_instance(original_instance)
        else:
            SystemConfig._instances.pop(SystemConfig, None)
