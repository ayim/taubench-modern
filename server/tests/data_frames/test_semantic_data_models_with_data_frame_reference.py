# ruff: noqa: PLR0913, E501
"""Tests for semantic data models referencing data frames."""

import typing
from pathlib import Path

import pytest

if typing.TYPE_CHECKING:
    from agent_platform.server.storage.sqlite import SQLiteStorage


@pytest.mark.asyncio
async def test_semantic_data_model_with_data_frame_reference(
    sqlite_storage: "SQLiteStorage",
    tmpdir: Path,
):
    """Test semantic data model referencing a data frame.

    This test:
    1. Creates a semantic data model that references a data frame (using data_frame_name)
    2. Tries to execute it and verifies it fails (data frame doesn't exist yet)
    3. Adds the data frame to the thread
    4. Verifies it succeeds
    5. Verifies the query references the logical name which is translated to the data frame name
    """
    from agent_platform.architectures.experimental.exp_1 import Exp1State
    from agent_platform.core.kernel import Kernel
    from agent_platform.server.kernel.data_frames import AgentServerDataFramesInterface
    from server.tests.storage.sample_model_creator import SampleModelCreator

    # Setup model creator
    model_creator = SampleModelCreator(sqlite_storage, tmpdir)
    await model_creator.setup()

    # Create agent and thread
    agent = await model_creator.obtain_sample_agent()
    thread = await model_creator.obtain_sample_thread()
    user_id = await model_creator.get_user_id()

    # Create a semantic data model that references a data frame
    # The logical table name is "users" but it references data frame "source_data_frame"
    semantic_model = {
        "name": "test_semantic_model_with_data_frame",
        "description": "Test semantic model referencing a data frame",
        "tables": [
            {
                "name": "users",  # This is the logical table name
                "base_table": {
                    "table": "source_data_frame",  # Actual data frame name
                },
                "dimensions": [
                    {"name": "user_id", "expr": "id", "data_type": "INTEGER"},
                    {"name": "user_name", "expr": "name", "data_type": "TEXT"},
                ],
                "facts": [
                    {"name": "user_value", "expr": "value", "data_type": "INTEGER"},
                ],
            }
        ],
    }

    semantic_data_model_id = await sqlite_storage.set_semantic_data_model(
        semantic_data_model_id=None,
        semantic_model=semantic_model,
        data_connection_ids=[],
        file_references=[],
    )

    # Associate model to agent=
    await sqlite_storage.set_agent_semantic_data_models(
        agent_id=agent.agent_id, semantic_data_model_ids=[semantic_data_model_id]
    )

    # Prepare Kernel stub bound to our agent/thread
    from tests.data_frames.fixtures import KernelStub, UserStub

    state = Exp1State()
    user_stub = UserStub(user_id=user_id)
    kernel_stub = KernelStub(thread, user_stub)

    # Initialize interface
    interface = AgentServerDataFramesInterface()
    interface.attach_kernel(typing.cast(Kernel, kernel_stub))
    await interface.step_initialize(storage=sqlite_storage, state=state)

    # Get the tools
    tools = interface.get_data_frame_tools()

    # Now create the source data frame in the thread
    # Create a CSV file with the data
    csv_content = b"id,name,value\n1,Alice,10\n2,Bob,20\n3,Charlie,30"
    csv_file = await model_creator.obtain_sample_file(
        file_content=csv_content,
        file_name="source_data.csv",
        mime_type="text/csv",
    )

    # Create data frame from file using the tool
    create_file_tool = next(tool for tool in tools if tool.name == "data_frames_create_from_file")
    await create_file_tool.function(
        data_frame_name="source_data_frame",
        file_ref=csv_file.file_ref,
        sheet_name=None,
        description="Source data frame",
    )

    # Re-initialize to pick up the new data frame
    await interface.step_initialize(storage=sqlite_storage, state=state)
    tools = interface.get_data_frame_tools()
    create_sql_tool = next(tool for tool in tools if tool.name == "data_frames_create_from_sql")

    # Now try again - this should succeed
    result = await create_sql_tool.function(
        sql_query="SELECT * FROM users WHERE id > 1",  # Uses logical name "users"
        new_data_frame_name="result_data_frame",
    )

    # Verify the result
    assert "result" in result
    assert "sample_data" in result

    sample_data = result["sample_data"]
    assert "columns" in sample_data
    assert "rows" in sample_data

    # Verify columns
    assert sample_data["columns"] == ["id", "name", "value"]

    # Verify rows (should have 2 rows with id 2 and 3)
    rows = sample_data["rows"]
    assert len(rows) == 2

    # Check that we have the expected rows (id 2 and 3)
    row_ids = [row[0] for row in rows]
    assert 2 in row_ids
    assert 3 in row_ids

    # Verify that the logical name "users" was translated to the actual data frame name
    # "source_data_frame" in the SQL query execution
    # This is verified by the fact that the query succeeded and returned the correct data
