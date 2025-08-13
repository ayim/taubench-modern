import typing
from pathlib import Path

import pytest

if typing.TYPE_CHECKING:
    from agent_platform.server.storage.postgres import PostgresStorage
    from agent_platform.server.storage.sqlite import SQLiteStorage

    from .sample_model_creator import SampleModelCreator


async def check_data_frame_storage_crud(
    model_creator: "SampleModelCreator",
) -> None:
    from uuid import uuid4

    await model_creator.setup()

    # Save the data frame (this will call `save_data_frame`)
    sample_data_frame = await model_creator.obtain_sample_data_frame()

    # Verify it was saved by retrieving it
    retrieved_data_frame = await model_creator.storage.get_data_frame(
        sample_data_frame.data_frame_id
    )

    assert sample_data_frame is not retrieved_data_frame
    assert sample_data_frame == retrieved_data_frame

    non_existent_id = str(uuid4())

    with pytest.raises(ValueError, match=f"Data frame {non_existent_id} not found"):
        await model_creator.storage.get_data_frame(non_existent_id)

    # List data frames for the user and thread
    data_frames = await model_creator.storage.list_data_frames(sample_data_frame.thread_id)

    assert len(data_frames) == 1

    # Now, add a new data frame
    model_creator.sample_data_frame = None
    sample_data_frame_2 = await model_creator.obtain_sample_data_frame()
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
    await model_creator.storage.update_data_frame(sample_data_frame_2)

    retrieved_data_frame_2 = await model_creator.storage.get_data_frame(
        sample_data_frame_2.data_frame_id
    )
    assert retrieved_data_frame_2.name == "Updated Data Frame"

    # Update data frame with a non-existent id (use first one)
    with pytest.raises(ValueError, match=f"Data frame {sample_data_frame.data_frame_id} not found"):
        await model_creator.storage.update_data_frame(sample_data_frame)


@pytest.mark.asyncio
async def test_data_frame_storage_crud_sqlite(
    sqlite_storage: "SQLiteStorage",
    tmpdir: Path,
) -> None:
    """Test saving a new data frame."""
    from tests.storage.sample_model_creator import SampleModelCreator

    model_creator = SampleModelCreator(sqlite_storage, tmpdir)
    await check_data_frame_storage_crud(model_creator)


@pytest.mark.asyncio
async def test_data_frame_storage_crud_postgres(
    postgres_storage: "PostgresStorage",
    tmpdir: Path,
) -> None:
    """Test saving a new data frame."""
    from tests.storage.sample_model_creator import SampleModelCreator

    model_creator = SampleModelCreator(postgres_storage, tmpdir)
    await check_data_frame_storage_crud(model_creator)
