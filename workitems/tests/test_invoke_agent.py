import asyncio
from uuid import uuid4

import pytest

from agent_platform.core.payloads.initiate_stream import InitiateStreamPayload
from agent_platform.core.thread.base import ThreadMessage
from agent_platform.core.thread.content.text import ThreadTextContent
from agent_platform.workitems.agents.client import HttpAgentClient


@pytest.mark.integration
class TestInvokeAgent:
    """Test the ability to invoke an agent and wait for completion."""

    @pytest.mark.asyncio
    async def test_invoke_agent(
        self,
        require_docker,
        agent_server_url: str,
        agent_id: str,
    ):
        """Test async invoke of an agent generates a complete run."""
        client = HttpAgentClient(agent_server_url)

        # 1. Create
        invoke_payload = InitiateStreamPayload(
            agent_id=agent_id,
            thread_id=str(uuid4()),
            messages=[
                ThreadMessage(
                    role="user",
                    content=[ThreadTextContent(text="tell me a joke")],
                )
            ],
        )

        invoke_resp = await client.invoke_agent(agent_id, invoke_payload)

        assert invoke_resp.run_id, "Expected a run ID"
        assert invoke_resp.status, "Expected a run status"

        async def completed_run(run_id: str) -> bool:
            while True:
                run_status_resp = await client.get_run_status(run_id)
                # Run not found?
                if not run_status_resp:
                    await asyncio.sleep(1)
                    continue

                # Check for completed
                if run_status_resp.status != "completed":
                    await asyncio.sleep(1)
                    continue

                # Success!
                return True

        done, pending = await asyncio.wait(
            [asyncio.create_task(completed_run(invoke_resp.run_id))],
            timeout=30,  # 30s
            return_when=asyncio.ALL_COMPLETED,
        )

        if pending:
            pytest.fail(f"Run {invoke_resp.run_id} did not complete within 30 seconds")

        # 3. Get the run
        run_status_resp = await client.get_run_status(invoke_resp.run_id)
        assert run_status_resp, "Expected a run status response"
        assert run_status_resp.run_id == invoke_resp.run_id, "wrong run_id"
        assert run_status_resp.status == "completed", "Expected a completed run"

        # 4. Get the messages from the (now proven) completed run
        messages = await client.get_messages(invoke_resp.run_id)
        assert messages, "Expected messages"
        assert len(messages) > 0, "Expected at least one message"
        message = messages[0]
        assert message.role == "agent", "Expected an agent message"
        assert message.complete is True, "Expected a complete message"
        text_contents = [c for c in message.content if isinstance(c, ThreadTextContent)]
        assert len(text_contents) > 0, "Expected a text content"
        assert len(text_contents[0].text) > 0, "Expected a non-empty text reply"
        assert text_contents[0].complete is True, "Expected a complete text reply"
