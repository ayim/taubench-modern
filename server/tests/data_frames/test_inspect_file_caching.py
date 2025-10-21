"""Tests for caching functionality in inspect_file_as_data_frame method."""

import pytest

from server.tests.storage_fixtures import *  # noqa


@pytest.mark.asyncio
async def test_inspect_file_caching_metadata_only(  # noqa: PLR0915
    sqlite_storage, tmpdir, monkeypatch, data_regression
) -> None:
    """Test caching of metadata-only inspection results."""
    from agent_platform.core.user import User
    from agent_platform.server.api.private_v2.threads_data_frames import (
        CacheHitEvent,
        cache_tracking_callback,
        inspect_file_as_data_frame,
    )
    from server.tests.storage.sample_model_creator import SampleModelCreator

    monkeypatch.setattr(
        "agent_platform.server.api.private_v2.threads_data_frames._CacheHandler.max_samples_in_short_samples_cache",
        10,
    )

    storage = sqlite_storage

    found_events: list[CacheHitEvent] = []
    with cache_tracking_callback.register(lambda event: found_events.append(event)):
        sample_model_creator = SampleModelCreator(storage, tmpdir)

        user_id = await sample_model_creator.get_user_id()
        agent_thread = await sample_model_creator.obtain_sample_thread()
        tid = agent_thread.thread_id

        file_content = b"""
name,age
John,25
Jane,30
Jim,35
Jill,40
Albert,45
Barbara,50
Charlie,55
Diana,60
Edward,65
Fiona,70
George,75
Helen,80
Irene,85
Jack,90
"""
        sample_file = await sample_model_creator.obtain_sample_file(
            file_content=file_content, file_name="my.csv", mime_type="text/csv"
        )
        assert await storage.get_file_by_id(sample_file.file_id, user_id=user_id) is not None
        assert len(await storage.list_cached_entries()) == 0
        assert len(found_events) == 0

        async def make_inspect(num_samples=0):
            result = await inspect_file_as_data_frame(
                user=User(user_id=user_id, sub="tenant:test:user:test-user"),
                tid=tid,
                storage=storage,
                num_samples=num_samples,
                file_id=sample_file.file_id,
                file_ref=None,
                sheet_name=None,
            )

            assert isinstance(result, list)
            assert len(result) == 1
            df = result[0]
            assert df.num_rows == 14
            assert df.num_columns == 2
            assert df.column_headers == ["name", "age"]
            if num_samples == -1:
                assert len(df.sample_rows) == 14
            else:
                assert len(df.sample_rows) == num_samples

            data_regression.check(df.sample_rows, basename=f"inspect_sample_rows_{num_samples}")
            return df

        await make_inspect()  # no cache hit yet

        assert len(await storage.list_cached_entries()) == 1
        assert len(found_events) == 0
        await make_inspect()  # Now we should have a cache hit
        assert len(await storage.list_cached_entries()) == 1
        assert len(found_events) == 1

        assert (
            ", ".join(str(event) for event in found_events)
            == "cache_hit: single_sheet - 1 data frame"
        )

        del found_events[:]
        # Now we should have a cache hit of the metadata again and store the samples in the cache
        await make_inspect(num_samples=1)
        assert (
            ", ".join(str(event) for event in found_events)
            == "cache_hit: single_sheet - 1 data frame"
        )

        del found_events[:]
        await make_inspect(num_samples=1)
        assert (
            ", ".join(str(event) for event in found_events)
            == "cache_hit: single_sheet - 1 data frame, cache_hit: samples_small"
        )

        del found_events[:]
        await make_inspect(num_samples=11)  # Populate the full data cache
        assert (
            ", ".join(str(event) for event in found_events)
            == "cache_hit: single_sheet - 1 data frame"
        )

        del found_events[:]
        await make_inspect(num_samples=11)  # Must use the full data cache
        assert (
            ", ".join(str(event) for event in found_events)
            == "cache_hit: single_sheet - 1 data frame, cache_hit: full_data"
        )

        # clear all caches
        await storage.evict_old_cache_entries_by_date(0)
        assert len(await storage.list_cached_entries()) == 0

        del found_events[:]
        await make_inspect(num_samples=-1)
        assert not found_events, "No events should be found"
        await make_inspect(num_samples=-1)
        assert (
            ", ".join(str(event) for event in found_events)
            == "cache_hit: single_sheet - 1 data frame, cache_hit: full_data"
        )
