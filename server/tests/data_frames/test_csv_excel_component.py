"""Tests for CSV/Excel data frame limit handling and memory safety fixes.

These tests verify that:
1. Default limit handling when limit=None (prevents loading all rows)
2. Maximum limit cap at MAX_SLICE_LIMIT rows (prevents memory exhaustion)
"""

import json
import typing

import pytest

if typing.TYPE_CHECKING:
    from tests.data_frames.fixtures import StorageStub

    from agent_platform.server.data_frames.data_frames_kernel import DataFramesKernel
    from agent_platform.server.data_frames.data_node import DataNodeResult


async def _create_simple_data_frame(
    storage_stub: "StorageStub",
    num_rows: int,
    name: str = "test_data",
) -> None:
    """Helper to create a simple in-memory data frame with id and value columns.

    Args:
        storage_stub: The storage stub fixture
        num_rows: Number of rows to create
        name: Name of the data frame
    """
    csv_data = {
        "id": list(range(1, num_rows + 1)),
        "value": [i * 10 for i in range(num_rows)],
    }
    await storage_stub.create_in_memory_data_frame(name=name, contents=csv_data)


async def _get_resolved_data_frame(
    storage_stub: "StorageStub",
    data_frames_kernel: "DataFramesKernel",
) -> "DataNodeResult":
    """Helper to get and resolve the first data frame from storage.

    Args:
        storage_stub: The storage stub fixture
        data_frames_kernel: The data frames kernel fixture

    Returns:
        The resolved data frame
    """
    tid = storage_stub.thread.tid
    data_frames = await storage_stub.list_data_frames(tid)
    assert len(data_frames) >= 1, "Expected at least one data frame"
    return await data_frames_kernel.resolve_data_frame(data_frames[0])


async def _slice_and_parse(
    resolved: "DataNodeResult",
    offset: int = 0,
    limit: int | None = None,
    column_names: list[str] | None = None,
    order_by: str | None = None,
) -> list[dict]:
    """Helper to slice a data frame and parse the JSON result.

    Args:
        resolved: The resolved data frame
        offset: Offset for slicing
        limit: Limit for slicing (None for default, -1 for all)
        column_names: Optional list of columns to select
        order_by: Optional column to order by

    Returns:
        List of row dictionaries
    """
    result = await resolved.slice(
        offset=offset,
        limit=limit,
        column_names=column_names,
        output_format="json",
        order_by=order_by,
    )
    assert isinstance(result, bytes), "Expected slice to return bytes"
    return json.loads(result)


@pytest.mark.asyncio
async def test_slice_with_no_limit_uses_default(
    storage_stub: "StorageStub",
    data_frames_kernel: "DataFramesKernel",
):
    """Test that slice with limit=None applies DEFAULT_SLICE_LIMIT.

    This verifies Fix #1: Default limit prevents loading all rows into memory.
    """
    from agent_platform.server.data_frames.data_node import DEFAULT_SLICE_LIMIT

    # Create a data frame with more rows than the default limit
    num_rows = DEFAULT_SLICE_LIMIT + 500
    await _create_simple_data_frame(storage_stub, num_rows)
    resolved = await _get_resolved_data_frame(storage_stub, data_frames_kernel)

    # Call slice without limit - should default to DEFAULT_SLICE_LIMIT
    loaded = await _slice_and_parse(resolved, offset=0, limit=None)

    # Should only return DEFAULT_SLICE_LIMIT rows, not all rows
    assert len(loaded) == DEFAULT_SLICE_LIMIT, (
        f"Expected {DEFAULT_SLICE_LIMIT} rows when limit=None, but got {len(loaded)}"
    )
    assert loaded[0]["id"] == 1
    assert loaded[-1]["id"] == DEFAULT_SLICE_LIMIT


@pytest.mark.asyncio
async def test_slice_with_excessive_limit_is_capped(
    storage_stub: "StorageStub",
    data_frames_kernel: "DataFramesKernel",
):
    """Test that slice with limit > MAX_SLICE_LIMIT is capped.

    This verifies Fix #2: Maximum limit cap prevents memory exhaustion.
    """
    from agent_platform.server.data_frames.data_node import MAX_SLICE_LIMIT

    # Create a data frame with more rows than the max limit
    num_rows = MAX_SLICE_LIMIT + 1000
    await _create_simple_data_frame(storage_stub, num_rows)
    resolved = await _get_resolved_data_frame(storage_stub, data_frames_kernel)

    # Request more than MAX_SLICE_LIMIT - should be capped
    excessive_limit = MAX_SLICE_LIMIT * 2
    loaded = await _slice_and_parse(resolved, offset=0, limit=excessive_limit)

    # Should only return MAX_SLICE_LIMIT rows, not the requested amount
    assert len(loaded) == MAX_SLICE_LIMIT, (
        f"Expected {MAX_SLICE_LIMIT} rows when limit={excessive_limit}, but got {len(loaded)}"
    )
    assert loaded[0]["id"] == 1
    assert loaded[-1]["id"] == MAX_SLICE_LIMIT


