# ruff: noqa: PLR0912, PLR0913, PLR0915, C901, E501
import typing
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
async def test_data_frames_assembly_info(
    sqlite_storage: "SQLiteStorage",
    tmpdir: Path,
    client: TestClient,
    test_user,
    fastapi_app,
    file_regression,
):
    """Test the data frames assembly info API endpoint."""

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

    result = await create_sql_tool.function(
        sql_query="SELECT * FROM file_data",
        new_data_frame_name="test_data_frame",
    )
    assert "result" in result

    # Create a new data frame based on the existing data frame with a single column
    result = await create_sql_tool.function(
        sql_query="SELECT Category FROM test_data_frame",
        new_data_frame_name="test_data_frame_single_column",
    )
    assert "result" in result

    # Create a new data frame based on the existing data frame with a single column
    result = await create_sql_tool.function(
        sql_query="SELECT * FROM test_data_frame_single_column",
        new_data_frame_name="another_data_frame",
        new_data_frame_description="Another data frame (description)",
    )
    assert "result" in result

    check_data_frame_names = [
        "another_data_frame",
        "test_data_frame_single_column",
        "test_data_frame",
    ]

    # Call the API endpoint to get assembly info for both data frames
    response = client.post(
        f"/api/v2/threads/{thread.thread_id}/data-frames/assembly-info",
        json={"data_frame_names": check_data_frame_names},
    )

    assert response.status_code == 200
    assembly_info = response.json()
    # At this point, just check that it returned something (not empty string)
    for data_frame_name, info in assembly_info.items():
        file_regression.check(info, basename=f"test_data_frames_assembly_info_{data_frame_name}")
