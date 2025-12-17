"""Unit tests for data frame slicing with limit=-1 (regression test for negative indexing bug)."""

import json
import typing

import pytest

if typing.TYPE_CHECKING:
    from tests.data_frames.fixtures import StorageStub

    from agent_platform.server.data_frames.data_frames_kernel import DataFramesKernel


@pytest.mark.asyncio
async def test_data_frame_slice_with_limit_minus_one(
    storage_stub: "StorageStub",
    data_frames_kernel: "DataFramesKernel",
):
    """Test that limit=-1 fetches all rows from offset onwards (regression test for negative indexing bug).

    This tests the fix in _convert_ibis_slice_to_format that handles limit=-1 specially
    to avoid the negative indexing bug where result[offset : offset + limit] with limit=-1
    would incorrectly slice the data.
    """
    tid = storage_stub.thread.tid

    # Create an in-memory data frame with 5 rows
    await storage_stub.create_in_memory_data_frame(
        name="test_data",
        contents={
            "name": ["Alice", "Bob", "Carol", "Dave", "Eve"],
            "age": [20, 25, 30, 35, 40],
            "city": ["Berlin", "Paris", "London", "Madrid", "Rome"],
        },
    )

    # Get the data frame and resolve it
    data_frames = await storage_stub.list_data_frames(tid)
    assert len(data_frames) == 1
    resolved = await data_frames_kernel.resolve_data_frame(data_frames[0])

    # Test 1: limit=-1 without offset (should return all rows)
    result = await resolved.slice(offset=0, limit=-1, output_format="json")
    loaded = json.loads(typing.cast(bytes, result))
    assert len(loaded) == 5, "limit=-1 with offset=0 should return all 5 rows"
    assert loaded[0]["name"] == "Alice"
    assert loaded[-1]["name"] == "Eve"

    # Test 2: limit=-1 with offset=2 (should return rows from index 2 onwards)
    result = await resolved.slice(offset=2, limit=-1, output_format="json")
    loaded = json.loads(typing.cast(bytes, result))
    assert len(loaded) == 3, "limit=-1 with offset=2 should return 3 rows (from Carol onwards)"
    assert loaded == [
        {"name": "Carol", "age": 30, "city": "London"},
        {"name": "Dave", "age": 35, "city": "Madrid"},
        {"name": "Eve", "age": 40, "city": "Rome"},
    ]

    # Test 3: limit=-1 with offset=4 (should return 1 row)
    result = await resolved.slice(offset=4, limit=-1, output_format="json")
    loaded = json.loads(typing.cast(bytes, result))
    assert len(loaded) == 1, "limit=-1 with offset=4 should return 1 row"
    assert loaded == [{"name": "Eve", "age": 40, "city": "Rome"}]

    # Test 4: limit=None with offset (should behave similarly to limit=-1)
    result = await resolved.slice(offset=2, limit=None, output_format="json")
    loaded = json.loads(typing.cast(bytes, result))
    assert len(loaded) == 3, "limit=None with offset=2 should also return 3 rows"
    assert loaded[0]["name"] == "Carol"


@pytest.mark.asyncio
async def test_data_frame_slice_with_normal_limit(
    storage_stub: "StorageStub",
    data_frames_kernel: "DataFramesKernel",
):
    """Test that normal limit values still work correctly (not affected by the bug fix)."""
    tid = storage_stub.thread.tid

    # Create an in-memory data frame with 5 rows
    await storage_stub.create_in_memory_data_frame(
        name="test_data",
        contents={
            "name": ["Alice", "Bob", "Carol", "Dave", "Eve"],
            "age": [20, 25, 30, 35, 40],
            "city": ["Berlin", "Paris", "London", "Madrid", "Rome"],
        },
    )

    # Get the data frame and resolve it
    data_frames = await storage_stub.list_data_frames(tid)
    resolved = await data_frames_kernel.resolve_data_frame(data_frames[0])

    # Test normal limit=2 with offset=1
    result = await resolved.slice(offset=1, limit=2, output_format="json")
    loaded = json.loads(typing.cast(bytes, result))
    assert len(loaded) == 2, "limit=2 with offset=1 should return 2 rows"
    assert loaded == [
        {"name": "Bob", "age": 25, "city": "Paris"},
        {"name": "Carol", "age": 30, "city": "London"},
    ]

    # Test limit=1 with offset=0
    result = await resolved.slice(offset=0, limit=1, output_format="json")
    loaded = json.loads(typing.cast(bytes, result))
    assert len(loaded) == 1, "limit=1 with offset=0 should return 1 row"
    assert loaded == [{"name": "Alice", "age": 20, "city": "Berlin"}]


@pytest.mark.asyncio
async def test_data_frame_slice_with_limit_minus_one_and_column_selection(
    storage_stub: "StorageStub",
    data_frames_kernel: "DataFramesKernel",
):
    """Test that limit=-1 works correctly with column selection."""
    tid = storage_stub.thread.tid

    await storage_stub.create_in_memory_data_frame(
        name="test_data",
        contents={
            "name": ["Alice", "Bob", "Carol"],
            "age": [20, 25, 30],
            "city": ["Berlin", "Paris", "London"],
        },
    )

    data_frames = await storage_stub.list_data_frames(tid)
    resolved = await data_frames_kernel.resolve_data_frame(data_frames[0])

    # Test limit=-1 with column selection
    result = await resolved.slice(offset=1, limit=-1, output_format="json", column_names=["name", "city"])
    loaded = json.loads(typing.cast(bytes, result))
    assert len(loaded) == 2, "limit=-1 with offset=1 and column selection should return 2 rows"
    assert loaded == [
        {"name": "Bob", "city": "Paris"},
        {"name": "Carol", "city": "London"},
    ]


@pytest.mark.asyncio
async def test_data_frame_slice_with_limit_minus_one_and_order_by(
    storage_stub: "StorageStub",
    data_frames_kernel: "DataFramesKernel",
):
    """Test that limit=-1 works correctly with order_by."""
    tid = storage_stub.thread.tid

    await storage_stub.create_in_memory_data_frame(
        name="test_data",
        contents={
            "name": ["Alice", "Bob", "Carol"],
            "age": [20, 25, 30],
            "city": ["Berlin", "Paris", "London"],
        },
    )

    data_frames = await storage_stub.list_data_frames(tid)
    resolved = await data_frames_kernel.resolve_data_frame(data_frames[0])

    # Test limit=-1 with order_by descending
    result = await resolved.slice(offset=0, limit=-1, output_format="json", order_by="-age")
    loaded = json.loads(typing.cast(bytes, result))
    assert len(loaded) == 3, "limit=-1 with order_by should return all rows"
    # Results should be ordered by age descending
    assert loaded[0]["name"] == "Carol"  # age=30
    assert loaded[1]["name"] == "Bob"  # age=25
    assert loaded[2]["name"] == "Alice"  # age=20
