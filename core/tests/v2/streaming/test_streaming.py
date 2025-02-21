# File: tests/test_streaming.py

from datetime import datetime

import pytest

# Import the classes/functions to be tested
# Assuming you have a structure like: agent_server_types_v2/streaming/...
from agent_server_types_v2.delta import GenericDelta
from agent_server_types_v2.streaming.compute_delta import compute_message_delta
from agent_server_types_v2.streaming.delta import (
    StreamingDelta,
    StreamingDeltaMessageBegin,
    StreamingDeltaMessageContent,
    StreamingDeltaMessageEnd,
)
from agent_server_types_v2.streaming.error import StreamingError

########################################
# Mock classes and helpers
########################################


class MockThreadMessage:
    """
    A mock stand-in for ThreadMessage with the minimum attributes needed
    to test compute_message_delta. It provides a .to_json_dict() and a .uid.
    """

    def __init__(self, message_id, **kwargs):
        self.message_id = message_id
        self.data = kwargs

    def to_json_dict(self):
        return {
            "message_id": self.message_id,
            **self.data,
        }


########################################
# Tests for compute_message_delta
########################################


def test_compute_message_delta_no_old():
    """
    If no old message, we expect individual add operations for each field
    in the new message.
    """
    new_msg = MockThreadMessage("msg-1", text="Hello", count=1)
    deltas = compute_message_delta(None, new_msg, sequence_number=0)  # old is None

    # Because old was None => old dict is {}
    # The new is {"message_id": "msg-1", "text": "Hello", "count": 1}
    # We expect individual add operations for each field

    assert len(deltas) == 3
    # Sort deltas by path to make testing deterministic
    sorted_deltas = sorted(deltas, key=lambda d: d.delta.path)

    # Check first delta (count)
    assert isinstance(sorted_deltas[0], StreamingDeltaMessageContent)
    assert sorted_deltas[0].message_id == "msg-1"
    assert sorted_deltas[0].delta.op == "add"
    assert sorted_deltas[0].delta.path == "/count"
    assert sorted_deltas[0].delta.value == 1

    # Check second delta (message_id)
    assert isinstance(sorted_deltas[1], StreamingDeltaMessageContent)
    assert sorted_deltas[1].message_id == "msg-1"
    assert sorted_deltas[1].delta.op == "add"
    assert sorted_deltas[1].delta.path == "/message_id"
    assert sorted_deltas[1].delta.value == "msg-1"

    # Check third delta (text)
    assert isinstance(sorted_deltas[2], StreamingDeltaMessageContent)
    assert sorted_deltas[2].message_id == "msg-1"
    assert sorted_deltas[2].delta.op == "add"
    assert sorted_deltas[2].delta.path == "/text"
    assert sorted_deltas[2].delta.value == "Hello"

    # The sequence numbers should be 0, 1, and 2
    assert set(d.sequence_number for d in sorted_deltas) == {0, 1, 2}


def test_compute_message_delta_with_old():
    """
    If we have an old message, only the changed fields should appear in the delta.
    """
    old_msg = MockThreadMessage("msg-1", text="Hello", count=10)
    new_msg = MockThreadMessage("msg-1", text="Hello World", count=12)

    deltas = compute_message_delta(old_msg, new_msg, sequence_number=2)
    # We expect two deltas:
    #   1) concat_string at /text with " World"
    #   2) inc at /count with 2

    assert len(deltas) == 2
    # Sort them to check easily
    sorted_ops = sorted(deltas, key=lambda d: d.delta.op)

    assert sorted_ops[0].delta.op == "concat_string"
    assert sorted_ops[0].delta.path == "/text"
    assert sorted_ops[0].delta.value == " World"
    assert sorted_ops[1].delta.op == "inc"
    assert sorted_ops[1].delta.path == "/count"
    assert sorted_ops[1].delta.value == 2

    # The ops may be in any order, but the sequence numbers should be 2 and 3.
    assert set(d.sequence_number for d in sorted_ops) == {2, 3}


########################################
# Tests for StreamingDelta classes
########################################


def test_streaming_delta_base():
    delta = StreamingDelta(
        sequence_number=1,
        message_id="msg-123",
        timestamp=datetime(2025, 1, 24, 12, 0, 0),
        event_type="message_metadata",
    )
    d = delta.to_json_dict()
    assert d["sequence_number"] == 1
    assert d["message_id"] == "msg-123"
    assert d["timestamp"] == "2025-01-24T12:00:00"
    assert d["event_type"] == "message_metadata"


def test_streaming_delta_message_content():
    delta = GenericDelta(op="replace", path="/somepath", value="newval")
    msg_content = StreamingDeltaMessageContent(
        sequence_number=1,
        message_id="msg-123",
        timestamp=datetime(2025, 1, 24, 13, 0, 0),
        delta=delta,
    )
    d = msg_content.to_json_dict()
    assert d["sequence_number"] == 1
    assert d["message_id"] == "msg-123"
    assert d["timestamp"] == "2025-01-24T13:00:00"
    assert d["event_type"] == "message_content"
    assert d["delta"]["op"] == "replace"
    assert d["delta"]["path"] == "/somepath"
    assert d["delta"]["value"] == "newval"


def test_streaming_delta_message_begin():
    begin_event = StreamingDeltaMessageBegin(
        sequence_number=1,
        message_id="msg-001",
        thread_id="thread-123",
        agent_id="agent-456",
        timestamp=datetime(2025, 1, 24, 14, 0, 0),
        data={"initial": "data"},
    )
    d = begin_event.to_json_dict()
    assert d["sequence_number"] == 1
    assert d["message_id"] == "msg-001"
    assert d["thread_id"] == "thread-123"
    assert d["agent_id"] == "agent-456"
    assert d["timestamp"] == "2025-01-24T14:00:00"
    assert d["event_type"] == "message_begin"
    assert d["data"] == {"initial": "data"}
    # channel is forced to "events", but not in the dictionary unless you add it.
    # If you want it, you can test it:
    assert begin_event.channel == "events"


def test_streaming_delta_message_end():
    end_event = StreamingDeltaMessageEnd(
        sequence_number=1,
        message_id="msg-002",
        thread_id="thread-123",
        agent_id="agent-456",
        timestamp=datetime(2025, 1, 24, 15, 0, 0),
        data={"final": "data"},
    )
    d = end_event.to_json_dict()
    assert d["sequence_number"] == 1
    assert d["message_id"] == "msg-002"
    assert d["thread_id"] == "thread-123"
    assert d["agent_id"] == "agent-456"
    assert d["timestamp"] == "2025-01-24T15:00:00"
    assert d["event_type"] == "message_end"
    assert d["data"] == {"final": "data"}
    assert end_event.channel == "events"


########################################
# Tests for StreamingError
########################################


def test_streaming_error_no_delta():
    with pytest.raises(StreamingError) as exc_info:
        raise StreamingError("Something went wrong!")

    assert str(exc_info.value) == "Something went wrong!"
    assert exc_info.value.delta_object is None


def test_streaming_error_with_delta():
    some_delta = StreamingDelta(
        sequence_number=1,
        message_id="msg-xyz",
        timestamp=datetime.now(),
        event_type="message_end",
    )

    with pytest.raises(StreamingError) as exc_info:
        raise StreamingError("Failure with delta", delta_object=some_delta)

    assert str(exc_info.value) == "Failure with delta"
    assert exc_info.value.delta_object is some_delta
