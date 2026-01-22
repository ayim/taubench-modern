"""Tests for semantic data model API endpoints."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from agent_platform.server.api.private_v2 import semantic_data_models_router
from agent_platform.server.auth.handlers import auth_user
from agent_platform.server.error_handlers import add_exception_handlers
from agent_platform.server.storage.option import StorageService

# Get storage fixtures
from server.tests.storage_fixtures import *  # noqa: F403


@pytest.fixture
async def stub_user(storage):
    """Create a stub user for authentication."""
    user, _ = await storage.get_or_create_user("tenant:test:user:sdm-endpoint")
    return user


@pytest.fixture
def fastapi_app_sdm(storage, stub_user) -> FastAPI:
    """FastAPI app configured with semantic data model router."""
    StorageService.reset()
    StorageService.set_for_testing(storage)

    app = FastAPI()
    app.include_router(
        semantic_data_models_router,
        prefix="/api/v2/semantic-data-models",
        tags=["semantic-data-models"],
    )
    app.dependency_overrides[auth_user] = lambda: stub_user
    add_exception_handlers(app)
    return app


@pytest.fixture
def client(fastapi_app_sdm: FastAPI) -> TestClient:
    """Test client for the FastAPI app."""
    return TestClient(fastapi_app_sdm)


@pytest.mark.asyncio
async def test_semantic_data_model_large_integer_serialization(storage, client: TestClient):
    """Test that SDMs with out-of-range integers are properly serialized through database round-trip.

    This test verifies that when an SDM contains integers outside the 64-bit signed integer range,
    they can be stored and retrieved without error. By using JSONResponse instead of ORJSONResponse,
    we avoid the orjson limitation that cannot serialize integers outside the 64-bit range.

    This is a regression test for the bug where large integers in sample_values would cause
    serialization errors with orjson.
    """
    # Large integers outside 64-bit signed integer range (orjson would fail on these)
    large_positive = 2**63  # 9223372036854775808 (just outside int64 max)
    large_negative = -(2**63) - 1  # -9223372036854775809 (just outside int64 min)
    safe_integer = 123  # Within safe range

    # Create SDM with large integers in sample_values directly in storage
    semantic_model = {
        "name": "test_large_integers_serialization",
        "description": "Test model for large integer serialization",
        "tables": [
            {
                "name": "big_numbers",
                "base_table": {
                    "table": "test_table",
                },
                "dimensions": [
                    {
                        "name": "big_value",
                        "expr": "id",
                        "data_type": "int64",
                        "sample_values": [large_positive, large_negative, safe_integer],
                    }
                ],
            }
        ],
    }

    # Create the SDM directly in storage (bypassing API to insert raw large integers)
    semantic_data_model_id = await storage.set_semantic_data_model(
        semantic_data_model_id=None,
        semantic_model=semantic_model,
        data_connection_ids=[],
        file_references=[],
    )
    assert semantic_data_model_id is not None

    # Retrieve the SDM via API GET endpoint - this should NOT raise an error
    # (orjson would fail here with "Integer exceeds 64-bit range")
    response = client.get(f"/api/v2/semantic-data-models/{semantic_data_model_id}")
    assert response.status_code == 200, f"Failed to get SDM: {response.status_code} {response.text}"

    retrieved_model = response.json()
    assert retrieved_model is not None

    # Verify the sample_values are properly serialized - integers should be preserved as-is
    sample_values = retrieved_model["tables"][0]["dimensions"][0]["sample_values"]

    # Large integers should be preserved (standard json library handles arbitrary precision)
    assert sample_values[0] == large_positive, f"Expected large positive int {large_positive}, got {sample_values[0]!r}"
    assert sample_values[1] == large_negative, f"Expected large negative int {large_negative}, got {sample_values[1]!r}"
    assert sample_values[2] == safe_integer, f"Expected safe integer {safe_integer}, got {sample_values[2]!r}"
