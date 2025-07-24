from agent_platform.core.agent.agent import Agent, AgentArchitecture
from agent_platform.core.payloads.upsert_agent import UpsertAgentPayload
from agent_platform.server.api.private_v2.compatibility.agent_compat import AgentCompat
from agent_platform.core.mcp.mcp_server import MCPServer
from agent_platform.core.mcp.mcp_types import (
    MCPVariableTypeString,
    MCPVariableTypeSecret,
    MCPVariableTypeOAuth2Secret,
    MCPVariableTypeDataServerInfo,
)
import json

DEFAULT_ARCH = AgentArchitecture(name="agent_platform.architectures.default", version="1.0.0")


def _create_payload(metadata: dict) -> UpsertAgentPayload:
    return UpsertAgentPayload(
        name="Test Agent",
        description="desc",
        version="1.0.0",
        runbook="hi",
        agent_architecture=DEFAULT_ARCH,
        metadata=metadata,
    )


def process_payload(payload: UpsertAgentPayload) -> Agent:
    # Dummy function to simulate endpoint or handler
    payload = UpsertAgentPayload.model_validate(payload)
    return UpsertAgentPayload.to_agent(payload, user_id="u1")


class TestWorkerConfigRoundTrip:
    def test_underscore_key(self) -> None:
        payload = _create_payload(
            {
                "mode": "worker",
                "worker_config": {
                    "type": "Document Intelligence",
                    "document_type": "Invoice",
                },
            }
        )
        agent = UpsertAgentPayload.to_agent(payload, user_id="u1")
        assert agent.extra["worker_config"] == {
            "type": "Document Intelligence",
            "document_type": "Invoice",
        }
        compat = AgentCompat.from_agent(agent)
        assert compat.metadata["worker_config"] == {
            "type": "Document Intelligence",
            "document_type": "Invoice",
        }

    def test_dash_key(self) -> None:
        payload = _create_payload(
            {
                "mode": "worker",
                "worker-config": {
                    "type": "Document Intelligence",
                    "document_type": "Invoice",
                },
            }
        )
        agent = UpsertAgentPayload.to_agent(payload, user_id="u1")
        assert agent.extra["worker_config"] == {
            "type": "Document Intelligence",
            "document_type": "Invoice",
        }
        compat = AgentCompat.from_agent(agent)
        assert compat.metadata["worker_config"] == {
            "type": "Document Intelligence",
            "document_type": "Invoice",
        }


