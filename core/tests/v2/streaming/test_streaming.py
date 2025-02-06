# File: tests/test_streaming.py

from datetime import datetime

import pytest

from agent_server_types_v2.streaming.compute_delta import compute_message_delta
from agent_server_types_v2.streaming.delta import (
    StreamingDelta,
    StreamingDeltaMessageBegin,
    StreamingDeltaMessageContent,
    StreamingDeltaMessageEnd,
)
from agent_server_types_v2.streaming.error import StreamingError

# Import the classes/functions to be tested
# Assuming you have a structure like: agent_server_types_v2/streaming/...
from agent_server_types_v2.streaming.generic.compute_delta import compute_generic_delta
from agent_server_types_v2.streaming.generic.delta import GenericDelta

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
# Tests for GenericDelta
########################################

def test_generic_delta_init_and_dict():
    """
    Basic test to ensure GenericDelta can be constructed and
    converted to a JSON-compatible dictionary.
    """
    delta = GenericDelta(op="replace", path="/foo/bar", value="new_value")
    assert delta.op == "replace"
    assert delta.path == "/foo/bar"
    assert delta.value == "new_value"

    as_dict = delta.to_json_dict()
    assert as_dict == {
        "op": "replace",
        "path": "/foo/bar",
        "value": "new_value",
    }


########################################
# Tests for compute_generic_delta
########################################

@pytest.mark.parametrize(
    ("old_val", "new_val", "expected_ops"),
    [
        # 1) Same string => no delta
        ("hello", "hello", []),
        # 2) String replaced entirely
        ("hello", "world", [GenericDelta(op="replace", path="", value="world")]),
        # 3) String extended
        ("hello", "hello world", [GenericDelta(op="concat_string", path="", value=" world")]),
        # 4) Same int => no delta
        (42, 42, []),
        # 5) int new > old => inc
        (10, 15, [GenericDelta(op="inc", path="", value=5)]),
        # 6) int new < old => replace
        (15, 10, [GenericDelta(op="replace", path="", value=10)]),
        # 7) Different types => replace
        ("123", 123, [GenericDelta(op="replace", path="", value=123)]),
        # 8) None to something => replace
        (None, True, [GenericDelta(op="replace", path="", value=True)]),
        # 9) Lists are same
        ([1, 2, 3], [1, 2, 3], []),
        # 10) List appended
        ([1, 2, 3], [1, 2, 3, 4, 5], [GenericDelta(op="append_array", path="", value=[4, 5])]),
        # 11) List last item is a string extended
        (["hello"], ["hello world"], [GenericDelta(op="concat_string", path="/0", value=" world")]),
        # 12) Dict: same
        ({"a": 1}, {"a": 1}, []),
        # 13) Dict: remove key
        ({"a": 1, "b": 2}, {"a": 1}, [GenericDelta(op="remove", path="/b", value=None)]),
        # 14) Dict: add key
        ({"a": 1}, {"a": 1, "b": 2}, [GenericDelta(op="merge", path="", value={"b": 2})]),
        # 15) Dict: changed key
        (
            {"a": 1},
            {"a": 2},
            [GenericDelta(op="inc", path="/a", value=1)],  # since int changed from 1 -> 2
        ),
    ],
)
def test_compute_generic_delta(old_val, new_val, expected_ops):
    ops = compute_generic_delta(old_val, new_val, path="")
    # Compare lists of GenericDelta objects
    # Because we can't directly compare dataclasses with lists unless you 
    # explicitly handle them, do a length and then field-by-field check:
    assert len(ops) == len(expected_ops), f"Expected {expected_ops} got {ops}"
    for o, e in zip(ops, expected_ops, strict=False):
        assert o.op == e.op
        assert o.path == e.path
        assert o.value == e.value


def test_compute_generic_delta_nested_lists_and_dicts():
    """
    Tests a more complex structure with nested lists and dicts.
    """
    old = {
        "name": "Alice",
        "scores": [10, 20],
        "details": {
            "hobbies": ["reading"],
        },
    }
    new = {
        "name": "Alice B",           # string extended
        "scores": [10, 20, 30],      # appended
        "details": {
            "hobbies": ["reading", "chess"],  # appended
            "age": 30,                         # new key
        },
    }

    ops = compute_generic_delta(old, new)
    # We expect:
    # 1) "name" => "concat_string" with " B"
    # 2) "scores" => append_array with [30]
    # 3) "details/hobbies" => append_array with ["chess"]
    # 4) "details" => merge with {"age": 30}
    
    # Let's break down the expected ops:
    expected = [
        GenericDelta(op="concat_string", path="/name", value=" B"),
        GenericDelta(op="append_array", path="/scores", value=[30]),
        GenericDelta(op="append_array", path="/details/hobbies", value=["chess"]),
        GenericDelta(op="merge", path="/details", value={"age": 30}),
    ]

    # Sort them on ops and path, before zip
    expected = sorted(expected, key=lambda x: (x.op, x.path))
    ops = sorted(ops, key=lambda x: (x.op, x.path))

    assert len(ops) == len(expected), f"Got ops: {ops}"
    for actual, exp in zip(ops, expected, strict=False):
        assert actual.op == exp.op
        assert actual.path == exp.path
        assert actual.value == exp.value


########################################
# Tests for compute_message_delta
########################################

def test_compute_message_delta_no_old():
    """
    If no old message, we expect a full replace of all fields in new message (or multiple field-level ops).
    """
    new_msg = MockThreadMessage("msg-1", text="Hello", count=1)
    deltas = compute_message_delta(None, new_msg, sequence_number=0)  # old is None

    # Because old was None => old dict is {}
    # The new is {"uid": "msg-1", "text": "Hello", "count": 1}
    # We expect a merge with entire new dict or multiple ops. 
    # For the code in compute_generic_delta, 
    #   - old_as_dict = {} 
    #   - new_as_dict = { "uid": "msg-1", "text": "Hello", "count": 1 }
    # We'll get a "merge" of the new fields, ignoring "uid" as it's part of the new structure.
    # Actually the path is "", so we get: [
    #   GenericDelta(op="merge", path="", value={"uid": "msg-1", "text": "Hello", "count": 1})
    # ]
    
    assert len(deltas) == 1
    delta_content = deltas[0]
    assert isinstance(delta_content, StreamingDeltaMessageContent)
    assert delta_content.message_id == "msg-1"
    # The delta operation should be "merge"
    assert delta_content.delta.op == "merge"
    assert delta_content.delta.value["text"] == "Hello"
    assert delta_content.delta.value["count"] == 1


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
