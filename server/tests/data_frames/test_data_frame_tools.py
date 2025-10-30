import typing
from collections.abc import Sequence
from pathlib import Path

import pytest

from agent_platform.core.kernel_interfaces.data_frames import DataFrameArchState

if typing.TYPE_CHECKING:
    from agent_platform.core.tools.tool_definition import ToolDefinition


class _DefaultDataFrameArchState(DataFrameArchState):
    def __init__(self):
        self.data_frames_tools_state = ""
        self.empty_file_cache_key_to_matching_info = {}


def find_tool(name: str, tools: Sequence["ToolDefinition"]) -> "ToolDefinition":
    try:
        return next(tool for tool in tools if tool.name == name)
    except Exception as e:
        raise RuntimeError(
            f"{name} tool not found. Available tools: {', '.join([tool.name for tool in tools])}"
        ) from e


@pytest.mark.asyncio
async def test_data_frames_interface(file_regression):
    import json

    from tests.data_frames.fixtures import KernelStub, StorageStub

    from agent_platform.core.data_frames.semantic_data_model_validation import References
    from agent_platform.core.kernel import Kernel
    from agent_platform.server.data_frames.semantic_data_model_collector import (
        SemanticDataModelAndReferences,
    )
    from agent_platform.server.kernel.data_frames import (
        AgentServerDataFramesInterface,
    )
    from agent_platform.server.storage.base import BaseStorage

    storage_stub = StorageStub()
    kernel_stub = KernelStub(storage_stub.thread, storage_stub.thread.user)

    await storage_stub.create_in_memory_data_frame(
        name="test_data_frame",
        contents={"col1": [1, 2, 3], "col2": [4, 5, 6]},
    )

    interface = AgentServerDataFramesInterface()
    interface.attach_kernel(typing.cast(Kernel, kernel_stub))

    assert interface.thread_has_data_frames is False

    assert interface.data_frames_system_prompt == ""

    state = _DefaultDataFrameArchState()
    await interface.step_initialize(storage=typing.cast(BaseStorage, storage_stub), state=state)

    assert interface.thread_has_data_frames is True

    file_regression.check(interface.data_frames_system_prompt)

    tools = interface.get_data_frame_tools()

    data_frame_slice_tool = find_tool("data_frames_slice", tools)

    collected_data = await data_frame_slice_tool.function(
        data_frame_name="test_data_frame",
        column_names=["col1", "col2"],
    )
    assert collected_data == {"columns": ["col1", "col2"], "rows": [[1, 4], [2, 5], [3, 6]]}
    json.dumps(collected_data)  # just check it works

    semantic_data_models: list[BaseStorage.SemanticDataModelInfo] = [
        {
            "semantic_data_model": {
                "name": "test_semantic_model",
                "description": "A test semantic model for data frame testing",
                "tables": [
                    {
                        "name": "test_table",
                        "base_table": {
                            "table": "test_data_frame",
                            "data_connection_id": "data-connection-id1",
                            "database": "test_db",
                            "schema": "public",
                        },
                        "description": "Test table for semantic model",
                        "dimensions": [
                            {
                                "name": "col1",
                                "expr": "col1",
                                "data_type": "INTEGER",
                                "description": "First column dimension",
                            }
                        ],
                        "facts": [
                            {
                                "name": "col2",
                                "expr": "col2",
                                "data_type": "INTEGER",
                                "description": "Second column fact",
                            }
                        ],
                    }
                ],
                "relationships": [],
            },
            "semantic_data_model_id": "test_semantic_model_id",
            "agent_ids": {storage_stub.thread.agent_id},
            "thread_ids": {storage_stub.thread.tid},
            "updated_at": "2024-01-01T00:00:00.000Z",
        }
    ]

    assert hasattr(interface, "_semantic_data_models")
    interface._semantic_data_models = [
        SemanticDataModelAndReferences(
            semantic_data_model_info=semantic_data_model_info,
            references=References(
                data_connection_ids=set(),
                file_references=set(),
                data_connection_id_to_logical_table_names={},
                file_reference_to_logical_table_names={},
                logical_table_name_to_connection_info={},
                errors=[],
                tables_with_unresolved_file_references=set(),
                semantic_data_model_with_errors=None,
            ),
        )
        for semantic_data_model_info in semantic_data_models
    ]
    file_regression.check(
        interface.data_frames_system_prompt,
        basename="data_frames_system_prompt_with_semantic_data_models",
    )
    file_regression.check(
        interface.data_frames_system_prompt_no_tools,
        basename="data_frames_system_prompt_with_semantic_data_models_no_tools",
    )


