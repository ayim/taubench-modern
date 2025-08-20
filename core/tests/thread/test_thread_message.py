import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from agent_platform.core.kernel_interfaces.thread_state import (
    ThreadMessageWithThreadState,
)
from agent_platform.core.streaming import StreamingError
from agent_platform.core.thread.base import ThreadMessage
from agent_platform.core.thread.content import (
    ThreadQuickActionContent,
    ThreadQuickActionsContent,
    ThreadTextContent,
    ThreadThoughtContent,
    ThreadVegaChartContent,
)
from agent_platform.core.thread.messages import ThreadAgentMessage, ThreadUserMessage


class TestThreadTextContent:
    def test_create_valid_text_content(self):
        content = ThreadTextContent(text="Hello, world!")
        assert content.kind == "text"
        assert content.text == "Hello, world!"
        # as_text_content should return self
        assert content.as_text_content() == content.text


class TestThreadQuickActionsContent:
    def test_create_valid_quick_actions(self):
        actions = [
            ThreadQuickActionContent(label="Action 1", value="value1"),
            ThreadQuickActionContent(label="Action 2", value="value2", icon="info"),
        ]
        content = ThreadQuickActionsContent(actions=actions)
        assert content.kind == "quick_actions"
        assert len(content.actions) == len(actions)
        assert content.actions[0].label == actions[0].label
        assert content.actions[0].value == actions[0].value

    def test_empty_actions_raises(self):
        with pytest.raises(ValueError, match="Actions value cannot be empty"):
            ThreadQuickActionsContent(actions=[])

    def test_duplicate_labels_raises(self):
        actions = [
            ThreadQuickActionContent(label="Duplicate", value="val1"),
            ThreadQuickActionContent(label="Duplicate", value="val2"),
        ]
        with pytest.raises(ValueError, match="All actions must have unique labels"):
            ThreadQuickActionsContent(actions=actions)

    def test_as_text_content(self):
        actions = [
            ThreadQuickActionContent(label="A1", value="val1"),
            ThreadQuickActionContent(label="A2", value="val2", icon="info"),
        ]
        content = ThreadQuickActionsContent(actions=actions)
        text_version = content.as_text_content()
        assert isinstance(text_version, str)
        assert "<choice" in text_version
        # Check that both labels appear
        assert "A1" in text_version
        assert "A2" in text_version
        # Check that the second includes icon data
        assert 'data-icon="info"' in text_version


class TestThreadVegaChartContent:
    def test_create_valid_vega_chart(self):
        spec = {
            "$schema": "https://vega.github.io/schema/vega/v5.json",
            "width": 400,
            "height": 200,
            "data": [{"name": "table", "values": [1, 2, 3]}],
        }
        content = ThreadVegaChartContent(
            chart_spec_raw=json.dumps(spec, indent=2),
            sub_type="vega",
        )
        assert content.kind == "vega_chart"
        assert content.sub_type == "vega"
        assert content.chart_spec == spec

    def test_missing_schema_is_auto_inserted(self):
        spec = {
            "width": 400,
            "height": 200,
            "data": [{"name": "table", "values": [1, 2, 3]}],
        }
        content = ThreadVegaChartContent(
            chart_spec_raw=json.dumps(spec),
            sub_type="vega-lite",
        )
        # The class auto-inserts a $schema key for us
        assert content.chart_spec["$schema"].endswith("vega-lite/v5.json")

    def test_empty_raw_raises(self):
        with pytest.raises(ValueError, match="Chart spec value cannot be empty"):
            ThreadVegaChartContent(chart_spec_raw="")

    def test_invalid_json_raises(self):
        with pytest.raises(ValueError, match="must be a valid JSON string"):
            ThreadVegaChartContent(chart_spec_raw="not valid json")

    def test_schema_type_mismatch(self):
        # sub_type=vega but we have a vega-lite schema
        spec = {
            "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
            "width": 400,
        }
        with pytest.raises(ValueError, match="Schema indicates Vega-Lite"):
            ThreadVegaChartContent(chart_spec_raw=json.dumps(spec), sub_type="vega")

    def test_as_text_content(self):
        spec = {
            "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
            "width": 400,
            "height": 300,
        }
        content = ThreadVegaChartContent(
            chart_spec_raw=json.dumps(spec),
            sub_type="vega-lite",
        )
        txt = content.as_text_content()
        assert isinstance(txt, str)
        assert "vega-lite" in txt
        # The JSON spec should appear in the code block
        assert '"width": 400' in txt

    def test_non_string_chart_spec_raises(self):
        with pytest.raises(ValueError, match="Chart spec value must be a string"):
            ThreadVegaChartContent(
                chart_spec_raw={
                    "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
                    "width": 400,
                    "height": 300,
                },  # type: ignore (invalid on purpose)
            )


