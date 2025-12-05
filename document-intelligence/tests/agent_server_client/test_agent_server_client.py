from sema4ai_docint.agent_server_client.client import AgentServerClient


def test_is_known_schema():
    assert AgentServerClient.is_known_schema("foo", ["foo"])
    assert AgentServerClient.is_known_schema("FOO", ["foo"])
    assert not AgentServerClient.is_known_schema("foo", ["foobar", "bar", "baz"])
    assert not AgentServerClient.is_known_schema("unknown", ["foo"])
    assert not AgentServerClient.is_known_schema("UNKNOWN", ["foo"])
