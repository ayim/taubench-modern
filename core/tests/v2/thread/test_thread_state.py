from unittest.mock import AsyncMock, patch

import pytest

from agent_server_types_v2.kernel_interfaces.thread_state import ThreadStateInterface
from agent_server_types_v2.streaming import StreamingDelta, StreamingError
from agent_server_types_v2.thread.content.text import ThreadTextContent
from agent_server_types_v2.thread.messages import ThreadAgentMessage, ThreadMessage


class ThreadStateTestImpl(ThreadStateInterface):
    def __init__(self):
        super().__init__(thread_id="test-thread-123", agent_id="my-testing-agent-456")

    async def _send_delta_event(self, delta_object: StreamingDelta) -> None:
        pass  # we can spy on calls or do nothing

    async def _commit_message_to_storage(self, message: ThreadMessage) -> None:
        pass

@pytest.mark.asyncio
class TestThreadState:
    async def test_stream_message_delta_for_new_message(self):
        ts = ThreadStateTestImpl()
        msg = ThreadAgentMessage(content=[ThreadTextContent(text="hello")])
        with patch.object(ts, '_send_delta_event', new_callable=AsyncMock) as mock_send:
            await ts.stream_message_delta(msg)
            assert mock_send.await_count == 1  # one delta event for brand new message

    async def test_stream_message_delta_for_updated_message(self):
        ts = ThreadStateTestImpl()
        msg = ThreadAgentMessage(content=[ThreadTextContent(text="hello")])
        await ts.stream_message_delta(msg)
        # Now update the content
        msg.content[0] = ThreadTextContent(text="hello updated")
        with patch.object(ts, '_send_delta_event', new_callable=AsyncMock) as mock_send:
            await ts.stream_message_delta(msg)
            assert mock_send.await_count >= 1  # at least one delta event for updated message

    async def test_stream_message_delta_raises_streamingerror_on_exception(self):
        ts = ThreadStateTestImpl()
        msg = ThreadAgentMessage(content=[ThreadTextContent(text="fail me")])
        with patch.object(ts, '_send_delta_event', new_callable=AsyncMock) as mock_send:
            mock_send.side_effect = Exception("Network issue")
            with pytest.raises(StreamingError, match="Failed to send delta"):
                await ts.stream_message_delta(msg)

    async def test_commit_message_abstract(self):
        """Tests the commit_message is an abstract method; 
        we verify if our subclass must implement it."""
        ts = ThreadStateTestImpl()
        msg = ThreadAgentMessage(content=[])
        # This should do nothing since we override it with pass in the subclass
        await ts.commit_message(msg)  # no error if properly overridden

    async def test_send_delta_event_abstract(self):
        """Tests the _send_delta_event is an abstract method."""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            # We try to instantiate the ABC directly, should fail
            _ = ThreadStateInterface()