@pytest.mark.asyncio
class TestThreadMessageBase:
    async def test_create_thread_message(self):
        msg = ThreadMessage(
            role="user",
            content=[ThreadTextContent(text="User says hi!")],
            created_at=datetime(2021, 1, 1, tzinfo=UTC),
            updated_at=datetime(2021, 1, 1, tzinfo=UTC),
        )
        assert msg.role == "user"
        assert msg.content[0].kind == "text"
        assert msg.created_at == datetime(2021, 1, 1, tzinfo=UTC)

    async def test_append_content_appends_existing_content(self):
        # Mock out the thread state
        mock_thread_state = AsyncMock()
        msg = ThreadMessageWithThreadState(
            ThreadMessage(
                role="agent",
                content=[ThreadTextContent(text="Hello")],
            ),
            mock_thread_state,
        )
        msg.append_content(" world!")
        await msg.stream_delta()
        # Check that the text was appended
        assert isinstance(msg.message.content[0], ThreadTextContent)
        assert msg.message.content[0].text == "Hello world!"
        # Check that stream_message_delta was called with self
        mock_thread_state.stream_message_delta.assert_awaited_once_with(msg.message)

    async def test_append_content_creates_new_text_block_if_none_exist(self):
        msg = ThreadMessageWithThreadState(
            ThreadMessage(role="agent", content=[]),
            AsyncMock(),
        )
        msg.append_content("New text here")
        assert len(msg.message.content) == 1
        assert isinstance(msg.message.content[0], ThreadTextContent)
        assert msg.message.content[0].text == "New text here"

    async def test_append_content_raises_if_committed(self):
        msg = ThreadMessageWithThreadState(
            ThreadMessage(
                role="user",
                content=[ThreadTextContent(text="Can't edit me")],
                commited=True,
            ),
            AsyncMock(),
        )
        with pytest.raises(
            ValueError,
            match="Cannot add content to a committed message",
        ):
            msg.append_content(" some more text")

    async def test_commit_calls_thread_state_commit_message(self):
        msg = ThreadMessageWithThreadState(
            ThreadMessage(role="user", content=[], commited=False),
            AsyncMock(),
        )
        await msg.commit()
        assert msg.message.commited is True

    def test_model_dump_includes_commited_field(self):
        """Test that model_dump includes the commited field."""
        message = ThreadMessage(
            role="user",
            content=[ThreadTextContent(text="Test message")],
            commited=True,
        )

        dumped = message.model_dump()

        # Verify that commited field is present in the output
        assert "commited" in dumped
        assert dumped["commited"] is True

        # Test with commited=False
        message.commited = False
        dumped = message.model_dump()
        assert "commited" in dumped
        assert dumped["commited"] is False


class TestThreadUserMessage:
    def test_create_user_message(self):
        user_msg = ThreadUserMessage(content=[ThreadTextContent(text="Hi!")])
        assert user_msg.role == "user"
        assert isinstance(user_msg.content[0], ThreadTextContent)
        assert user_msg.content[0].text == "Hi!"
        # By default, freshly created messages are not complete
        assert user_msg.complete is False

    def test_create_message_explicitly_complete(self):
        user_msg = ThreadUserMessage(
            content=[ThreadTextContent(text="Hi!")],
            complete=True,
        )
        assert user_msg.complete is True
        assert all(c.complete for c in user_msg.content)

    def test_role_is_forced_literal(self):
        with pytest.raises(ValueError, match="Invalid value for 'role'"):
            ThreadUserMessage(content=[], role="not_user")  # type: ignore


