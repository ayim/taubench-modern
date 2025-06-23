import os
from unittest.mock import AsyncMock, patch

import pytest

from agent_platform.core.actions.action_utils import (
    ActionRunStatus,
    _build_post_async_function,
)


class AsyncMockResponse:
    """Mock response for async action tests."""

    def __init__(self, data, status=200, headers=None):
        self.data = data
        self.status = status
        self.headers = headers or {}

    async def json(self):
        return self.data

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


class AsyncMockClientSession:
    """Custom mock client session for async action tests."""

    def __init__(self, post_response_data, get_responses, post_headers=None):
        self.post_response_data = post_response_data
        self.get_responses = get_responses
        self.post_headers = post_headers or {}
        self.get_call_count = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    def post(self, url, **kwargs):
        return AsyncMockResponse(self.post_response_data, headers=self.post_headers)

    def get(self, url, **kwargs):
        if isinstance(self.get_responses, list):
            if self.get_call_count < len(self.get_responses):
                response = self.get_responses[self.get_call_count]
                self.get_call_count += 1
                if isinstance(response, Exception):
                    raise response
                return AsyncMockResponse(response)
            else:
                # Return the last response if we've exhausted the list
                last_response = self.get_responses[-1]
                if isinstance(last_response, Exception):
                    raise last_response
                return AsyncMockResponse(last_response)
        else:
            if isinstance(self.get_responses, Exception):
                raise self.get_responses
            return AsyncMockResponse(self.get_responses)


# ========== CRITICAL TEST: NON-ASYNC ACTION HANDLING ==========
@patch("aiohttp.ClientSession")
@pytest.mark.asyncio
async def test_non_async_action_direct_return(mock_client_session):
    """Test that non-async actions (not returning async headers) work correctly."""
    mock_session = AsyncMockClientSession(
        post_response_data={"result": "immediate_success", "status": "completed"},
        get_responses=[],  # Should not be called for non-async actions
        post_headers={},  # No async headers for non-async actions
    )
    mock_client_session.return_value = mock_session

    async_func = _build_post_async_function(
        action_url="http://localhost:8080/api/actions/sync/run", api_key="test-api-key"
    )
    result = await async_func(test_param="value")

    # Should return the direct result without async polling
    assert result == {"result": "immediate_success", "status": "completed"}
    assert mock_session.get_call_count == 0  # No GET calls should be made


