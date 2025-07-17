import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import patch

import pytest

from agent_platform.core.thread.base import ThreadMessage
from agent_platform.core.thread.content.text import ThreadTextContent
from agent_platform.core.work_items.work_item import (
    WorkItem,
    WorkItemCallback,
    WorkItemCallbackPayload,
    WorkItemStatus,
)
from agent_platform.server.work_items.callbacks import (
    InvalidTimeoutError,
    InvalidWorkItemError,
    _build_work_item_url,
    _compute_signature,
    _execute_callback,
    execute_callbacks,
)


@pytest.mark.asyncio
class TestWorkItemsCallbacks:
    async def test_build_work_item_url(self):
        """Test the _build_work_item_url function with various scenarios."""
        # Test with all fields populated
        work_item = WorkItem(
            work_item_id="test_work_item_123",
            user_id="user_456",
            agent_id="agent_789",
            thread_id="thread_012",
            status=WorkItemStatus.COMPLETED,
        )

        url = _build_work_item_url(work_item)
        # With default settings (WORKSPACE_ID="no-workspace-id", WORKROOM_URL="http://localhost:8000/")
        # The function includes workspace_id in the URL path
        expected_url = (
            f"http://localhost:8000/no-workspace-id/{work_item.agent_id}/{work_item.thread_id}"
        )
        assert url == expected_url

        # Test with None agent_id (should raise InvalidWorkItemError)
        work_item.agent_id = None
        with pytest.raises(InvalidWorkItemError, match="agent_id should not be None or empty"):
            _build_work_item_url(work_item)

        # Test with empty string agent_id (should raise InvalidWorkItemError)
        work_item.agent_id = ""
        with pytest.raises(InvalidWorkItemError, match="agent_id should not be None or empty"):
            _build_work_item_url(work_item)

        # Test with whitespace agent_id (should raise InvalidWorkItemError)
        work_item.agent_id = "   "
        with pytest.raises(InvalidWorkItemError, match="agent_id should not be None or empty"):
            _build_work_item_url(work_item)

    async def test_compute_signature_consistency(self):
        """Test that the same object generates the same signature twice."""
        body = WorkItemCallbackPayload.model_validate(
            {
                "work_item_id": "test_id",
                "agent_id": "agent_123",
                "thread_id": "thread_456",
                "status": "COMPLETED",
                "work_item_url": "http://localhost:8000",
            }
        )
        secret = "test_secret"

        signature1 = _compute_signature(secret, body.model_dump())
        signature2 = _compute_signature(secret, body.model_dump())

        assert signature1 == signature2
        assert isinstance(signature1, str)
        assert len(signature1) == 64  # SHA-256 hex digest is 64 characters

    async def test_compute_signature_serialization_order(self):
        """Test that objects with the same parameters but different order
        generate the same signature."""
        body1 = WorkItemCallbackPayload.model_validate(
            {
                "work_item_id": "test_id",
                "agent_id": "agent_123",
                "thread_id": "thread_456",
                "status": "COMPLETED",
                "work_item_url": "http://localhost:8000",
            }
        )

        body2 = WorkItemCallbackPayload.model_validate(
            {
                "status": "COMPLETED",
                "work_item_id": "test_id",
                "thread_id": "thread_456",
                "agent_id": "agent_123",
                "work_item_url": "http://localhost:8000",
            }
        )

        secret = "test_secret"

        signature1 = _compute_signature(secret, body1.model_dump())
        signature2 = _compute_signature(secret, body2.model_dump())

        assert signature1 == signature2

    async def test_compute_signature_different_secrets(self):
        """Test that different secrets generate different signatures."""
        body = WorkItemCallbackPayload.model_validate(
            {
                "work_item_id": "test_id",
                "agent_id": "agent_123",
                "thread_id": "thread_456",
                "status": "COMPLETED",
                "work_item_url": "http://localhost:8000",
            }
        )

        signature1 = _compute_signature("secret1", body.model_dump())
        signature2 = _compute_signature("secret2", body.model_dump())

        assert signature1 != signature2

    async def test_compute_signature_different_bodies(self):
        """Test that different bodies generate different signatures."""
        body1 = WorkItemCallbackPayload.model_validate(
            {
                "work_item_id": "test_id",
                "agent_id": "agent_123",
                "thread_id": "thread_456",
                "status": "COMPLETED",
                "work_item_url": "http://localhost:8000",
            }
        )

        body2 = WorkItemCallbackPayload.model_validate(
            {
                "work_item_id": "test_id",
                "agent_id": "agent_123",
                "thread_id": "thread_457",
                "status": "COMPLETED",
                "work_item_url": "http://localhost:8000",
            }
        )

        secret = "test_secret"

        signature1 = _compute_signature(secret, body1.model_dump())
        signature2 = _compute_signature(secret, body2.model_dump())

        assert signature1 != signature2

    async def test_execute_callback_with_server(self):
        """Test webhook execution with an in-process HTTP server."""
        # Track received requests
        received_requests = []

        class TestRequestHandler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                content_length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_length).decode("utf-8")

                received_requests.append(
                    {"path": self.path, "headers": dict(self.headers), "body": json.loads(body)}
                )

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status": "ok"}')

            def log_message(self, f, *args):
                # Suppress log messages
                pass

        # Start server in a separate thread
        server = HTTPServer(("localhost", 0), TestRequestHandler)
        server_port = server.server_address[1]
        server_thread = threading.Thread(target=server.serve_forever)
        server_thread.daemon = True
        server_thread.start()

        try:
            # Create test work item
            work_item = WorkItem(
                work_item_id="test_work_item_123",
                user_id="user_456",
                agent_id="agent_789",
                thread_id="thread_012",
                status=WorkItemStatus.COMPLETED,
                messages=[
                    ThreadMessage(content=[ThreadTextContent(text="Hello")], role="user"),
                    ThreadMessage(content=[ThreadTextContent(text="World")], role="agent"),
                    ThreadMessage(content=[ThreadTextContent(text="Test message")], role="user"),
                ],
            )

            # Create callback
            callback = WorkItemCallback(
                url=f"http://localhost:{server_port}/webhook", on_status=WorkItemStatus.COMPLETED
            )

            # Execute callback
            await _execute_callback(work_item, callback)

            # Verify request was received
            assert len(received_requests) == 1
            request = received_requests[0]

            assert request["path"] == "/webhook"
            assert request["headers"]["Content-Type"] == "application/json"
            assert "X-SEMA4AI-SIGNATURE" not in request["headers"]

            # Verify request body
            body = request["body"]
            assert body["work_item_id"] == "test_work_item_123"
            assert body["agent_id"] == "agent_789"
            assert body["thread_id"] == "thread_012"
            assert body["status"] == "COMPLETED"
            # With default settings, the URL should be "http://localhost:8000/no-workspace-id/agent_789/thread_012"
            expected_url = (
                f"http://localhost:8000/no-workspace-id/{work_item.agent_id}/{work_item.thread_id}"
            )
            assert body["work_item_url"] == expected_url

        finally:
            server.shutdown()
            server_thread.join(timeout=1)

    @pytest.mark.parametrize(
        "status",
        [
            WorkItemStatus.COMPLETED,
            WorkItemStatus.ERROR,
            WorkItemStatus.NEEDS_REVIEW,
            WorkItemStatus.CANCELLED,
        ],
    )
    async def test_allowed_statuses_for_callbacks(self, status):
        """Test that the allowed statuses for callbacks are the same as the
        allowed statuses for work items."""
        callback = WorkItemCallback(
            url="http://example.com/webhook",
            on_status=status,
        )
        assert callback.on_status == status

    @pytest.mark.parametrize(
        "status",
        [
            WorkItemStatus.PENDING,
            WorkItemStatus.PRECREATED,
            WorkItemStatus.EXECUTING,
        ],
    )
    async def test_disallowed_statuses_for_callbacks(self, status):
        """Test that disallowed statuses for callbacks raise validation errors."""
        with pytest.raises(ValueError, match="Calbacks can only be registered on"):
            WorkItemCallback.model_validate(
                {
                    "url": "http://example.com/webhook",
                    "on_status": status.value,
                }
            )

    @pytest.mark.parametrize("secret", ["this_is_secret", "another_secret_123"])
    async def test_execute_callback_with_signature(self, secret):
        """Test webhook execution with signature verification."""
        # Track received requests
        received_requests = []

        class TestRequestHandler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                content_length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_length).decode("utf-8")

                received_requests.append(
                    {"path": self.path, "headers": dict(self.headers), "body": json.loads(body)}
                )

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status": "ok"}')

            def log_message(self, f, *args):
                # Suppress log messages
                pass

        # Start server in a separate thread
        server = HTTPServer(("localhost", 0), TestRequestHandler)
        server_port = server.server_address[1]
        server_thread = threading.Thread(target=server.serve_forever)
        server_thread.daemon = True
        server_thread.start()

        try:
            # Create test work item
            work_item = WorkItem(
                work_item_id="test_work_item_123",
                user_id="user_456",
                agent_id="agent_789",
                thread_id="thread_012",
                status=WorkItemStatus.COMPLETED,
                messages=[
                    ThreadMessage(content=[ThreadTextContent(text="Hello")], role="user"),
                    ThreadMessage(content=[ThreadTextContent(text="World")], role="agent"),
                    ThreadMessage(content=[ThreadTextContent(text="Test message")], role="user"),
                ],
            )

            # Create callback with signature
            callback = WorkItemCallback(
                url=f"http://localhost:{server_port}/webhook",
                signature_secret=secret,
                on_status=WorkItemStatus.COMPLETED,
            )

            # Execute callback
            await _execute_callback(work_item, callback)

            # Verify request was received
            assert len(received_requests) == 1
            request = received_requests[0]

            assert request["path"] == "/webhook"
            assert request["headers"]["Content-Type"] == "application/json"
            assert "X-SEMA4AI-SIGNATURE" in request["headers"]

            # Verify signature
            expected_signature = _compute_signature(secret, request["body"])
            assert request["headers"]["X-SEMA4AI-SIGNATURE"] == expected_signature
            # With default settings, the URL should be "http://localhost:8000/no-workspace-id/agent_789/thread_012"
            expected_url = (
                f"http://localhost:8000/no-workspace-id/{work_item.agent_id}/{work_item.thread_id}"
            )
            assert request["body"]["work_item_url"] == expected_url

        finally:
            server.shutdown()
            server_thread.join(timeout=1)

    async def test_execute_callbacks_no_callbacks(self):
        """Test that execute_callbacks does nothing when there are no callbacks."""
        work_item = WorkItem(
            work_item_id="test_work_item_123",
            user_id="user_456",
            agent_id="agent_789",
            thread_id="thread_012",
            status=WorkItemStatus.COMPLETED,
            callbacks=[],  # No callbacks
        )

        # Should complete without error
        await execute_callbacks(work_item, WorkItemStatus.COMPLETED)

    async def test_execute_callbacks_mismatched_status(self):
        """Test that execute_callbacks does nothing when status doesn't match any callback."""
        work_item = WorkItem(
            work_item_id="test_work_item_123",
            user_id="user_456",
            agent_id="agent_789",
            thread_id="thread_012",
            status=WorkItemStatus.COMPLETED,
            callbacks=[
                WorkItemCallback(
                    url="http://example.com/webhook",
                    on_status=WorkItemStatus.ERROR,  # Different status
                )
            ],
        )

        # Should complete without error (no callbacks to execute)
        await execute_callbacks(work_item, WorkItemStatus.COMPLETED)

    async def test_execute_callbacks_matching_status(self):
        """Test that execute_callbacks executes callbacks with matching status."""
        # Track received requests
        received_requests = []

        class TestRequestHandler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                content_length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_length).decode("utf-8")

                received_requests.append(
                    {"path": self.path, "headers": dict(self.headers), "body": json.loads(body)}
                )

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status": "ok"}')

            def log_message(self, f, *args):
                # Suppress log messages
                pass

        # Start server in a separate thread
        server = HTTPServer(("localhost", 0), TestRequestHandler)
        server_port = server.server_address[1]
        server_thread = threading.Thread(target=server.serve_forever)
        server_thread.daemon = True
        server_thread.start()

        try:
            work_item = WorkItem(
                work_item_id="test_work_item_123",
                user_id="user_456",
                agent_id="agent_789",
                thread_id="thread_012",
                status=WorkItemStatus.COMPLETED,
                callbacks=[
                    WorkItemCallback(
                        url=f"http://localhost:{server_port}/webhook1",
                        on_status=WorkItemStatus.COMPLETED,
                    ),
                    WorkItemCallback(
                        url=f"http://localhost:{server_port}/webhook2",
                        on_status=WorkItemStatus.ERROR,  # Different status
                    ),
                    WorkItemCallback(
                        url=f"http://localhost:{server_port}/webhook3",
                        on_status=WorkItemStatus.COMPLETED,
                    ),
                ],
            )

            # Execute callbacks for COMPLETED status
            await execute_callbacks(work_item, WorkItemStatus.COMPLETED)

            # Should have received 2 requests (webhook1 and webhook3)
            assert len(received_requests) == 2
            paths = [req["path"] for req in received_requests]
            assert "/webhook1" in paths
            assert "/webhook3" in paths
            assert "/webhook2" not in paths

        finally:
            server.shutdown()
            server_thread.join(timeout=1)

    @pytest.mark.parametrize("timeout", [0, -1, None])
    async def test_execute_callbacks_timeout(self, timeout):
        """Test that execute_callbacks times out with invalid timeout."""
        with pytest.raises(InvalidTimeoutError):
            await execute_callbacks(
                WorkItem(
                    work_item_id="test_work_item_123",
                    user_id="user_456",
                    agent_id="agent_789",
                    thread_id="thread_012",
                ),
                WorkItemStatus.COMPLETED,
                timeout=timeout,
            )

    async def test_execute_callback_error_handling(self):
        """Test that callback errors are handled gracefully."""
        work_item = WorkItem(
            work_item_id="test_work_item_123",
            user_id="user_456",
            agent_id="agent_789",
            thread_id="thread_012",
            status=WorkItemStatus.COMPLETED,
            messages=[ThreadMessage(content=[ThreadTextContent(text="Hello")], role="user")],
        )

        # Create callback with invalid URL
        callback = WorkItemCallback(
            url="http://invalid-url-that-does-not-exist.com/webhook",
            on_status=WorkItemStatus.COMPLETED,
        )

        # Should not raise an exception
        with patch("agent_platform.server.work_items.callbacks.logger") as mock_logger:
            await _execute_callback(work_item, callback)

            # Should have logged an error
            mock_logger.error.assert_called_once()
            error_message = mock_logger.error.call_args[0][0]
            assert "Callback failed" in error_message
            assert "test_work_item_123" in error_message

    async def test_execute_callbacks_no_matching_status(self):
        """Test that callbacks are not executed when status doesn't match."""
        # Track received callback requests
        received_requests = []

        class CallbackHandler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                content_length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_length).decode("utf-8")
                received_requests.append(json.loads(body))

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status": "received"}')

            def log_message(self, format, *args):  # noqa: A002
                pass

        # Start callback server
        server = HTTPServer(("localhost", 0), CallbackHandler)
        callback_url = f"http://localhost:{server.server_address[1]}/webhook"

        server_thread = threading.Thread(target=server.serve_forever)
        server_thread.daemon = True
        server_thread.start()

        try:
            # Create work item with callback for COMPLETED status
            work_item = WorkItem(
                work_item_id="test-work-item-123",
                user_id="test-user",
                agent_id="test-agent-456",
                thread_id="test-thread-789",
                status=WorkItemStatus.NEEDS_REVIEW,  # Different from callback status
                callbacks=[
                    WorkItemCallback(
                        url=callback_url,
                        on_status=WorkItemStatus.COMPLETED,  # Callback only for COMPLETED
                    )
                ],
            )

            # Execute callbacks for NEEDS_REVIEW status (should not trigger callback)
            await execute_callbacks(work_item, WorkItemStatus.NEEDS_REVIEW)

            # Give it a moment to ensure no callbacks are sent
            import asyncio

            await asyncio.sleep(0.1)

            # Verify no callbacks were received
            assert len(received_requests) == 0

        finally:
            server.shutdown()
            server_thread.join(timeout=1)
