# ruff: noqa: PLR0913
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
    # Prepare Kernel stub bound to our agent/thread
    from tests.data_frames.fixtures import KernelStub, UserStub

    from agent_platform.core.kernel import Kernel
    from agent_platform.server.kernel.data_frames import AgentServerDataFramesInterface

    state = Exp1State()
    user_stub = UserStub(user_id=await model_creator.get_user_id())
    kernel_stub = KernelStub(thread, user_stub)

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


@pytest.mark.asyncio
async def test_data_frames_assembly_info_with_database_connection(
    sqlite_storage: "SQLiteStorage",
    tmpdir: Path,
    client: TestClient,
    test_user,
    fastapi_app,
):
    """Test that assembly info shows connection details (hostname/user/database) instead of Data Connection ID."""
    from agent_platform.core.data_connections.data_connections import DataConnection
    from agent_platform.core.data_frames.data_frames import PlatformDataFrame
    from agent_platform.core.payloads.data_connection import PostgresDataConnectionConfiguration
    from agent_platform.server.data_frames.data_frames_assembly_info import AssemblyInfo
    from agent_platform.server.data_frames.data_frames_kernel import DataFramesKernel
    from server.tests.storage.sample_model_creator import SampleModelCreator

    # Setup model creator
    model_creator = SampleModelCreator(sqlite_storage, tmpdir)
    await model_creator.setup()

    # Create agent and thread
    agent = await model_creator.obtain_sample_agent()
    thread = await model_creator.obtain_sample_thread()

    # Create a PostgreSQL data connection with known values
    dc = DataConnection(
        id="test-postgres-conn-123",
        name="Test PostgreSQL Connection",
        description="Test connection for assembly info",
        engine="postgres",
        configuration=PostgresDataConnectionConfiguration(
            host="test-db.example.com",
            port=5432,
            database="test_database",
            user="test_user",
            password="test_password",
        ),
        external_id=None,
        created_at=None,
        updated_at=None,
    )
    await sqlite_storage.set_data_connection(dc)

    # Create a semantic data model with database connection
    semantic_model = {
        "name": "test_db_semantic_model",
        "description": "Test semantic model with database connection",
        "tables": [
            {
                "name": "customers",
                "base_table": {
                    "database": "test_database",
                    "schema": "public",
                    "table": "customers",
                    "data_connection_id": dc.id,
                },
                "dimensions": [
                    {"name": "id", "expr": "id", "data_type": "INTEGER"},
                    {"name": "name", "expr": "name", "data_type": "TEXT"},
                ],
            }
        ],
    }

    semantic_data_model_id = await sqlite_storage.set_semantic_data_model(
        semantic_data_model_id=None,
        semantic_model=semantic_model,
        data_connection_ids=[dc.id],
        file_references=[],
    )

    # Associate model to agent and thread
    await sqlite_storage.set_agent_semantic_data_models(
        agent_id=agent.agent_id, semantic_data_model_ids=[semantic_data_model_id]
    )
    await sqlite_storage.set_thread_semantic_data_models(
        thread_id=thread.thread_id, semantic_data_model_ids=[semantic_data_model_id]
    )

    # Create a data frame directly (without executing SQL) to test assembly info
    # We'll create it with sql_computation type that references the semantic model
    from datetime import UTC, datetime
    from uuid import uuid4

    from agent_platform.core.data_frames.data_frames import DataFrameSource

    user_id = await model_creator.get_user_id()
    data_frame = PlatformDataFrame(
        data_frame_id=str(uuid4()),
        name="customers_data_frame",
        user_id=user_id,
        agent_id=agent.agent_id,
        thread_id=thread.thread_id,
        num_rows=0,  # Not executed, so 0 rows
        num_columns=0,  # Not executed, so 0 columns
        column_headers=[],
        columns={},
        input_id_type="sql_computation",
        created_at=datetime.now(UTC),
        computation="SELECT * FROM customers LIMIT 5",
        computation_input_sources={
            "customers": DataFrameSource(
                source_type="semantic_data_model",
                base_table={
                    "database": "test_database",
                    "schema": "public",
                    "table": "customers",
                    "data_connection_id": dc.id,
                },
            ),
        },
        parquet_contents=None,
        extra_data=PlatformDataFrame.build_extra_data(sql_dialect="postgres"),
        description=None,
        file_id=None,
        file_ref=None,
        sheet_name=None,
    )
    await sqlite_storage.save_data_frame(data_frame)

    # Build dependencies the same way resolve_data_frame would
    # This tests the real dependency building logic
    data_frames_kernel = DataFramesKernel(sqlite_storage, test_user, thread.thread_id)
    name_to_data_frame = await data_frames_kernel._get_name_to_data_frame()

    # This will build dependencies correctly from the data frame's computation_input_sources
    dependencies = await data_frames_kernel._compute_data_frame_graph(data_frame, name_to_data_frame)

    # Now test assembly info generation with real dependencies
    assembly_info = AssemblyInfo()
    assembly_info.set_initial_data_frame(data_frame)
    assembly_info.set_dependencies(dependencies)

    info = await assembly_info.to_markdown(storage=sqlite_storage)

    # Verify that connection details are shown instead of "Data Connection ID"
    assert "Data Connection ID" not in info, "Should not show 'Data Connection ID'"
    assert "Hostname: `test-db.example.com`" in info, "Should show hostname"
    assert "User: `test_user`" in info, "Should show user"
    assert "Database: `test_database`" in info, "Should show database"
    assert "Schema: `public`" in info, "Should show schema"
    assert "Table: `customers`" in info, "Should show table"

    # Verify the semantic data model section shows connection details
    assert "## Semantic Data Model: `customers`" in info
    assert "#### Source: Database" in info
