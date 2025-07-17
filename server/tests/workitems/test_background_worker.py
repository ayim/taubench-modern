import asyncio
import itertools
import math
from collections import defaultdict
from unittest.mock import patch
from uuid import uuid4

import pytest

from agent_platform.core.responses import ResponseMessage
from agent_platform.core.responses.content.text import ResponseTextContent
from agent_platform.core.responses.content.tool_use import ResponseToolUseContent
from agent_platform.core.thread.content import ThreadTextContent
from agent_platform.core.thread.messages import ThreadAgentMessage, ThreadUserMessage
from agent_platform.core.work_items import WorkItem, WorkItemStatus
from agent_platform.server.storage.option import StorageService
from agent_platform.server.work_items import background_worker as bw
from agent_platform.server.work_items.settings import Settings as WorkerSettings

pytest_plugins = ("server.tests.endpoints.conftest",)

# ---------------------------------------------------------------------------
# Helper: create a minimal WorkItem in the PENDING state
# ---------------------------------------------------------------------------


@pytest.fixture
def stub_validate_work_item_result(mocker):
    return mocker.patch(
        "agent_platform.server.work_items.background_worker._validate_success",
        return_value=WorkItemStatus.COMPLETED,
    )


def _make_work_item(user_id: str, agent_id: str, text: str = "test message") -> WorkItem:
    """Convenience helper to build a PENDING WorkItem for the given user/agent."""
    return WorkItem(
        work_item_id=str(uuid4()),
        user_id=user_id,
        agent_id=agent_id,
        thread_id=None,
        status=WorkItemStatus.PENDING,
        messages=[ThreadUserMessage(content=[ThreadTextContent(text=text)])],
        payload={},
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def configured_storage(storage):
    """Point the StorageService singleton used by background_worker at the test DB."""
    StorageService.reset()
    StorageService.set_for_testing(storage)
    return storage


@pytest.fixture(autouse=True)
def patch_worker_settings(monkeypatch):
    """Shrink worker settings so tests run quickly (small sleeps, small batches)."""
    test_settings = WorkerSettings(worker_interval=0, max_batch_size=5, work_item_timeout=1.0)
    monkeypatch.setattr(bw, "WORK_ITEMS_SETTINGS", test_settings, raising=False)
    return test_settings


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestBackgroundWorker:
    """Port of the legacy work-items worker tests to the new background_worker."""

    # --------------------------------------------------
    # execute_work_item
    # --------------------------------------------------
    @pytest.mark.asyncio
    async def test_execute_work_item(
        self, configured_storage, stub_user, seed_agents, stub_validate_work_item_result
    ):
        item = _make_work_item(stub_user.user_id, seed_agents[0].agent_id)
        await configured_storage.create_work_item(item)

        async def mock_agent_func(wi: WorkItem) -> bool:
            return True

        result = await bw.execute_work_item(item, mock_agent_func)
        assert result is True

        updated = await configured_storage.get_work_item(item.work_item_id)
        assert updated.status == WorkItemStatus.COMPLETED

    # --------------------------------------------------
    # errored_work_item (agent raises)
    # --------------------------------------------------
    @pytest.mark.asyncio
    async def test_errored_work_item(
        self,
        configured_storage,
        stub_user,
        seed_agents,
    ):
        item = _make_work_item(stub_user.user_id, seed_agents[0].agent_id)
        await configured_storage.create_work_item(item)

        async def error_agent_func(_: WorkItem) -> bool:
            raise Exception("Test error")

        result = await bw.execute_work_item(item, error_agent_func)
        assert result is False

        updated = await configured_storage.get_work_item(item.work_item_id)
        assert updated.status == WorkItemStatus.ERROR

    # --------------------------------------------------
    # failed_work_item (agent returns False)
    # --------------------------------------------------
    @pytest.mark.asyncio
    async def test_failed_work_item(
        self,
        configured_storage,
        stub_user,
        seed_agents,
    ):
        item = _make_work_item(stub_user.user_id, seed_agents[0].agent_id)
        await configured_storage.create_work_item(item)

        async def fail_agent_func(_: WorkItem) -> bool:
            return False

        result = await bw.execute_work_item(item, fail_agent_func)
        assert result is False

        updated = await configured_storage.get_work_item(item.work_item_id)
        assert updated.status == WorkItemStatus.ERROR

    # --------------------------------------------------
    # batch_processing
    # --------------------------------------------------
    @pytest.mark.asyncio
    async def test_batch_processing(
        self, configured_storage, stub_user, seed_agents, stub_validate_work_item_result
    ):
        num_work_items = 5
        counter = itertools.count()

        async def sometimes_fail_agent(_: WorkItem) -> bool:
            i = next(counter)
            match i % num_work_items:
                case 0:
                    return False  # handled failure
                case 1:
                    raise Exception("Injected error")  # unhandled --> becomes ERROR
                case _:
                    return True

        # Seed work-items in DB
        work_items: list[WorkItem] = []
        for _ in range(num_work_items):
            wi = _make_work_item(stub_user.user_id, seed_agents[0].agent_id)
            work_items.append(wi)
            await configured_storage.create_work_item(wi)

        work_item_ids = [wi.work_item_id for wi in work_items]
        results = await bw.run_batch(work_item_ids, sometimes_fail_agent, batch_timeout=2.0)

        # Expectations: 3 successes, 2 handled failures (False)
        assert len(results) == num_work_items
        assert sum(1 for r in results if r is True) == 3
        assert sum(1 for r in results if r is False) == 2

        # Verify DB statuses
        items = await configured_storage.get_work_items_by_ids(work_item_ids)
        rows_by_status: defaultdict[WorkItemStatus, list[str]] = defaultdict(list)
        for item in items:
            rows_by_status[item.status].append(item.work_item_id)

        assert len(rows_by_status[WorkItemStatus.ERROR]) == 2
        assert len(rows_by_status[WorkItemStatus.COMPLETED]) == 3

    # --------------------------------------------------
    # worker_iteration multiple passes
    # --------------------------------------------------
    @pytest.mark.asyncio
    async def test_worker_iteration(
        self, configured_storage, stub_user, seed_agents, stub_validate_work_item_result
    ):
        num_work_items = 21
        max_batch_size = bw.WORK_ITEMS_SETTINGS.max_batch_size  # 5 in fixture

        async def always_succeed(_: WorkItem) -> bool:
            return True

        # Add work-items
        for _ in range(num_work_items):
            await configured_storage.create_work_item(
                _make_work_item(stub_user.user_id, seed_agents[0].agent_id)
            )

        # Run enough iterations to pick them all up
        iterations = math.ceil(num_work_items / max_batch_size)
        for _ in range(iterations):
            await bw.worker_iteration(always_succeed)

        # All should be COMPLETED
        items = await configured_storage.list_work_items(stub_user.user_id)
        assert len(items) == num_work_items
        assert all(item.status == WorkItemStatus.COMPLETED for item in items)

    # --------------------------------------------------
    # timeout_work_item
    # --------------------------------------------------
    @pytest.mark.asyncio
    async def test_timeout_work_item(
        self, configured_storage, stub_user, seed_agents, stub_validate_work_item_result
    ):
        call_count = 0

        async def slow_agent(wi: WorkItem) -> bool:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                await asyncio.sleep(5)  # exceeds timeout
            return True

        # Two work-items: first will timeout, second succeeds
        items = [
            _make_work_item(stub_user.user_id, seed_agents[0].agent_id, "timeout-1"),
            _make_work_item(stub_user.user_id, seed_agents[0].agent_id, "timeout-2"),
        ]
        for wi in items:
            await configured_storage.create_work_item(wi)

        await bw.worker_iteration(slow_agent)

        statuses = {
            wi.work_item_id: (await configured_storage.get_work_item(wi.work_item_id)).status
            for wi in items
        }
        status_counts: defaultdict[WorkItemStatus, int] = defaultdict(int)
        for st in statuses.values():
            status_counts[st] += 1

        assert status_counts[WorkItemStatus.ERROR] == 1
        assert status_counts[WorkItemStatus.COMPLETED] == 1

    # --------------------------------------------------
    # concurrent_worker_iterations
    # --------------------------------------------------
    @pytest.mark.asyncio
    async def test_concurrent_worker_iterations(
        self, configured_storage, stub_user, seed_agents, stub_validate_work_item_result
    ):
        processed_ids: set[str] = set()
        lock = asyncio.Lock()

        async def tracking_agent(wi: WorkItem) -> bool:
            async with lock:
                processed_ids.add(wi.work_item_id)
            await asyncio.sleep(0.05)
            return True

        # Create 10 work-items
        work_items = [
            _make_work_item(stub_user.user_id, seed_agents[0].agent_id, f"msg-{i}")
            for i in range(10)
        ]
        for wi in work_items:
            await configured_storage.create_work_item(wi)

        expected_ids = {wi.work_item_id for wi in work_items}

        await asyncio.gather(
            bw.worker_iteration(tracking_agent),
            bw.worker_iteration(tracking_agent),
        )

        # Post-conditions
        items = await configured_storage.get_work_items_by_ids(list(expected_ids))
        assert all(item.status == WorkItemStatus.COMPLETED for item in items)
        assert processed_ids == expected_ids

    @pytest.mark.asyncio
    async def test_work_item_validate_success__needs_review(
        self, configured_storage, stub_user, seed_agents, stub_validate_work_item_result, mocker
    ):
        mocker.patch(
            "agent_platform.server.work_items.background_worker._validate_success",
            return_value=WorkItemStatus.NEEDS_REVIEW,
        )

        item = _make_work_item(stub_user.user_id, seed_agents[0].agent_id)
        await configured_storage.create_work_item(item)

        async def mock_agent_func(wi: WorkItem) -> bool:
            return True

        result = await bw.execute_work_item(item, mock_agent_func)
        assert result is True

        updated = await configured_storage.get_work_item(item.work_item_id)
        assert updated.status == WorkItemStatus.NEEDS_REVIEW

    # --------------------------------------------------
    # Validation logic tests (testing actual _validate_success function)
    # --------------------------------------------------
    @pytest.mark.asyncio
    async def test_validate_success_with_completed_response(
        self, configured_storage, stub_user, seed_agents
    ):
        """Test that _validate_success correctly parses a COMPLETED response
        from the validation LLM."""

        # Create a work item with realistic conversation messages
        item = _make_work_item(stub_user.user_id, seed_agents[0].agent_id)
        item.messages = [
            ThreadUserMessage(content=[ThreadTextContent(text="Please calculate 2+2")]),
            ThreadAgentMessage(
                content=[
                    ThreadTextContent(
                        text="The answer is 4. I have successfully completed the calculation."
                    )
                ]
            ),
        ]

        # Mock prompt_generate to return a COMPLETED validation response
        mock_response = ResponseMessage(
            content=[ResponseTextContent(text="COMPLETED")], role="agent"
        )

        with patch(
            "agent_platform.server.work_items.background_worker.prompt_generate",
            return_value=mock_response,
        ):
            result = await bw._validate_success(item)
            assert result == WorkItemStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_validate_success_with_needs_review_response(
        self, configured_storage, stub_user, seed_agents
    ):
        """Test that _validate_success correctly parses a NEEDS_REVIEW response
        from the validation LLM."""

        item = _make_work_item(stub_user.user_id, seed_agents[0].agent_id)
        item.messages = [
            ThreadUserMessage(content=[ThreadTextContent(text="Debug this complex system")]),
            ThreadAgentMessage(
                content=[
                    ThreadTextContent(text="I encountered errors and could not complete the task.")
                ]
            ),
        ]

        # Mock prompt_generate to return a NEEDS_REVIEW validation response
        mock_response = ResponseMessage(
            content=[ResponseTextContent(text="NEEDS_REVIEW")], role="agent"
        )

        with patch(
            "agent_platform.server.work_items.background_worker.prompt_generate",
            return_value=mock_response,
        ):
            result = await bw._validate_success(item)
            assert result == WorkItemStatus.NEEDS_REVIEW

    @pytest.mark.asyncio
    async def test_validate_success_with_invalid_response(
        self, configured_storage, stub_user, seed_agents
    ):
        """Test that _validate_success defaults to INDETERMINATE for invalid LLM responses."""

        item = _make_work_item(stub_user.user_id, seed_agents[0].agent_id)

        # Mock prompt_generate to return an invalid response that isn't COMPLETED or NEEDS_REVIEW
        mock_response = ResponseMessage(
            content=[ResponseTextContent(text="INVALID_STATUS")], role="agent"
        )

        with patch(
            "agent_platform.server.work_items.background_worker.prompt_generate",
            return_value=mock_response,
        ):
            result = await bw._validate_success(item)
            # Should default to INDETERMINATE for invalid responses
            assert result == WorkItemStatus.INDETERMINATE

    @pytest.mark.asyncio
    async def test_validate_success_with_empty_content(
        self, configured_storage, stub_user, seed_agents
    ):
        """Test that _validate_success defaults to INDETERMINATE when LLM returns empty content."""

        item = _make_work_item(stub_user.user_id, seed_agents[0].agent_id)

        # Mock prompt_generate to return empty content
        mock_response = ResponseMessage(content=[], role="agent")

        with patch(
            "agent_platform.server.work_items.background_worker.prompt_generate",
            return_value=mock_response,
        ):
            result = await bw._validate_success(item)
            assert result == WorkItemStatus.INDETERMINATE

    @pytest.mark.asyncio
    async def test_validate_success_with_non_text_content(
        self, configured_storage, stub_user, seed_agents
    ):
        """Test that _validate_success defaults to INDETERMINATE when LLM returns
        only non-text content."""

        item = _make_work_item(stub_user.user_id, seed_agents[0].agent_id)

        # Mock prompt_generate to return only tool use content (no text)
        mock_response = ResponseMessage(
            content=[
                ResponseToolUseContent(
                    tool_call_id="test", tool_name="test_tool", tool_input_raw="{}"
                )
            ],
            role="agent",
        )

        with patch(
            "agent_platform.server.work_items.background_worker.prompt_generate",
            return_value=mock_response,
        ):
            result = await bw._validate_success(item)
            assert result == WorkItemStatus.INDETERMINATE

    @pytest.mark.asyncio
    async def test_response_text_content_is_parsed(
        self, configured_storage, stub_user, seed_agents
    ):
        """Test that ResponseTextContent is correctly parsed by the validation logic."""

        item = _make_work_item(stub_user.user_id, seed_agents[0].agent_id)

        # Mock prompt_generate to return ResponseTextContent with COMPLETED
        mock_response = ResponseMessage(
            content=[ResponseTextContent(text="COMPLETED")], role="agent"
        )

        with patch(
            "agent_platform.server.work_items.background_worker.prompt_generate",
            return_value=mock_response,
        ):
            result = await bw._validate_success(item)
            assert result == WorkItemStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_thread_text_content_is_not_parsed(
        self, configured_storage, stub_user, seed_agents
    ):
        """Test that ThreadTextContent is not parsed by the validation logic.

        This test verifies that the validation logic correctly distinguishes between
        ThreadTextContent and ResponseTextContent, only parsing the latter.
        """

        item = _make_work_item(stub_user.user_id, seed_agents[0].agent_id)

        # Create a mock response with ThreadTextContent (wrong type for validation parsing)
        # Using type: ignore since this simulates incorrect content type
        mock_response = ResponseMessage(
            content=[ThreadTextContent(text="COMPLETED")],  # type: ignore
            role="agent",
        )

        with patch(
            "agent_platform.server.work_items.background_worker.prompt_generate",
            return_value=mock_response,
        ):
            result = await bw._validate_success(item)
            # Should return INDETERMINATE because ThreadTextContent isn't parsed
            assert result == WorkItemStatus.INDETERMINATE

    @pytest.mark.asyncio
    async def test_mixed_content_types(self, configured_storage, stub_user, seed_agents):
        """Test validation logic with mixed content types in the LLM response.

        Verifies that when multiple content types are present, the validation
        logic correctly extracts text from ResponseTextContent items.
        """

        item = _make_work_item(stub_user.user_id, seed_agents[0].agent_id)

        # Mock response with mixed content types
        # Note: validation logic takes the LAST ResponseTextContent, so put COMPLETED last
        mock_response = ResponseMessage(
            content=[
                ResponseToolUseContent(tool_call_id="test", tool_name="test", tool_input_raw="{}"),
                ResponseTextContent(text="Additional text"),
                ResponseTextContent(text="COMPLETED"),  # This will be the last one picked up
            ],
            role="agent",
        )

        with patch(
            "agent_platform.server.work_items.background_worker.prompt_generate",
            return_value=mock_response,
        ):
            result = await bw._validate_success(item)
            # Should parse the last ResponseTextContent and get COMPLETED
            assert result == WorkItemStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_validation_with_various_invalid_responses(
        self, configured_storage, stub_user, seed_agents
    ):
        """Test that various invalid validation responses all default to INDETERMINATE.

        Ensures robust handling of edge cases where the validation LLM returns
        unexpected text that doesn't match the expected COMPLETED/NEEDS_REVIEW values.
        """

        item = _make_work_item(stub_user.user_id, seed_agents[0].agent_id)

        # Test various invalid responses
        invalid_responses = [
            "INVALID_STATUS",
            "completed",  # wrong case
            "needs_review",  # wrong case
            "SUCCESS",
            "FAILED",
            "   ",  # whitespace only
            "COMPLETED but with extra text",
            "NEEDS_REVIEW but with extra text",
        ]

        for invalid_text in invalid_responses:
            mock_response = ResponseMessage(
                content=[ResponseTextContent(text=invalid_text)], role="agent"
            )

            with patch(
                "agent_platform.server.work_items.background_worker.prompt_generate",
                return_value=mock_response,
            ):
                result = await bw._validate_success(item)
                assert result == WorkItemStatus.INDETERMINATE, f"Failed for text: '{invalid_text}'"
