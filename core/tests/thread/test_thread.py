from agent_platform.core.thread.base import ThreadMessage
from agent_platform.core.thread.content.text import ThreadTextContent
from agent_platform.core.thread.thread import Thread


class TestThread:
    def test_add_message_updates_updated_at(self):
        import time

        thread = Thread(user_id="dummy", agent_id="dummy", name="test-thread")
        old_updated_at = thread.updated_at
        time.sleep(0.3)  # Make sure that the updated_at is different
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

    def test_model_dump_includes_all_messages(self):
        thread = Thread(user_id="dummy", agent_id="dummy", name="test-thread")
        msg1 = ThreadMessage(content=[ThreadTextContent(text="Msg1")], role="user")
        msg2 = ThreadMessage(content=[ThreadTextContent(text="Msg2")], role="agent")
        thread.add_message(msg1)
        thread.add_message(msg2)

        data = thread.model_dump()
        assert len(data["messages"]) == 2
        assert data["messages"][0]["content"][0]["text"] == "Msg1"
        assert data["messages"][1]["content"][0]["text"] == "Msg2"

    def test_get_last_n_messages_empty_thread(self):
        thread = Thread(user_id="dummy", agent_id="dummy", name="test-thread")
        assert thread.get_last_n_messages(1) == []

    def test_get_last_n_messages_single_message(self):
        thread = Thread(user_id="dummy", agent_id="dummy", name="test-thread")
        msg = ThreadMessage(content=[ThreadTextContent(text="Msg1")], role="user")
        thread.add_message(msg)
        assert thread.get_last_n_messages(1) == [msg]

    def test_get_last_n_messages_multiple_messages(self):
        thread = Thread(user_id="dummy", agent_id="dummy", name="test-thread")
        msg1 = ThreadMessage(content=[ThreadTextContent(text="Msg1")], role="user")
        msg2 = ThreadMessage(content=[ThreadTextContent(text="Msg2")], role="agent")
        msg3 = ThreadMessage(content=[ThreadTextContent(text="Msg3")], role="user")
        msg4 = ThreadMessage(content=[ThreadTextContent(text="Msg4")], role="agent")
        thread.add_message(msg1)
        thread.add_message(msg2)
        thread.add_message(msg3)
        thread.add_message(msg4)
        assert thread.get_last_n_messages(2) == [msg3, msg4]

    def test_get_last_n_turns_empty_thread(self):
        thread = Thread(user_id="dummy", agent_id="dummy", name="test-thread")
        assert thread.get_last_n_message_turns(1) == []

    def test_get_last_n_turns_single_turn(self):
        thread = Thread(user_id="dummy", agent_id="dummy", name="test-thread")
        msg1 = ThreadMessage(content=[ThreadTextContent(text="Msg1")], role="user")
        msg2 = ThreadMessage(content=[ThreadTextContent(text="Msg2")], role="user")
        msg3 = ThreadMessage(content=[ThreadTextContent(text="Msg3")], role="agent")
        msg4 = ThreadMessage(content=[ThreadTextContent(text="Msg4")], role="agent")
        thread.add_message(msg1)
        thread.add_message(msg2)
        thread.add_message(msg3)
        thread.add_message(msg4)
        assert thread.get_last_n_message_turns(1) == [msg1, msg2, msg3, msg4]

    def test_get_last_n_turns_multiple_turns(self):
        thread = Thread(user_id="dummy", agent_id="dummy", name="test-thread")
        msg1 = ThreadMessage(content=[ThreadTextContent(text="Msg1")], role="user")
        msg2 = ThreadMessage(content=[ThreadTextContent(text="Msg2")], role="user")
        msg3 = ThreadMessage(content=[ThreadTextContent(text="Msg3")], role="agent")
        msg4 = ThreadMessage(content=[ThreadTextContent(text="Msg4")], role="user")
        msg5 = ThreadMessage(content=[ThreadTextContent(text="Msg5")], role="agent")
        msg6 = ThreadMessage(content=[ThreadTextContent(text="Msg6")], role="user")
        msg7 = ThreadMessage(content=[ThreadTextContent(text="Msg7")], role="agent")
        msg8 = ThreadMessage(content=[ThreadTextContent(text="Msg8")], role="agent")
        thread.add_message(msg1)
        thread.add_message(msg2)
        thread.add_message(msg3)
        thread.add_message(msg4)
        thread.add_message(msg5)
        thread.add_message(msg6)
        thread.add_message(msg7)
        thread.add_message(msg8)
        assert thread.get_last_n_message_turns(2) == [msg4, msg5, msg6, msg7, msg8]
        assert thread.get_last_n_message_turns(1) == [msg6, msg7, msg8]
        assert thread.get_last_n_message_turns(0) == []
        assert thread.get_last_n_message_turns(-1) == []
        assert thread.get_last_n_message_turns(10) == [
            msg1,
            msg2,
            msg3,
            msg4,
            msg5,
            msg6,
            msg7,
            msg8,
        ]
