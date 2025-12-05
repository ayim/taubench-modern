from typing import Any

import pytest

from sema4ai_docint.agent_server_client.client import AgentServerClient
from sema4ai_docint.agent_server_client.transport.base import ResponseMessage


@pytest.mark.parametrize(
    "test_case",
    [
        (
            ResponseMessage(
                content=[
                    {"kind": "reasoning", "text": "This is a test"},
                    {"kind": "text", "text": "Hello, world!"},
                ]
            ),
            "Hello, world!",
        ),
        (
            ResponseMessage(
                content=[
                    {"kind": "text", "text": "Hello, world!"},
                ]
            ),
            "Hello, world!",
        ),
        (
            ResponseMessage(
                content=[
                    {"kind": "text", "text": "Hello, earth!"},
                    {"kind": "text", "text": "Hello, world!"},
                ]
            ),
            "Hello, earth!",
        ),
    ],
)
def test_extract_text_content(test_case: tuple[dict[str, Any], str]):
    agent_server_response, expected = test_case

    assert AgentServerClient.extract_text_content(agent_server_response) == expected


def test_extract_text_content_bad_input():
    with pytest.raises(ValueError, match="No content in response from agent server"):
        AgentServerClient.extract_text_content(ResponseMessage())

    with pytest.raises(ValueError, match="No content in response from agent server"):
        AgentServerClient.extract_text_content(ResponseMessage(content=[]))

    with pytest.raises(ValueError, match="No text content in response from agent server"):
        AgentServerClient.extract_text_content(
            ResponseMessage(content=[{"kind": "reasoning", "text": "This is a test"}])
        )