@pytest.mark.asyncio
async def test_slice_with_limit_minus_one_fetches_all(
    storage_stub: "StorageStub",
    data_frames_kernel: "DataFramesKernel",
):
    """Test that limit=-1 explicitly fetches all rows (bypass safety limits)."""
    # Create a small dataset to test limit=-1
    num_rows = 150
    await _create_simple_data_frame(storage_stub, num_rows)
    resolved = await _get_resolved_data_frame(storage_stub, data_frames_kernel)

    # Use limit=-1 to explicitly request all rows
    loaded = await _slice_and_parse(resolved, offset=0, limit=-1)

    # Should return all rows
    assert len(loaded) == num_rows
    assert loaded[0]["id"] == 1
    assert loaded[-1]["id"] == num_rows


@pytest.mark.asyncio
async def test_slice_with_offset_and_no_limit_uses_default(
    storage_stub: "StorageStub",
    data_frames_kernel: "DataFramesKernel",
):
    """Test that offset with limit=None still applies DEFAULT_SLICE_LIMIT."""
    from agent_platform.server.data_frames.data_node import DEFAULT_SLICE_LIMIT

    num_rows = DEFAULT_SLICE_LIMIT + 1000
    await _create_simple_data_frame(storage_stub, num_rows)
    resolved = await _get_resolved_data_frame(storage_stub, data_frames_kernel)

    # Call slice with offset but no limit
    offset = 100
    loaded = await _slice_and_parse(resolved, offset=offset, limit=None)

    # Should return DEFAULT_SLICE_LIMIT rows starting from offset
    assert len(loaded) == DEFAULT_SLICE_LIMIT
    assert loaded[0]["id"] == offset + 1
    assert loaded[-1]["id"] == offset + DEFAULT_SLICE_LIMIT


@pytest.mark.asyncio
async def test_sample_rows_respects_max_limit(
    storage_stub: "StorageStub",
    data_frames_kernel: "DataFramesKernel",
):
    """Test that list_sample_rows respects MAX_SAMPLE_ROWS cap.

    This verifies the sampling operation also has memory safety limits.
    """
    from agent_platform.server.data_frames.data_node import MAX_SAMPLE_ROWS

    # Create a data frame with more rows than MAX_SAMPLE_ROWS
    num_rows = MAX_SAMPLE_ROWS + 500
    await _create_simple_data_frame(storage_stub, num_rows)
    resolved = await _get_resolved_data_frame(storage_stub, data_frames_kernel)

    # Request more samples than the max - should be capped
    excessive_samples = MAX_SAMPLE_ROWS * 2
    sample_rows = await resolved.list_sample_rows(excessive_samples)

    # Should be capped at MAX_SAMPLE_ROWS
    assert len(sample_rows) == MAX_SAMPLE_ROWS, (
        f"Expected {MAX_SAMPLE_ROWS} sample rows when requesting {excessive_samples}, but got {len(sample_rows)}"
    )


@pytest.mark.asyncio
async def test_sample_rows_with_minus_one_fetches_all(
    storage_stub: "StorageStub",
    data_frames_kernel: "DataFramesKernel",
):
    """Test that list_sample_rows with num_samples=-1 fetches all rows."""
    # Create a small dataset
    num_rows = 150
    await _create_simple_data_frame(storage_stub, num_rows)
    resolved = await _get_resolved_data_frame(storage_stub, data_frames_kernel)

    # Use -1 to explicitly request all rows
    sample_rows = await resolved.list_sample_rows(-1)

    # Should return all rows
    assert len(sample_rows) == num_rows
    assert sample_rows[0][0] == 1  # First row, id column
    assert sample_rows[-1][0] == num_rows  # Last row, id column


@pytest.mark.asyncio
async def test_sample_rows_normal_limits_work(
    storage_stub: "StorageStub",
    data_frames_kernel: "DataFramesKernel",
):
    """Test that normal sample sizes (within bounds) work correctly."""
    num_rows = 500
    await _create_simple_data_frame(storage_stub, num_rows)
    resolved = await _get_resolved_data_frame(storage_stub, data_frames_kernel)

    # Test various normal sample sizes
    for num_samples in [10, 50, 100, 200]:
        sample_rows = await resolved.list_sample_rows(num_samples)
        assert len(sample_rows) == num_samples, f"Expected {num_samples} sample rows, got {len(sample_rows)}"


@pytest.mark.asyncio
async def test_slice_normal_limits_work_correctly(
    storage_stub: "StorageStub",
    data_frames_kernel: "DataFramesKernel",
):
    """Test that normal limits (within bounds) work as expected."""
    num_rows = 1000
    await _create_simple_data_frame(storage_stub, num_rows)
    resolved = await _get_resolved_data_frame(storage_stub, data_frames_kernel)

    # Test various normal limits
    for limit in [10, 50, 100, 500]:
        loaded = await _slice_and_parse(resolved, offset=0, limit=limit)
        assert len(loaded) == limit, f"Expected {limit} rows, got {len(loaded)}"
