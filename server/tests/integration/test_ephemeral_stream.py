import json
import uuid

import pytest
import websockets


@pytest.mark.integration
@pytest.mark.asyncio
async def test_ephemeral_stream_endpoint(base_url_agent_server, openai_api_key):
    """Test the ephemeral stream endpoint with a complete conversation flow."""
    # Convert HTTP URL to WebSocket URL
    ws_url = base_url_agent_server.replace("http://", "ws://") + "/api/v2/runs/ephemeral/stream"

    async with websockets.connect(ws_url) as ws:
        # Prepare ephemeral stream payload
        payload = {
            "agent": {
                "name": "TestAgent",
                "description": "Test agent for ephemeral stream",
                "version": "1.0",
                "runbook": "You are a helpful assistant.",
                "agent_architecture": {
                    "name": "agent_platform.architectures.default",
                    "version": "1.0.0",
                },
                "platform_configs": [
                    {
                        "kind": "openai",
                        "openai_api_key": openai_api_key,
                    }
                ],
                "action_packages": [
                    {
                        "name": "test-action-package",
                        "organization": "test-organization",
                        "version": "1.0.0",
                        "url": "https://example.com",
                        "api_key": "testing-api-key",
                        "allowed_actions": [],
                        "whitelist": "",
                    }
                ],
                "mcp_servers": [],
                "question_groups": [],
                "observability_configs": [],
                "mode": "conversational",
                "extra": {},
                "advanced_config": {},
                "metadata": {},
                "public": True,
            },
            "messages": [],
        }

        # Send the ephemeral stream request
        await ws.send(json.dumps(payload))

        # Track received events
        events = []
        agent_ready_received = False
        agent_finished_received = False

        # Read all messages until agent_finished
        while True:
            try:
                msg = await ws.recv()
                data = json.loads(msg)
                events.append(data)

                event_type = data.get("event_type")

                if event_type == "agent_ready":
                    agent_ready_received = True
                    # Verify required fields in agent_ready
                    assert "run_id" in data
                    assert "thread_id" in data
                    assert "agent_id" in data
                    assert "timestamp" in data
                    assert uuid.UUID(data["run_id"])  # Valid UUID
                    assert uuid.UUID(data["thread_id"])  # Valid UUID
                    assert uuid.UUID(data["agent_id"])  # Valid UUID

                elif event_type == "agent_finished":
                    agent_finished_received = True
                    break

                elif event_type == "agent_error":
                    error_msg = data.get("error_message", "Unknown error")
                    pytest.fail(f"Agent error: {error_msg}")

            except websockets.exceptions.ConnectionClosed:
                break

        # Verify the conversation flow
        assert agent_ready_received, "Should receive agent_ready event"
        assert agent_finished_received, "Should receive agent_finished event"
        assert len(events) >= 2, "Should receive at least agent_ready and agent_finished"

        # Verify first event is agent_ready
        assert events[0]["event_type"] == "agent_ready"

        # Verify last event is agent_finished
        assert events[-1]["event_type"] == "agent_finished"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_ephemeral_stream_with_message(base_url_agent_server, openai_api_key):
    """Test ephemeral stream basic flow with OpenAI integration."""
    ws_url = base_url_agent_server.replace("http://", "ws://") + "/api/v2/runs/ephemeral/stream"

    async with websockets.connect(ws_url) as ws:
        payload = {
            "agent": {
                "name": "TestAgent",
                "description": "Test agent for ephemeral stream",
                "version": "1.0",
                "runbook": "You are a helpful assistant.",
                "agent_architecture": {
                    "name": "agent_platform.architectures.default",
                    "version": "1.0.0",
                },
                "platform_configs": [
                    {
                        "kind": "openai",
                        "openai_api_key": openai_api_key,
                    }
                ],
                "action_packages": [],
                "mcp_servers": [],
                "question_groups": [],
                "observability_configs": [],
                "mode": "conversational",
                "extra": {},
                "advanced_config": {},
                "metadata": {},
                "public": True,
            },
            "messages": [],  # Start with empty messages for simplicity
        }

        await ws.send(json.dumps(payload))

        # Track received events
        events = []
        agent_ready_received = False
        agent_finished_received = False

        # Read all messages until agent_finished
        while True:
            try:
                msg = await ws.recv()
                data = json.loads(msg)
                events.append(data)

                event_type = data.get("event_type")

                if event_type == "agent_ready":
                    agent_ready_received = True
                elif event_type == "agent_finished":
                    agent_finished_received = True
                    break
                elif event_type == "agent_error":
                    error_msg = data.get("error_message", "Unknown error")
                    pytest.fail(f"Agent error: {error_msg}")

            except websockets.exceptions.ConnectionClosed:
                break

        # Verify basic ephemeral stream flow with OpenAI configuration
        assert agent_ready_received, "Should receive agent_ready event"
        assert agent_finished_received, "Should receive agent_finished event"
        assert len(events) >= 2, "Should receive at least agent_ready and agent_finished"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_ephemeral_stream_invalid_payload(base_url_agent_server):
    """Test ephemeral stream with invalid agent payload."""
    ws_url = base_url_agent_server.replace("http://", "ws://") + "/api/v2/runs/ephemeral/stream"

    async with websockets.connect(ws_url) as ws:
        # Send invalid payload (missing required agent fields)
        invalid_payload = {
            "agent": {
                "name": "InvalidAgent",
                # Missing required fields like description, version, etc.
            },
            "messages": [],
        }

        await ws.send(json.dumps(invalid_payload))

        # Connection should be closed due to invalid payload
        with pytest.raises(websockets.exceptions.ConnectionClosed) as exc_info:
            await ws.recv()

        # Verify close code indicates unsupported data or policy violation
        close_code = (
            getattr(exc_info.value.rcvd, "code", None)
            if hasattr(exc_info.value, "rcvd") and exc_info.value.rcvd
            else getattr(exc_info.value, "code", None)
        )
        assert close_code in {1003, 1008}  # WS_1003_UNSUPPORTED_DATA or WS_1008_POLICY_VIOLATION


if __name__ == "__main__":
    pytest.main([__file__])
