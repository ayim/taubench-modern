import typing
from pathlib import Path

import pytest

if typing.TYPE_CHECKING:
    from agent_platform.server.storage.postgres import PostgresStorage
    from agent_platform.server.storage.sqlite import SQLiteStorage


@pytest.mark.asyncio
async def test_data_frame_storage_crud(
    storage: "SQLiteStorage|PostgresStorage",
    tmpdir: Path,
) -> None:
    """Test saving a new data frame."""
    from tests.storage.sample_model_creator import SampleModelCreator

    from agent_platform.core.errors.base import PlatformHTTPError

    model_creator = SampleModelCreator(storage, tmpdir)
    from uuid import uuid4

    from sqlalchemy.exc import IntegrityError

    await model_creator.setup()

    # Save the data frame (this will call `save_data_frame`)
    sample_data_frame = await model_creator.obtain_sample_data_frame(name="test_data_frame")

    # Verify it was saved by retrieving it
    retrieved_data_frame = await model_creator.storage.get_data_frame(
        thread_id=sample_data_frame.thread_id, data_frame_id=sample_data_frame.data_frame_id
    )

    assert sample_data_frame is not retrieved_data_frame
    assert sample_data_frame == retrieved_data_frame

    with pytest.raises(
        PlatformHTTPError, match="Unable to create data frame because the data frame name provided"
    ):
        await model_creator.obtain_sample_data_frame(name="test data frame")

    with pytest.raises(IntegrityError):
        await model_creator.obtain_sample_data_frame(name="test_data_frame")

    non_existent_id = str(uuid4())

    with pytest.raises(
        PlatformHTTPError,
        match=f"Data frame with id {non_existent_id} not found in "
        f"thread: {sample_data_frame.thread_id}",
    ):
        await model_creator.storage.get_data_frame(
            thread_id=sample_data_frame.thread_id, data_frame_id=non_existent_id
        )

    # List data frames for the user and thread
    data_frames = await model_creator.storage.list_data_frames(sample_data_frame.thread_id)

    assert len(data_frames) == 1

    # Now, add a new data frame
    model_creator.sample_data_frame = None
    sample_data_frame_2 = await model_creator.obtain_sample_data_frame(name="test_data_frame_2")
    data_frames = await model_creator.storage.list_data_frames(sample_data_frame.thread_id)

    assert len(data_frames) == 2

    # Check ids are there
    data_frame_ids = {df.data_frame_id for df in data_frames}
    assert data_frame_ids == {sample_data_frame.data_frame_id, sample_data_frame_2.data_frame_id}

    # Delete the first data frame
    await model_creator.storage.delete_data_frame(sample_data_frame.data_frame_id)

    data_frames = await model_creator.storage.list_data_frames(sample_data_frame.thread_id)
    assert {df.data_frame_id for df in data_frames} == {sample_data_frame_2.data_frame_id}

    # Update the 2nd data frame
    sample_data_frame_2.name = "Updated Data Frame"
    with pytest.raises(
        PlatformHTTPError, match="Unable to create data frame because the data frame name provided"
    ):
        await model_creator.storage.update_data_frame(sample_data_frame_2)

    sample_data_frame_2.name = "updated_data_frame"
    await model_creator.storage.update_data_frame(sample_data_frame_2)

    retrieved_data_frame_2 = await model_creator.storage.get_data_frame(
        thread_id=sample_data_frame_2.thread_id, data_frame_id=sample_data_frame_2.data_frame_id
    )
    assert retrieved_data_frame_2.name == "updated_data_frame"

    # Update data frame with a non-existent id (use first one)
    with pytest.raises(
        PlatformHTTPError, match=f"Data frame {sample_data_frame.data_frame_id} not found"
    ):
        await model_creator.storage.update_data_frame(sample_data_frame)

    # Now, delete the data frame by name
    await model_creator.storage.delete_data_frame_by_name(
        sample_data_frame.thread_id, "updated_data_frame"
    )
    data_frames = await model_creator.storage.list_data_frames(sample_data_frame.thread_id)
    assert len(data_frames) == 0
