# ruff: noqa: PLR0912, PLR0913, PLR0915, C901, E501
import time
import typing
from datetime import datetime
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

if typing.TYPE_CHECKING:
    from agent_platform.server.storage.sqlite import SQLiteStorage


@pytest.fixture
async def test_user(sqlite_storage: "SQLiteStorage"):
    """Create a test user for API calls."""

    user, _ = await sqlite_storage.get_or_create_user(sub="tenant:testing:user:system")
    return user


@pytest.fixture
async def fastapi_app(sqlite_storage: "SQLiteStorage", test_user) -> FastAPI:
    """Create FastAPI test app with router and storage dependency."""
    from agent_platform.server.api.private_v2 import threads_data_frames
    from agent_platform.server.auth.handlers import auth_user
    from agent_platform.server.storage.option import StorageService

    StorageService.reset()
    StorageService.set_for_testing(sqlite_storage)

    app = FastAPI()
    app.include_router(threads_data_frames.router, prefix="/api/v2/threads")

    async def override_auth_user():
        return test_user

    app.dependency_overrides[auth_user] = override_auth_user

    return app


@pytest.fixture
def client(fastapi_app: FastAPI) -> TestClient:
    """Create test client."""
    return TestClient(fastapi_app)


@pytest.mark.asyncio
async def test_save_data_frame_as_validated_query(
    sqlite_storage: "SQLiteStorage",
    tmpdir: Path,
    client: TestClient,
    test_user,
    fastapi_app,
):
    """Test saving a data frame as a validated query in a semantic data model."""

    from agent_platform.architectures.experimental.exp_1 import Exp1State
    from server.tests.storage.sample_model_creator import SampleModelCreator

    # Setup model creator
    model_creator = SampleModelCreator(sqlite_storage, tmpdir)
    await model_creator.setup()

    # Create agent and thread
    agent = await model_creator.obtain_sample_agent()
    thread = await model_creator.obtain_sample_thread()

    # Create a CSV file
    csv_content = b"Category,Value\nA,100\nB,200\nC,300"
    csv_file = await model_creator.obtain_sample_file(
        file_content=csv_content,
        file_name="test_data.csv",
        mime_type="text/csv",
    )

    # Create a semantic data model with file reference
    semantic_model = {
        "name": "test_semantic_model",
        "description": "Test semantic model with file reference",
        "tables": [
            {
                "name": "file_data",
                "base_table": {
                    "table": "data_frame_file",
                    "file_reference": {
                        "thread_id": thread.thread_id,
                        "file_ref": csv_file.file_ref,
                        "sheet_name": None,
                    },
                },
                "dimensions": [
                    {"name": "category", "expr": "Category", "data_type": "TEXT"},
                ],
                "facts": [
                    {"name": "value", "expr": "Value", "data_type": "INTEGER"},
                ],
            }
        ],
    }

    semantic_data_model_id = await sqlite_storage.set_semantic_data_model(
        semantic_data_model_id=None,
        semantic_model=semantic_model,
        data_connection_ids=[],
        file_references=[(thread.thread_id, csv_file.file_ref)],
    )

    # Associate model to agent and thread
    await sqlite_storage.set_agent_semantic_data_models(
        agent_id=agent.agent_id, semantic_data_model_ids=[semantic_data_model_id]
    )
    await sqlite_storage.set_thread_semantic_data_models(
        thread_id=thread.thread_id, semantic_data_model_ids=[semantic_data_model_id]
    )

    # Create a data frame from the semantic data model using SQL
    from agent_platform.core.kernel import Kernel
    from agent_platform.server.kernel.data_frames import AgentServerDataFramesInterface

    # Prepare Kernel stub bound to our agent/thread
    class _KernelStub:
        def __init__(self, thread, user_id: str, state):
            self.thread = thread

            class _User:
                def __init__(self, user_id: str):
                    self.user_id = user_id

            self.user = _User(user_id)
            self.agent = type("_Agent", (), {"extra": {}})()
            self.thread_state = state

    state = Exp1State()
    kernel_stub = _KernelStub(thread, await model_creator.get_user_id(), state)

    # Initialize interface and create data frame via SQL
    interface = AgentServerDataFramesInterface()
    interface.attach_kernel(typing.cast(Kernel, kernel_stub))

    await interface.step_initialize(storage=sqlite_storage, state=state)

    # Create a data frame via SQL referencing the semantic model logical table
    tools = interface.get_data_frame_tools()
    create_sql_tool = next(tool for tool in tools if tool.name == "data_frames_create_from_sql")

    data_frame_name = "test_validated_query_df"
    data_frame_description = "Test data frame description for validated query"

    result = await create_sql_tool.function(
        sql_query="SELECT * FROM file_data",
        new_data_frame_name=data_frame_name,
        new_data_frame_description=data_frame_description,
    )
    assert "result" in result

    # Verify the semantic data model doesn't have verified_queries yet
    retrieved_model_before = await sqlite_storage.get_semantic_data_model(semantic_data_model_id)
    assert (
        "verified_queries" not in retrieved_model_before
        or retrieved_model_before.get("verified_queries") is None
    )

    # Step 1: Get the data frame as a validated query
    get_response = client.post(
        f"/api/v2/threads/{thread.thread_id}/data-frames/as-validated-query",
        json={"data_frame_name": data_frame_name},
    )

    assert get_response.status_code == 200
    validated_query = get_response.json()
    # The verified query name is converted to human-readable format (spaces + title case)
    from agent_platform.core.data_frames.data_frame_utils import (
        data_frame_name_to_verified_query_name,
    )

    expected_verified_query_name = data_frame_name_to_verified_query_name(data_frame_name)
    assert validated_query["name"] == expected_verified_query_name
    assert validated_query["nlq"] == data_frame_description
    assert validated_query["verified_by"] == test_user.user_id
    assert "verified_at" in validated_query

    def fix_sql_query(sql_query: str) -> str:
        return sql_query.replace("\n", " ").strip().replace("  ", " ").replace("  ", " ")

    assert fix_sql_query(validated_query["sql"]) == "SELECT * FROM file_data"

    # Step 2: Save the validated query
    response = client.post(
        f"/api/v2/threads/{thread.thread_id}/data-frames/save-as-validated-query",
        json={
            "verified_query": validated_query,
            "semantic_data_model_id": semantic_data_model_id,
        },
    )

    assert response.status_code == 200
    response_data = response.json()
    assert "message" in response_data
    assert "Successfully saved" in response_data["message"]
    assert validated_query["name"] in response_data["message"]

    # Verify the semantic data model was updated with the verified query
    retrieved_model_after = await sqlite_storage.get_semantic_data_model(semantic_data_model_id)
    assert "verified_queries" in retrieved_model_after
    assert retrieved_model_after["verified_queries"] is not None
    assert len(retrieved_model_after["verified_queries"]) == 1

    verified_query = retrieved_model_after["verified_queries"][0]
    assert verified_query["name"] == expected_verified_query_name
    assert verified_query["nlq"] == data_frame_description
    assert verified_query["verified_by"] == test_user.user_id

    assert fix_sql_query(verified_query["sql"]) == "SELECT * FROM file_data"
    assert "verified_at" in verified_query
    # Verify verified_at is a valid ISO format string
    datetime.fromisoformat(verified_query["verified_at"])

    # Test updating an existing verified query by calling the endpoint again
    # This should update the verified_at timestamp
    time.sleep(0.02)  # Small delay to ensure different timestamp

    # Step 1: Get the validated query again
    get_response_updated = client.post(
        f"/api/v2/threads/{thread.thread_id}/data-frames/as-validated-query",
        json={"data_frame_name": data_frame_name},
    )
    assert get_response_updated.status_code == 200
    updated_validated_query = get_response_updated.json()

    # Step 2: Save the updated validated query
    response = client.post(
        f"/api/v2/threads/{thread.thread_id}/data-frames/save-as-validated-query",
        json={
            "verified_query": updated_validated_query,
            "semantic_data_model_id": semantic_data_model_id,
        },
    )

    assert response.status_code == 200

    # Verify the semantic data model still has only one verified query (updated)
    retrieved_model_updated = await sqlite_storage.get_semantic_data_model(semantic_data_model_id)
    assert len(retrieved_model_updated["verified_queries"]) == 1

    updated_query = retrieved_model_updated["verified_queries"][0]
    assert updated_query["name"] == expected_verified_query_name
    assert updated_query["nlq"] == data_frame_description
    assert fix_sql_query(updated_query["sql"]) == "SELECT * FROM file_data"
    # Verify verified_at was updated (should be different timestamp)
    assert updated_query["verified_at"] != verified_query["verified_at"]