@pytest.mark.asyncio
async def test_data_frames_interface_state(file_regression):
    from tests.data_frames.fixtures import KernelStub, StorageStub

    from agent_platform.core.kernel import Kernel
    from agent_platform.server.kernel.data_frames import (
        AgentServerDataFramesInterface,
    )
    from agent_platform.server.storage.base import BaseStorage

    storage_stub = StorageStub()
    kernel_stub = KernelStub(storage_stub.thread, storage_stub.thread.user)

    state = _DefaultDataFrameArchState()

    interface = AgentServerDataFramesInterface()
    interface.attach_kernel(typing.cast(Kernel, kernel_stub))
    await interface.step_initialize(storage=typing.cast(BaseStorage, storage_stub), state=state)

    assert interface.thread_has_data_frames is False
    tools = interface.get_data_frame_tools()
    assert {t.name for t in tools} == {"data_frames_create_from_file"}
    assert state.data_frames_tools_state == ""

    await storage_stub.create_in_memory_data_frame(
        name="test_data_frame",
        contents={"col1": [1, 2, 3], "col2": [4, 5, 6]},
    )

    await interface.step_initialize(storage=typing.cast(BaseStorage, storage_stub), state=state)
    assert state.data_frames_tools_state == "enabled"
    all_tools = {
        "data_frames_create_from_file",
        "data_frames_slice",
        "data_frames_delete",
        "data_frames_create_from_sql",
    }
    tools = interface.get_data_frame_tools()
    assert {t.name for t in tools} == all_tools

    storage_stub.data_frames.clear()
    await interface.step_initialize(storage=typing.cast(BaseStorage, storage_stub), state=state)
    assert state.data_frames_tools_state == "enabled"
    tools = interface.get_data_frame_tools()
    assert {t.name for t in tools} == all_tools


def _upload_file(storage_stub, tmp_path: Path):
    import datetime
    from uuid import uuid4

    from agent_platform.core.files.files import UploadedFile

    f = tmp_path / "test_data_frame.csv"
    f.write_text("col1,col2\n1,4\n2,5\n3,6")

    uploaded_file = UploadedFile(
        file_id=str(uuid4()),
        file_ref=f.name,
        file_path=f.as_uri(),
        file_hash="1234567890",
        file_size_raw=100,
        mime_type="text/csv",
        created_at=datetime.datetime.now(datetime.UTC),
        embedded=False,
        thread_id=storage_stub.thread.tid,
        user_id=storage_stub.thread.user.user_id,
        agent_id=storage_stub.thread.agent_id,
        work_item_id=None,
        file_url=None,
        file_path_expiration=None,
    )
    storage_stub.add_file(uploaded_file)


@pytest.mark.asyncio
async def test_data_frames_create_from_file(tmp_path):
    import json

    from tests.data_frames.fixtures import KernelStub, StorageStub

    from agent_platform.core.kernel import Kernel
    from agent_platform.server.kernel.data_frames import (
        AgentServerDataFramesInterface,
    )
    from agent_platform.server.storage.base import BaseStorage

    storage_stub = StorageStub()
    kernel_stub = KernelStub(storage_stub.thread, storage_stub.thread.user)

    _upload_file(storage_stub, tmp_path)

    interface = AgentServerDataFramesInterface()
    interface.attach_kernel(typing.cast(Kernel, kernel_stub))

    state = _DefaultDataFrameArchState()
    await interface.step_initialize(storage=typing.cast(BaseStorage, storage_stub), state=state)

    tools = interface.get_data_frame_tools()

    data_frame_create_from_file_tool = find_tool("data_frames_create_from_file", tools)

    result = await data_frame_create_from_file_tool.function(
        data_frame_name="test_data_frame",
        file_ref="test_data_frame.csv",
    )
    json.dumps(result)  # just check it works

    # After this step, other tools should also be available.
    state = _DefaultDataFrameArchState()
    await interface.step_initialize(storage=typing.cast(BaseStorage, storage_stub), state=state)
    tools = interface.get_data_frame_tools()
    data_frame_slice_tool = find_tool("data_frames_slice", tools)

    collected_data = await data_frame_slice_tool.function(
        data_frame_name="test_data_frame",
        column_names=["col1", "col2"],
    )
    assert collected_data == {"columns": ["col1", "col2"], "rows": [[1, 4], [2, 5], [3, 6]]}
    json.dumps(collected_data)  # just check it works


@pytest.mark.asyncio
async def test_data_frame_tools():
    from tests.data_frames.fixtures import StorageStub

    from agent_platform.server.auth.handlers import AuthedUser
    from agent_platform.server.kernel.data_frames import _DataFrameTools
    from agent_platform.server.storage.base import BaseStorage

    storage_stub = StorageStub()

    await storage_stub.create_in_memory_data_frame(
        name="test_data_frame",
        contents={"col1": [1, 2, 3], "col2": [4, 5, 6]},
    )

    data_frames = await storage_stub.list_data_frames(storage_stub.thread.tid)
    assert len(data_frames) == 1
    data_frame = data_frames[0]

    tools = _DataFrameTools(
        user=typing.cast(AuthedUser, storage_stub.thread.user),
        tid=storage_stub.thread.tid,
        name_to_data_frame={d.name: d for d in data_frames},
        storage=typing.cast(BaseStorage, storage_stub),
    )

    rows = await tools.data_frame_slice(data_frame.name, limit=10)

    assert rows == {"columns": ["col1", "col2"], "rows": [[1, 4], [2, 5], [3, 6]]}

    result = await tools.create_data_frame_from_sql(
        sql_query="SELECT col1 FROM test_data_frame WHERE col1 > 1",
        new_data_frame_name="test data frame 2",
    )
    assert result == {
        "result": "Data frame test_data_frame_2 created from SQL query",
        "sample_data": {"columns": ["col1"], "rows": [[2], [3]]},
    }

    rows = await tools.data_frame_slice(
        "test_data_frame_2",
        limit=10,
        order_by="-col1",
    )
    assert rows == {"columns": ["col1"], "rows": [[3], [2]]}

    assert await tools.delete_data_frame("test_data_frame_2") == {
        "result": "Data frame 'test_data_frame_2' deleted"
    }

    assert await tools.delete_data_frame("test_data_frame_2") == {
        "error_code": "data_frame_not_found",
        "error": "Data frame 'test_data_frame_2' not found",
    }


