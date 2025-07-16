from typing import Any

import pytest


def make_text_message(text: str) -> list[dict[str, Any]]:
    """Create a standard text message for work item requests."""
    return [
        {
            "role": "user",
            "content": [{"kind": "text", "text": text}],
        }
    ]


def assert_work_item_url(body: dict[str, Any], agent_id: str, work_item_id: str) -> None:
    """Assert that the work item URL has the expected format."""
    expected_url_suffix = f"{agent_id}/{work_item_id}"
    assert body["work_item_url"].endswith(expected_url_suffix)
    # With default test settings, should start with "http://localhost:8000/"
    assert body["work_item_url"].startswith("http://localhost:8000/")


@pytest.mark.integration
@pytest.mark.usefixtures("copy_tmpdir_on_failure")
@pytest.mark.asyncio
async def test_work_item_callback_completed(
    agent_factory,
    work_item_factory,
    callback_server,
):
    """Test end-to-end callback execution for a COMPLETED work item."""

    # Arrange
    agent_id = agent_factory(
        runbook="You are a helpful assistant. Always respond with exactly what the user asks for."
    )
    callback_srv = callback_server(["COMPLETED"])

    messages = make_text_message("Say hello")

    # Act
    work_item_id, poller = await work_item_factory(
        agent_id=agent_id,
        messages=messages,
        callbacks=[{"url": callback_srv.url, "on_status": "COMPLETED"}],
        payload={"workflow": "callback_test"},
    )

    await poller.wait_for_status("COMPLETED")
    callback_received = callback_srv.wait_for("COMPLETED")

    # Assert
    assert callback_received, "Callback was not received within timeout"

    request = callback_srv.single_request()
    body = request["body"]

    assert request["path"] == "/webhook"
    assert request["headers"]["Content-Type"] == "application/json"
    assert body["work_item_id"] == work_item_id
    assert body["agent_id"] == agent_id
    assert body["status"] == "COMPLETED"
    assert body["thread_id"] is not None

    assert_work_item_url(body, agent_id, work_item_id)


@pytest.mark.integration
@pytest.mark.usefixtures("copy_tmpdir_on_failure")
@pytest.mark.asyncio
async def test_work_item_callback_needs_review(
    agent_factory,
    work_item_factory,
    callback_server,
):
    """Test end-to-end callback execution for a NEEDS_REVIEW work item."""

    # Arrange
    agent_id = agent_factory(
        runbook=(
            "You are a helpful assistant. When you encounter requests that require "
            "external data or capabilities you don't have, express uncertainty "
            "and request human assistance."
        )
    )
    callback_srv = callback_server(["NEEDS_REVIEW"])

    messages = make_text_message(
        "Send an email to john@company.com with our latest quarterly financial results "
        "and market analysis."
    )

    # Act
    work_item_id, poller = await work_item_factory(
        agent_id=agent_id,
        messages=messages,
        callbacks=[{"url": callback_srv.url, "on_status": "NEEDS_REVIEW"}],
        payload={"workflow": "callback_test_needs_review"},
    )

    await poller.wait_for_status("NEEDS_REVIEW")
    callback_received = callback_srv.wait_for("NEEDS_REVIEW")

    # Assert
    assert callback_received, "Callback was not received within timeout"

    request = callback_srv.single_request()
    body = request["body"]

    assert request["path"] == "/webhook"
    assert request["headers"]["Content-Type"] == "application/json"
    assert body["work_item_id"] == work_item_id
    assert body["agent_id"] == agent_id
    assert body["status"] == "NEEDS_REVIEW"
    assert body["thread_id"] is not None

    assert_work_item_url(body, agent_id, work_item_id)


@pytest.mark.integration
@pytest.mark.usefixtures("copy_tmpdir_on_failure")
@pytest.mark.asyncio
async def test_work_item_callback_with_signature(
    agent_factory,
    work_item_factory,
    callback_server,
):
    """Test end-to-end callback execution with signature verification."""

    # Arrange
    signature_secret = "test_secret_key_123"
    agent_id = agent_factory(runbook="You are a helpful assistant. Always respond concisely.")
    callback_srv = callback_server(["COMPLETED"])

    messages = make_text_message("Count from 1 to 3")

    # Act
    work_item_id, poller = await work_item_factory(
        agent_id=agent_id,
        messages=messages,
        callbacks=[
            {
                "url": callback_srv.url,
                "on_status": "COMPLETED",
                "signature_secret": signature_secret,
            }
        ],
        payload={"workflow": "signature_test"},
    )

    await poller.wait_for_status("COMPLETED")
    callback_received = callback_srv.wait_for("COMPLETED")

    # Assert
    assert callback_received, "Callback was not received within timeout"

    request = callback_srv.single_request()
    body = request["body"]

    assert request["path"] == "/webhook"
    assert request["headers"]["Content-Type"] == "application/json"
    assert "X-SEMA4AI-SIGNATURE" in request["headers"]

    # Verify signature is correct
    from agent_platform.server.work_items.callbacks import _compute_signature

    expected_signature = _compute_signature(signature_secret, body)
    actual_signature = request["headers"]["X-SEMA4AI-SIGNATURE"]
    assert actual_signature == expected_signature

    assert body["work_item_id"] == work_item_id
    assert body["agent_id"] == agent_id
    assert body["status"] == "COMPLETED"
    assert body["thread_id"] is not None

    assert_work_item_url(body, agent_id, work_item_id)


@pytest.mark.integration
@pytest.mark.usefixtures("copy_tmpdir_on_failure")
@pytest.mark.asyncio
async def test_work_item_callback_multiple_callbacks(
    agent_factory,
    work_item_factory,
    callback_server,
):
    """Test end-to-end execution of multiple callbacks on the same work item."""

    # Arrange
    agent_id = agent_factory(
        runbook="You are a helpful assistant. Always respond with exactly what the user asks for."
    )
    completed_srv = callback_server(["COMPLETED"])
    needs_review_srv = callback_server(["NEEDS_REVIEW"])

    messages = make_text_message("Say 'test complete'")

    # Act
    work_item_id, poller = await work_item_factory(
        agent_id=agent_id,
        messages=messages,
        callbacks=[
            {"url": completed_srv.url, "on_status": "COMPLETED"},
            {"url": needs_review_srv.url, "on_status": "NEEDS_REVIEW"},
        ],
        payload={"workflow": "multiple_callbacks_test"},
    )

    final_status = await poller.wait_for_final_status()

    # Assert - only the appropriate callback should have fired
    if final_status == "COMPLETED":
        callback_received = completed_srv.wait_for("COMPLETED")
        assert callback_received, "COMPLETED callback was not received"
        assert len(completed_srv.requests) == 1
        assert len(needs_review_srv.requests) == 0

        request = completed_srv.single_request()
        assert request["body"]["status"] == "COMPLETED"
        assert request["body"]["work_item_id"] == work_item_id

    elif final_status == "NEEDS_REVIEW":
        callback_received = needs_review_srv.wait_for("NEEDS_REVIEW")
        assert callback_received, "NEEDS_REVIEW callback was not received"
        assert len(needs_review_srv.requests) == 1
        assert len(completed_srv.requests) == 0

        request = needs_review_srv.single_request()
        assert request["body"]["status"] == "NEEDS_REVIEW"
        assert request["body"]["work_item_id"] == work_item_id

    else:
        pytest.fail(f"Unexpected final status: {final_status}")