@pytest.mark.asyncio
class TestThreadAgentMessage:
    async def test_create_agent_message(self):
        agent_msg = ThreadAgentMessage(content=[ThreadTextContent(text="Hello user!")])
        assert agent_msg.role == "agent"
        assert isinstance(agent_msg.content[0], ThreadTextContent)
        assert agent_msg.content[0].text == "Hello user!"
        assert agent_msg.complete is False

    def test_create_message_explicitly_complete(self):
        agent_msg = ThreadAgentMessage(
            content=[ThreadTextContent(text="Hi!")],
            complete=True,
        )
        assert agent_msg.complete is True
        assert all(c.complete for c in agent_msg.content)

    async def test_append_thought_appends_by_default(self):
        mock_thread_state = AsyncMock()
        agent_msg = ThreadMessageWithThreadState(
            ThreadAgentMessage(content=[ThreadTextContent(text="public content")]),
            mock_thread_state,
        )
        # Start with one thought
        agent_msg.new_thought("Initial thought.")
        agent_msg.append_thought(" Appended more stuff")
        await agent_msg.stream_delta()
        assert len(agent_msg.message.content) == 2
        assert isinstance(agent_msg.message.content[-1], ThreadThoughtContent)
        assert agent_msg.message.content[-1].thought == "Initial thought. Appended more stuff"
        mock_thread_state.stream_message_delta.assert_awaited_once_with(
            agent_msg.message,
        )

    async def test_new_thought_creates_new_thought(self):
        mock_thread_state = AsyncMock()
        agent_msg = ThreadMessageWithThreadState(
            ThreadAgentMessage(content=[ThreadTextContent(text="Hello")]),
            mock_thread_state,
        )
        agent_msg.new_thought("First thought")
        assert len(agent_msg.message.content) == 2

        agent_msg.new_thought("Second thought separate")
        assert len(agent_msg.message.content) == 3
        # The second is an entirely new text block
        assert isinstance(agent_msg.message.content[-1], ThreadThoughtContent)
        assert agent_msg.message.content[-1].thought == "Second thought separate"

    async def test_complete_marked_when_committed(self):
        agent_msg = ThreadMessageWithThreadState(
            ThreadAgentMessage(content=[ThreadTextContent(text="Hello")]),
            AsyncMock(),
        )
        await agent_msg.commit()
        assert agent_msg.message.complete is True
        assert all(c.complete for c in agent_msg.message.content)

    async def test_append_thought_raises_if_committed(self):
        agent_msg = ThreadMessageWithThreadState(
            ThreadAgentMessage(content=[ThreadTextContent(text="xyz")], commited=True),
            AsyncMock(),
        )
        with pytest.raises(
            ValueError,
            match="Cannot add content to a committed message",
        ):
            agent_msg.append_thought("some new thought")


@pytest.mark.asyncio
class TestThreadMessageSoftCommit:
    """Test soft commit functionality for handling ws conn loss during tool execution."""

    async def test_soft_commit_preserves_editability(self):
        """Test that soft_commit saves to storage but keeps message editable."""

        mock_thread_state = AsyncMock()
        mock_thread_state.kernel = MagicMock()
        mock_thread_state.kernel.ctx.increment_counter = MagicMock()

        message = ThreadAgentMessage(
            content=[ThreadTextContent(text="Initial content")],
            commited=False,
            complete=False,
        )

        msg_with_state = ThreadMessageWithThreadState(message, mock_thread_state)
        msg_with_state.append_content("Tool is running...")

        await msg_with_state.soft_commit()

        mock_thread_state.commit_message.assert_called_once_with(
            message, ignore_websocket_errors=True
        )

        assert message.complete is False
        assert message.commited is False

        msg_with_state.append_content(" Tool completed!")

        await msg_with_state.commit(ignore_websocket_errors=True)

        assert message.commited is True
        assert message.complete is True

        text_content = next(
            content for content in message.content if isinstance(content, ThreadTextContent)
        )
        assert text_content.text.endswith("Tool completed!")

    async def test_commit_ignoring_websocket_errors(self):
        """Test that commit with ignore_websocket_errors=True works when websocket fails."""

        mock_thread_state = AsyncMock()
        mock_thread_state.kernel = MagicMock()
        mock_thread_state.kernel.ctx.increment_counter = MagicMock()

        mock_thread_state.stream_message_delta = AsyncMock(
            side_effect=StreamingError("WebSocket connection lost")
        )

        message = ThreadAgentMessage(
            content=[ThreadTextContent(text="Long running tool result")],
            commited=False,
            complete=False,
        )

        msg_with_state = ThreadMessageWithThreadState(message, mock_thread_state)

        await msg_with_state.commit(ignore_websocket_errors=True)

        mock_thread_state.commit_message.assert_called_once_with(
            message, ignore_websocket_errors=True
        )

        assert message.commited is True
        assert message.complete is True