@pytest.mark.asyncio
async def test_semantic_data_models_engine_in_summary(
    sqlite_storage, resources_dir, tmp_path, file_regression
):
    db_file = resources_dir / "data_frames" / "combined_data.sqlite"
    assert db_file.exists()

    # Imports inside method per project standard
    from agent_platform.core.data_connections.data_connections import DataConnection
    from agent_platform.core.kernel import Kernel
    from agent_platform.core.payloads.data_connection import (
        SQLiteDataConnectionConfiguration,
    )
    from agent_platform.server.kernel.data_frames import (
        AgentServerDataFramesInterface,
    )
    from server.tests.storage.sample_model_creator import SampleModelCreator

    # Create sample agent/thread and seed storage
    model_creator = SampleModelCreator(sqlite_storage, tmp_path)
    await model_creator.setup()
    agent = await model_creator.obtain_sample_agent()
    thread = await model_creator.obtain_sample_thread()

    # Create a data connection pointing to the SQLite database file
    dc = DataConnection(
        id="sqlite-test-conn",
        name="sqlite-test-conn",
        description="SQLite connection for tests",
        engine="sqlite",
        configuration=SQLiteDataConnectionConfiguration(db_file=str(db_file)),
        external_id=None,
        created_at=None,
        updated_at=None,
    )
    await sqlite_storage.set_data_connection(dc)

    # Minimal semantic data model that references a table in the SQLite DB via the data connection
    semantic_model = {
        "name": "combined_ai_semantic_model",
        "description": "Semantic model over combined_data.sqlite",
        "tables": [
            {
                "name": "artificial_intelligence_number_training_datapoints",
                "base_table": {
                    "database": "",
                    "schema": "",
                    "table": "artificial_intelligence_number_training_datapoints",
                    "data_connection_id": dc.id,
                },
            }
        ],
    }

    semantic_data_model_id = await sqlite_storage.set_semantic_data_model(
        semantic_data_model_id=None,
        semantic_model=semantic_model,
        data_connection_ids=[dc.id],
        file_references=[],
    )

    # Associate model to agent and thread so the collector will find it
    await sqlite_storage.set_agent_semantic_data_models(
        agent_id=agent.agent_id, semantic_data_model_ids=[semantic_data_model_id]
    )
    await sqlite_storage.set_thread_semantic_data_models(
        thread_id=thread.thread_id, semantic_data_model_ids=[semantic_data_model_id]
    )

    # Prepare Kernel stub bound to our agent/thread
    class _KernelStub:
        def __init__(self, thread, user_id: str):
            self.thread = thread

            # Minimal user object with user_id
            class _User:
                def __init__(self, user_id: str):
                    self.user_id = user_id

            self.user = _User(user_id)
            # Provide minimal agent attribute expected by interface
            self.agent = type("_Agent", (), {"extra": {}})()

    kernel_stub = _KernelStub(thread, await model_creator.get_user_id())

    # Initialize interface and verify engine in semantic data models summary
    interface = AgentServerDataFramesInterface()
    interface.attach_kernel(typing.cast(Kernel, kernel_stub))

    state = _DefaultDataFrameArchState()
    await interface.step_initialize(storage=sqlite_storage, state=state)

    # Create a data frame via SQL referencing the semantic model logical table
    tools = interface.get_data_frame_tools()
    create_sql_tool = find_tool("data_frames_create_from_sql", tools)
    result = await create_sql_tool.function(
        sql_query=("SELECT * FROM artificial_intelligence_number_training_datapoints LIMIT 1"),
        new_data_frame_name="ai_data_from_sql",
    )
    assert "result" in result

    # The created data frame should reflect the sqlite dialect in the summary
    df_summary = interface.data_frames_system_prompt
    # The sample has some non-ascii characters, remove so that we don't have issues in the compare.
    df_summary = df_summary.encode("ascii", errors="replace").decode("ascii")
    assert "SQL dialect: sqlite" in df_summary
    file_regression.check(df_summary, basename="data_frames_system_prompt_with_sqlite_dialect")
