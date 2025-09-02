import typing
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

import pytest

from agent_platform.core.kernel_interfaces.data_frames import DataFrameArchState

if typing.TYPE_CHECKING:
    from agent_platform.core.tools.tool_definition import ToolDefinition


class _DefaultDataFrameArchState(DataFrameArchState):
    data_frames_tools_state: Literal["enabled", ""] = ""


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

    from agent_platform.core.kernel import Kernel
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
    import typing

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
        new_data_frame_name="test_data_frame_2",
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
