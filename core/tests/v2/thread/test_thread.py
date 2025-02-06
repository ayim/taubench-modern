from agent_server_types_v2.thread.base import ThreadMessage
from agent_server_types_v2.thread.content.text import ThreadTextContent
from agent_server_types_v2.thread.thread import Thread


class TestThread:
    def test_add_message_updates_updated_at(self):
        thread = Thread(user_id="dummy", agent_id="dummy", name="test-thread")
        old_updated_at = thread.updated_at
        msg = ThreadMessage(
            content=[ThreadTextContent(text="Hello")],
            role="user",
        )
        thread.add_message(msg)
        assert thread.updated_at > old_updated_at

    def test_find_message_by_uid(self):
        thread = Thread(user_id="dummy", agent_id="dummy", name="test-thread")
        msg = ThreadMessage(
            content=[ThreadTextContent(text="one")],
            role="user",
        )
        thread.add_message(msg)
        found = thread.find_message(message_id=msg.message_id)
        assert found is not None
        assert found.message_id == msg.message_id

    def test_find_message_returns_none_if_not_found(self):
        thread = Thread(user_id="dummy", agent_id="dummy", name="test-thread")
        found = thread.find_message(message_id="non-existent-message-id")
        assert found is None

    def test_to_json_dict_includes_all_messages(self):
        thread = Thread(user_id="dummy", agent_id="dummy", name="test-thread")
        msg1 = ThreadMessage(content=[ThreadTextContent(text="Msg1")], role="user")
        msg2 = ThreadMessage(content=[ThreadTextContent(text="Msg2")], role="agent")
        thread.add_message(msg1)
        thread.add_message(msg2)

        data = thread.to_json_dict()
        assert len(data["messages"]) == 2
        assert data["messages"][0]["content"][0]["text"] == "Msg1"
        assert data["messages"][1]["content"][0]["text"] == "Msg2"
