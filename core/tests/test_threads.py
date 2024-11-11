from datetime import datetime

import pytest
from pydantic import ValidationError

from agent_server_types.threads import Thread


def test_thread_metadata_validator():
    # Test with valid JSON string
    valid_metadata_json = '{"key": "value"}'
    thread = Thread(
        thread_id="dummy",
        user_id="dummy",
        agent_id="dummy",
        name="dummy",
        created_at=datetime.now(),
        updated_at=datetime.now(),
        metadata=valid_metadata_json,
    )
    assert thread.metadata == {"key": "value"}

    # Test with invalid JSON string
    invalid_metadata_json = '{"key": "value"'
    with pytest.raises(ValidationError):
        Thread(
            thread_id="dummy",
            user_id="dummy",
            agent_id="dummy",
            name="dummy",
            created_at=datetime.now(),
            updated_at=datetime.now(),
            metadata=invalid_metadata_json,
        )

    # Test with 'null' string
    null_metadata = "null"
    thread = Thread(
        thread_id="dummy",
        user_id="dummy",
        agent_id="dummy",
        name="dummy",
        created_at=datetime.now(),
        updated_at=datetime.now(),
        metadata=null_metadata,
    )
    assert thread.metadata is None

    # Test with None
    thread = Thread(
        thread_id="dummy",
        user_id="dummy",
        agent_id="dummy",
        name="dummy",
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    assert thread.metadata is None
