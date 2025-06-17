"""Test that reproduces the exact bug scenario reported by the user."""

import json
from datetime import datetime

from agent_platform.core.thread import ThreadMessage
from agent_platform.core.thread.content import ThreadTextContent, ThreadThoughtContent


def test_bug_scenario_message_serialization():
    """Test the exact scenario from the bug report where commited and complete were always false."""
    # Create a message exactly like the one in the bug report
    message = ThreadMessage(
        message_id="9d18d393-5c07-4d7d-9997-f401ae83e137",
        role="agent",
        content=[
            ThreadThoughtContent(
                thought="""\nThe user\'s current request is simply "hi," which is a greeting. There
                      are no additional tasks or tool calls necessary. The best response is to reply
                with an appropriate greeting, maintaining context and readiness for follow-up
                requests.\n""",
            ),
            ThreadTextContent(
                text="\nHello! How can I assist you today?\n",
                citations=[],
            ),
        ],
        created_at=datetime.fromisoformat("2025-05-28T10:26:00.912082Z"),
        updated_at=datetime.fromisoformat("2025-05-28T10:26:00.912082Z"),
        agent_metadata={},
        server_metadata={},
        parent_run_id=None,
        # These should be True for messages retrieved from database
        commited=True,
        complete=True,
    )

    # Mark content as complete (as storage would do)
    for content in message.content:
        content.complete = True

    # Serialize the message
    dumped = message.model_dump()

    # Verify the bug is fixed: commited and complete should be included and True
    assert "commited" in dumped, "model_dump should include commited field"
    assert "complete" in dumped, "model_dump should include complete field"
    assert dumped["commited"] is True, "commited should be True for persisted messages"
    assert dumped["complete"] is True, "complete should be True for persisted messages"

    # Verify content items are also complete
    assert all(content["complete"] is True for content in dumped["content"])

    # Convert to JSON to simulate API response
    json_str = json.dumps(dumped, default=str)
    json_data = json.loads(json_str)

    # Verify the fields are still present and correct after JSON serialization
    assert json_data["commited"] is True
    assert json_data["complete"] is True

    # Print the output to show it matches expected format
    print("Fixed message output:")
    print(json.dumps(json_data, indent=2))


def test_streaming_vs_persisted_messages():
    """Test the difference between streaming and persisted messages."""
    # Streaming message (not yet saved to DB)
    streaming_message = ThreadMessage(
        role="agent",
        content=[ThreadTextContent(text="Still typing...")],
        commited=False,  # Not yet saved
        complete=False,  # Still streaming
    )

    streaming_dump = streaming_message.model_dump()
    assert streaming_dump["commited"] is False
    assert streaming_dump["complete"] is False

    # Persisted message (retrieved from DB)
    persisted_message = ThreadMessage(
        role="agent",
        content=[ThreadTextContent(text="Message complete!")],
        commited=True,  # Saved to DB
        complete=True,  # Finished streaming
    )
    persisted_message.mark_complete()  # Ensures content is also marked complete

    persisted_dump = persisted_message.model_dump()
    assert persisted_dump["commited"] is True
    assert persisted_dump["complete"] is True
    assert persisted_dump["content"][0]["complete"] is True