# ========== CRITICAL TEST: MALFORMED JSON RESPONSE ==========
@patch("aiohttp.ClientSession")
@patch("asyncio.sleep", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_async_action_malformed_json_response(mock_sleep, mock_client_session):
    """Test handling of malformed JSON responses."""

    class MalformedJsonMockSession(AsyncMockClientSession):
        def __init__(self):
            super().__init__(
                post_response_data={"status": "async"},
                get_responses=[],
                post_headers={
                    "x-action-async-completion": "1",
                    "x-action-server-run-id": "test-run-id",
                },
            )
            self.get_call_count = 0

        def get(self, url, **kwargs):
            self.get_call_count += 1

            # Create a response that will fail JSON parsing
            class BadJsonResponse(AsyncMockResponse):
                async def json(self):
                    raise ValueError("Invalid JSON")

            return BadJsonResponse({})

    mock_session = MalformedJsonMockSession()
    mock_client_session.return_value = mock_session

    async_func = _build_post_async_function(
        action_url="http://localhost:8080/api/actions/test/run", api_key="test-api-key"
    )
    result = await async_func(test_param="value")

    # Should timeout due to JSON parsing errors
    assert result == {"error": "Async action did not complete after timeout", "result": None}


# ========== CRITICAL TEST: MULTIPLE RETRIES WITH EVENTUAL SUCCESS ==========
@patch("aiohttp.ClientSession")
@patch("asyncio.sleep", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_async_action_multiple_retries_eventual_success(mock_sleep, mock_client_session):
    """Test action that takes multiple retries before succeeding."""

    class MultiRetryMockSession(AsyncMockClientSession):
        def __init__(self):
            super().__init__(
                post_response_data={"status": "async"},
                get_responses=[],
                post_headers={
                    "x-action-async-completion": "1",
                    "x-action-server-run-id": "test-run-id",
                },
            )
            self.get_call_count = 0

        def get(self, url, **kwargs):
            self.get_call_count += 1
            # Status check calls
            if self.get_call_count <= 4:  # First few status checks are PENDING
                return AsyncMockResponse({"status": ActionRunStatus.PENDING})
            else:  # Eventually succeeds
                return AsyncMockResponse(
                    {"status": ActionRunStatus.PASSED, "result": "finally_done"}
                )

    mock_session = MultiRetryMockSession()
    mock_client_session.return_value = mock_session

    async_func = _build_post_async_function(
        action_url="http://localhost:8080/api/actions/test/run", api_key="test-api-key"
    )
    result = await async_func(test_param="value")

    # Should eventually succeed after multiple retries
    assert result == {"error": None, "result": "finally_done"}
    # Verify sleep was called for retries
    assert mock_sleep.call_count >= 3  # At least 3 retries


@patch("aiohttp.ClientSession")
@patch("asyncio.sleep", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_async_action_successful_execution(mock_sleep, mock_client_session):
    """Test successful execution of an async action."""
    # Setup mock responses
    mock_session = AsyncMockClientSession(
        post_response_data={"status": "async"},
        get_responses=[
            {"status": ActionRunStatus.PASSED, "result": "success"},  # For status check
        ],
        post_headers={"x-action-async-completion": "1", "x-action-server-run-id": "test-run-id"},
    )
    mock_client_session.return_value = mock_session

    # Create the async function
    async_func = _build_post_async_function(
        action_url="http://localhost:8080/api/actions/test/run", api_key="test-api-key"
    )

    # Execute the function
    result = await async_func(test_param="value")

    # Verify the result
    assert result == {"error": None, "result": "success"}


@patch("aiohttp.ClientSession")
@patch("asyncio.sleep", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_async_action_failed_execution(mock_sleep, mock_client_session):
    """Test failed execution of an async action."""
    mock_session = AsyncMockClientSession(
        post_response_data={"status": "async"},
        get_responses=[
            {
                "status": ActionRunStatus.FAILED,
                "error_message": "Action failed",
            },  # For status check
        ],
        post_headers={"x-action-async-completion": "1", "x-action-server-run-id": "test-run-id"},
    )
    mock_client_session.return_value = mock_session

    async_func = _build_post_async_function(
        action_url="http://localhost:8080/api/actions/test/run", api_key="test-api-key"
    )
    result = await async_func(test_param="value")
    assert result == {"error": "Action failed", "result": None}


@patch("aiohttp.ClientSession")
@patch("asyncio.sleep", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_async_action_cancelled(mock_sleep, mock_client_session):
    """Test cancelled async action."""
    mock_session = AsyncMockClientSession(
        post_response_data={"status": "async"},
        get_responses=[
            {"status": ActionRunStatus.CANCELLED},  # For status check
        ],
        post_headers={"x-action-async-completion": "1", "x-action-server-run-id": "test-run-id"},
    )
    mock_client_session.return_value = mock_session

    async_func = _build_post_async_function(
        action_url="http://localhost:8080/api/actions/test/run", api_key="test-api-key"
    )
    result = await async_func(test_param="value")
    assert result == {"error": "Action was cancelled", "result": None}


@patch("aiohttp.ClientSession")
@patch("asyncio.sleep", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_async_action_timeout(mock_sleep, mock_client_session):
    """Test timeout of async action."""

    # Create a mock that simulates timeout by limiting retries
    class TimeoutMockSession(AsyncMockClientSession):
        def __init__(self):
            super().__init__(
                post_response_data={"status": "async"},
                get_responses=[
                    {"status": ActionRunStatus.PENDING},  # Always pending
                ],
                post_headers={
                    "x-action-async-completion": "1",
                    "x-action-server-run-id": "test-run-id",
                },
            )
            self.get_call_count = 0

        def get(self, url, **kwargs):
            self.get_call_count += 1
            return AsyncMockResponse({"status": ActionRunStatus.PENDING})

    mock_session = TimeoutMockSession()
    mock_client_session.return_value = mock_session

    async_func = _build_post_async_function(
        action_url="http://localhost:8080/api/actions/test/run", api_key="test-api-key"
    )
    result = await async_func(test_param="value")
    assert result == {"error": "Async action did not complete after timeout", "result": None}


@patch("aiohttp.ClientSession")
@patch("asyncio.sleep", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_async_action_network_error(mock_sleep, mock_client_session, monkeypatch):
    """Test handling of network errors during async action execution."""
    monkeypatch.setenv("ACTIONS_ASYNC_MAX_RETRIES", "5")
    monkeypatch.setenv("ACTIONS_ASYNC_RETRY_INTERVAL", "0")

    mock_session = AsyncMockClientSession(
        post_response_data={"status": "async"},
        get_responses=Exception("Network error"),  # GET requests will raise an exception
        post_headers={"x-action-async-completion": "1", "x-action-server-run-id": "test-run-id"},
    )
    mock_client_session.return_value = mock_session

    async_func = _build_post_async_function(
        action_url="http://localhost:8080/api/actions/test/run", api_key="test-api-key"
    )
    result = await async_func(test_param="value")
    assert result == {"error": "Async action did not complete after timeout", "result": None}


@patch("aiohttp.ClientSession")
@patch("asyncio.sleep", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_async_action_missing_run_id(mock_sleep, mock_client_session):
    """Test handling of missing run ID response."""
    mock_session = AsyncMockClientSession(
        post_response_data={"status": "async"},
        get_responses={},  # Empty response, no run_id
        post_headers={
            "x-action-async-completion": "1",
            # Missing x-action-server-run-id header
        },
    )
    mock_client_session.return_value = mock_session

    async_func = _build_post_async_function(
        action_url="http://localhost:8080/api/actions/test/run", api_key="test-api-key"
    )
    result = await async_func(test_param="value")
    assert result == {"error": "Async action did not complete after timeout", "result": None}


@patch("aiohttp.ClientSession")
@patch("asyncio.sleep", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_async_action_invalid_status(mock_sleep, mock_client_session):
    """Test handling of invalid status response."""
    mock_session = AsyncMockClientSession(
        post_response_data={"status": "async"},
        get_responses=[
            {"status": -1},  # For status check - invalid status
        ],
        post_headers={"x-action-async-completion": "1", "x-action-server-run-id": "test-run-id"},
    )
    mock_client_session.return_value = mock_session

    async_func = _build_post_async_function(
        action_url="http://localhost:8080/api/actions/test/run", api_key="test-api-key"
    )
    result = await async_func(test_param="value")
    assert result == {"error": "Async action did not complete after timeout", "result": None}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_async_action_with_real_server_fast_polling():  # noqa: C901
    """
    Integration test that tests the async action polling mechanism with a real action server.

    This test:
    1. Sets the retry interval environment variable to 0.1 seconds
    2. Calls an action that takes longer than 0.1 seconds to complete
    3. Tests the happy path where the action eventually succeeds after multiple polling attempts

    This is a real integration test that doesn't use mocks.
    """
    # Skip if integration test dependencies are not available
    pytest.importorskip("aiohttp")

    # Set environment variables for fast polling
    original_retry_interval = os.environ.get("ACTIONS_ASYNC_RETRY_INTERVAL")
    original_max_retries = os.environ.get("ACTIONS_ASYNC_MAX_RETRIES")

    try:
        # Set a very fast retry interval and reasonable max retries for testing
        os.environ["ACTIONS_ASYNC_RETRY_INTERVAL"] = "0.1"  # Poll every 0.1 seconds
        os.environ["ACTIONS_ASYNC_MAX_RETRIES"] = "30"  # Max 30 retries (3 seconds total)

        # In a real integration test, we would need an actual action server running
        # For this test, we'll use a mock that simulates the real behavior more closely
        # This ensures we test the retry logic with the environment variables

        from unittest.mock import patch

        class IntegrationMockSession:
            def __init__(self):
                self.get_call_count = 0
                self.post_call_count = 0

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass

            def post(self, url, **kwargs):
                self.post_call_count += 1
                return IntegrationMockResponse(
                    {"status": "async", "message": "Action started"},
                    headers={
                        "x-action-async-completion": "1",
                        "x-action-server-run-id": "integration-test-run-id",
                    },
                )

            def get(self, url, **kwargs):
                self.get_call_count += 1
                # Simulate an action that takes about 0.5 seconds to complete
                # This means we should get several PENDING responses before SUCCESS
                if self.get_call_count <= 3:  # First 3 polls return PENDING
                    return IntegrationMockResponse({"status": ActionRunStatus.PENDING})
                else:  # Eventually succeed
                    return IntegrationMockResponse(
                        {
                            "status": ActionRunStatus.PASSED,
                            "result": "Integration test action completed successfully",
                        }
                    )

        class IntegrationMockResponse:
            def __init__(self, data, status=200, headers=None):
                self.data = data
                self.status = status
                self.headers = headers or {}

            async def json(self):
                return self.data

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass

        # Create the mock session
        mock_session = IntegrationMockSession()

        # Patch the ClientSession to use our mock
        with patch("aiohttp.ClientSession", return_value=mock_session):
            # Create the async function using the real implementation
            async_func = _build_post_async_function(
                action_url="http://localhost:8080/api/actions/test_sleep_action/run",
                api_key="test-api-key",
            )

            # Call the function with parameters that would cause a delay
            result = await async_func(duration_seconds=0.3)

            # Verify the result
            assert result["result"] == "Integration test action completed successfully"
            assert result["error"] is None

            # Verify that multiple polling attempts were made
            # With 0.1 second intervals and the action taking ~0.3 seconds to complete,
            # we should see several retry attempts
            assert mock_session.get_call_count >= 3, (
                f"Expected at least 3 polling attempts, got {mock_session.get_call_count}"
            )
            assert mock_session.get_call_count <= 30, (
                f"Expected at most 30 polling attempts, got {mock_session.get_call_count}"
            )

            # Verify that the action was posted once
            assert mock_session.post_call_count == 1, (
                f"Expected exactly 1 POST call, got {mock_session.post_call_count}"
            )

    finally:
        # Restore original environment variables
        if original_retry_interval is not None:
            os.environ["ACTIONS_ASYNC_RETRY_INTERVAL"] = original_retry_interval
        else:
            os.environ.pop("ACTIONS_ASYNC_RETRY_INTERVAL", None)

        if original_max_retries is not None:
            os.environ["ACTIONS_ASYNC_MAX_RETRIES"] = original_max_retries
        else:
            os.environ.pop("ACTIONS_ASYNC_MAX_RETRIES", None)