class TestMCPServerPayload:
    def test_mcp_server_with_all_header_and_env_types_url(self):
        mcp_server = MCPServer(
            name="test-mcp-server-url",
            url="https://example.com/mcp",
            transport="streamable-http",
            headers={
                "X-Raw": "raw-value",
                "X-String": MCPVariableTypeString(
                    description="A string header", value="string-value"
                ),
                "X-Secret": MCPVariableTypeSecret(
                    description="A secret header", value="secret-value"
                ),
                "X-OAuth2": MCPVariableTypeOAuth2Secret(
                    provider="google",
                    scopes=["scope1", "scope2"],
                    description="OAuth2 header",
                    value="oauth2-token",
                ),
                "X-Data-Server": MCPVariableTypeDataServerInfo(value="server-info-value"),
            },
        )
        payload = _create_payload({})
        payload = payload.__class__(**{**payload.__dict__, "mcp_servers": [mcp_server]})
        agent = UpsertAgentPayload.to_agent(payload, user_id="u1")
        assert len(agent.mcp_servers) == 1
        server = agent.mcp_servers[0]
        assert server.name == "test-mcp-server-url"
        assert server.url == "https://example.com/mcp"
        assert server.transport == "streamable-http"
        # Check headers
        assert server.headers is not None, "server.headers should not be None"
        assert server.headers["X-Raw"] == "raw-value"
        assert isinstance(server.headers["X-Raw"], str)
        assert isinstance(server.headers["X-String"], MCPVariableTypeString)
        assert server.headers["X-String"].value == "string-value"
        assert isinstance(server.headers["X-Secret"], MCPVariableTypeSecret)
        assert server.headers["X-Secret"].value == "secret-value"
        assert isinstance(server.headers["X-OAuth2"], MCPVariableTypeOAuth2Secret)
        assert server.headers["X-OAuth2"].provider == "google"
        assert server.headers["X-OAuth2"].value == "oauth2-token"
        assert isinstance(server.headers["X-Data-Server"], MCPVariableTypeDataServerInfo)
        assert server.headers["X-Data-Server"].value == "server-info-value"

    def test_mcp_server_with_all_header_and_env_types_cmd(self):
        mcp_server = MCPServer(
            name="test-mcp-server-cmd",
            command="/usr/bin/fake-mcp-server",
            transport="stdio",
            env={
                "ENV_RAW": "raw-value",
                "ENV_STRING": MCPVariableTypeString(
                    description="A string env", value="env-string-value"
                ),
                "ENV_SECRET": MCPVariableTypeSecret(
                    description="A secret env", value="env-secret-value"
                ),
                "ENV_OAUTH2": MCPVariableTypeOAuth2Secret(
                    provider="github",
                    scopes=["repo", "user"],
                    description="OAuth2 env",
                    value="env-oauth2-token",
                ),
                "ENV_DATA_SERVER": MCPVariableTypeDataServerInfo(value="env-server-info-value"),
            },
        )
        payload = _create_payload({})
        payload = payload.__class__(**{**payload.__dict__, "mcp_servers": [mcp_server]})
        agent = UpsertAgentPayload.to_agent(payload, user_id="u1")
        assert len(agent.mcp_servers) == 1
        server = agent.mcp_servers[0]
        assert server.name == "test-mcp-server-cmd"
        assert server.command == "/usr/bin/fake-mcp-server"
        assert server.transport == "stdio"

        # Check env
        assert server.env is not None, "server.env should not be None"
        assert server.env["ENV_RAW"] == "raw-value"
        assert isinstance(server.env["ENV_RAW"], str)
        assert isinstance(server.env["ENV_STRING"], MCPVariableTypeString)
        assert server.env["ENV_STRING"].value == "env-string-value"
        assert isinstance(server.env["ENV_SECRET"], MCPVariableTypeSecret)
        assert server.env["ENV_SECRET"].value == "env-secret-value"
        assert isinstance(server.env["ENV_OAUTH2"], MCPVariableTypeOAuth2Secret)
        assert server.env["ENV_OAUTH2"].provider == "github"
        assert server.env["ENV_OAUTH2"].value == "env-oauth2-token"
        assert isinstance(server.env["ENV_DATA_SERVER"], MCPVariableTypeDataServerInfo)
        assert server.env["ENV_DATA_SERVER"].value == "env-server-info-value"

    def test_json_injection_url(self):
        json_str = json.dumps(
            {
                "name": "Test Agent",
                "description": "desc",
                "version": "1.0.0",
                "runbook": "hi",
                "agent_architecture": {
                    "name": "agent_platform.architectures.default",
                    "version": "1.0.0",
                },
                "mcp_servers": [
                    {
                        "name": "test-mcp-server-url",
                        "url": "https://example.com/mcp",
                        "transport": "streamable-http",
                        "headers": {
                            "X-Raw": "raw-value",
                            "X-String": {
                                "type": "string",
                                "description": "A string header",
                                "value": "string-value",
                            },
                            "X-Secret": {
                                "type": "secret",
                                "description": "A secret header",
                                "value": "secret-value",
                            },
                            "X-OAuth2": {
                                "type": "oauth2-secret",
                                "provider": "google",
                                "scopes": ["scope1", "scope2"],
                                "description": "OAuth2 header",
                                "value": "oauth2-token",
                            },
                            "X-Data-Server": {
                                "type": "data-server-info",
                                "value": "server-info-value",
                            },
                        },
                    }
                ],
            }
        )
        result = process_payload(json.loads(json_str))
        assert result.mcp_servers[0].name == "test-mcp-server-url"
        assert result.mcp_servers[0].url == "https://example.com/mcp"
        assert result.mcp_servers[0].transport == "streamable-http"
        headers = result.mcp_servers[0].headers
        assert headers is not None
        assert headers["X-Raw"] == "raw-value"
        assert isinstance(headers["X-String"], MCPVariableTypeString)
        assert headers["X-String"].value == "string-value"
        assert isinstance(headers["X-Secret"], MCPVariableTypeSecret)
        assert headers["X-Secret"].value == "secret-value"
        assert isinstance(headers["X-OAuth2"], MCPVariableTypeOAuth2Secret)
        assert headers["X-OAuth2"].provider == "google"
        assert headers["X-OAuth2"].value == "oauth2-token"
        assert isinstance(headers["X-Data-Server"], MCPVariableTypeDataServerInfo)
        assert headers["X-Data-Server"].value == "server-info-value"

    def test_json_injection_cmd(self):
        json_str = json.dumps(
            {
                "name": "Test Agent",
                "description": "desc",
                "version": "1.0.0",
                "runbook": "hi",
                "agent_architecture": {
                    "name": "agent_platform.architectures.default",
                    "version": "1.0.0",
                },
                "mcp_servers": [
                    {
                        "name": "test-mcp-server-cmd",
                        "command": "/usr/bin/fake-mcp-server",
                        "transport": "stdio",
                        "env": {
                            "ENV_RAW": "raw-value",
                            "ENV_STRING": {
                                "type": "string",
                                "description": "A string env",
                                "value": "env-string-value",
                            },
                            "ENV_SECRET": {
                                "type": "secret",
                                "description": "A secret env",
                                "value": "env-secret-value",
                            },
                            "ENV_OAUTH2": {
                                "type": "oauth2-secret",
                                "provider": "github",
                                "scopes": ["repo", "user"],
                                "description": "OAuth2 env",
                                "value": "env-oauth2-token",
                            },
                            "ENV_DATA_SERVER": {
                                "type": "data-server-info",
                                "value": "env-server-info-value",
                            },
                        },
                    }
                ],
            }
        )
        result = process_payload(json.loads(json_str))
        assert result.mcp_servers[0].name == "test-mcp-server-cmd"
        assert result.mcp_servers[0].command == "/usr/bin/fake-mcp-server"
        assert result.mcp_servers[0].transport == "stdio"
        env = result.mcp_servers[0].env
        assert env is not None
        assert env["ENV_RAW"] == "raw-value"
        assert isinstance(env["ENV_STRING"], MCPVariableTypeString)
        assert env["ENV_STRING"].value == "env-string-value"
        assert isinstance(env["ENV_SECRET"], MCPVariableTypeSecret)
        assert env["ENV_SECRET"].value == "env-secret-value"
        assert isinstance(env["ENV_OAUTH2"], MCPVariableTypeOAuth2Secret)
        assert env["ENV_OAUTH2"].provider == "github"
        assert env["ENV_OAUTH2"].value == "env-oauth2-token"
        assert isinstance(env["ENV_DATA_SERVER"], MCPVariableTypeDataServerInfo)
        assert env["ENV_DATA_SERVER"].value == "env-server-info-value"


def test_mcp_union_of_variable_types_behavior():
    from agent_platform.core.mcp.mcp_types import (
        MCPVariableTypeString,
        MCPVariableTypeSecret,
        MCPUnionOfVariableTypes,
    )

    # Create a dict with both str and MCPVariableTypeString
    headers: dict[str, MCPUnionOfVariableTypes] = {
        "plain": "plain-value",
        "string_obj": MCPVariableTypeString(description="desc", value="string-value"),
        "secret_obj": MCPVariableTypeSecret(description="desc", value="secret-value"),
    }
    # Check types
    assert isinstance(headers["plain"], str)
    assert isinstance(headers["string_obj"], MCPVariableTypeString)
    assert isinstance(headers["secret_obj"], MCPVariableTypeSecret)

    # Check value extraction
    def get_value(v):
        return v if isinstance(v, str) else v.value

    assert get_value(headers["plain"]) == "plain-value"
    assert get_value(headers["string_obj"]) == "string-value"
    assert get_value(headers["secret_obj"]) == "secret-value"
