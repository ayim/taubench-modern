import json
from datetime import UTC, datetime

import pytest

from agent_platform.core.agent.agent import Agent, AgentArchitecture
from agent_platform.core.architectures.resolver import ArchitectureResolutionError
from agent_platform.core.mcp.mcp_server import MCPServer
from agent_platform.core.mcp.mcp_types import (
    MCPVariableTypeDataServerInfo,
    MCPVariableTypeOAuth2Secret,
    MCPVariableTypeSecret,
    MCPVariableTypeString,
)
from agent_platform.core.payloads.upsert_agent import StructuredRunbookPayload, UpsertAgentPayload
from agent_platform.core.runbook import Runbook
from agent_platform.core.selected_tools import SelectedToolConfig, SelectedTools
from agent_platform.server.api.private_v2.compatibility.agent_compat import AgentCompat

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


def process_payload(payload: dict) -> Agent:
    # Dummy function to simulate endpoint or handler
    validated_payload = UpsertAgentPayload.model_validate(payload)
    return UpsertAgentPayload.to_agent(validated_payload, user_id="u1")


class TestLegacyModelDictToAllowlist:
    """Test the _legacy_model_dict_to_allowlist method."""

    def setup_method(self):
        """Set up a test payload instance."""
        self.payload = _create_payload({})

    def test_valid_simple_provider_name(self):
        """Test with simple provider and name."""
        model_dict = {"provider": "openai", "name": "gpt-4"}
        result = self.payload._legacy_model_dict_to_allowlist(model_dict)
        assert result == {"openai": ["gpt-4"]}

    def test_valid_name_with_slash(self):
        """Test when name contains a slash - should split and use first part as provider."""
        model_dict = {
            "provider": "openai",  # This will be overridden
            "name": "anthropic/claude-3-opus",
        }
        result = self.payload._legacy_model_dict_to_allowlist(model_dict)
        assert result == {"anthropic": ["claude-3-opus"]}

    def test_name_with_multiple_slashes(self):
        """Test when name contains multiple slashes - should only split on first."""
        model_dict = {"provider": "openai", "name": "provider/model/version"}
        result = self.payload._legacy_model_dict_to_allowlist(model_dict)
        assert result == {"provider": ["model/version"]}

    def test_missing_provider_key(self):
        """Test when provider key is missing - should return None."""
        model_dict = {"name": "gpt-4"}
        result = self.payload._legacy_model_dict_to_allowlist(model_dict)
        assert result is None

    def test_missing_name_key(self):
        """Test when name key is missing - should return None."""
        model_dict = {"provider": "openai"}
        result = self.payload._legacy_model_dict_to_allowlist(model_dict)
        assert result is None

    def test_missing_both_keys(self):
        """Test when both keys are missing - should return None."""
        model_dict = {}
        result = self.payload._legacy_model_dict_to_allowlist(model_dict)
        assert result is None

    def test_empty_provider(self):
        """Test with empty provider string - should return None."""
        model_dict = {"provider": "", "name": "gpt-4"}
        result = self.payload._legacy_model_dict_to_allowlist(model_dict)
        assert result is None

    def test_empty_name(self):
        """Test with empty name string - should return None."""
        model_dict = {"provider": "openai", "name": ""}
        result = self.payload._legacy_model_dict_to_allowlist(model_dict)
        assert result is None

    def test_empty_both_values(self):
        """Test with empty strings for both provider and name - should return None."""
        model_dict = {"provider": "", "name": ""}
        result = self.payload._legacy_model_dict_to_allowlist(model_dict)
        assert result is None

    def test_name_starts_with_slash(self):
        """Test when name starts with a slash."""
        model_dict = {"provider": "openai", "name": "/gpt-4"}
        result = self.payload._legacy_model_dict_to_allowlist(model_dict)
        assert result == {"": ["gpt-4"]}

    def test_name_ends_with_slash(self):
        """Test when name ends with a slash."""
        model_dict = {"provider": "openai", "name": "gpt-4/"}
        result = self.payload._legacy_model_dict_to_allowlist(model_dict)
        assert result == {"gpt-4": [""]}

    def test_name_only_slash(self):
        """Test when name is only a slash."""
        model_dict = {"provider": "openai", "name": "/"}
        result = self.payload._legacy_model_dict_to_allowlist(model_dict)
        assert result == {"": [""]}

    def test_none_values(self):
        """Test with None values for provider and name."""
        # Test None provider - should return None (invalid input)
        model_dict = {"provider": None, "name": "gpt-4"}
        result = self.payload._legacy_model_dict_to_allowlist(model_dict)
        assert result is None

        # Test None name - should return None (invalid input)
        model_dict = {"provider": "openai", "name": None}
        result = self.payload._legacy_model_dict_to_allowlist(model_dict)
        assert result is None

        # Test both None - should return None (invalid input)
        model_dict = {"provider": None, "name": None}
        result = self.payload._legacy_model_dict_to_allowlist(model_dict)
        assert result is None

    def test_extra_keys_ignored(self):
        """Test that extra keys in the dictionary are ignored."""
        model_dict = {
            "provider": "openai",
            "name": "gpt-4",
            "version": "1.0",
            "config": {"temperature": 0.7},
        }
        result = self.payload._legacy_model_dict_to_allowlist(model_dict)
        assert result == {"openai": ["gpt-4"]}

    def test_real_world_examples(self):
        """Test with real-world model examples."""
        # OpenAI
        model_dict = {"provider": "OpenAI", "name": "gpt-4"}
        result = self.payload._legacy_model_dict_to_allowlist(model_dict)
        assert result == {"openai": ["gpt-4"]}

        # Anthropic with slash notation
        model_dict = {"provider": "Anthropic", "name": "anthropic/claude-3-opus-20240229"}
        result = self.payload._legacy_model_dict_to_allowlist(model_dict)
        assert result == {"anthropic": ["claude-3-opus-20240229"]}

        # Azure
        model_dict = {"provider": "Azure", "name": "gpt-35-turbo"}
        result = self.payload._legacy_model_dict_to_allowlist(model_dict)
        assert result == {"azure": ["gpt-35-turbo"]}

        # Bedrock with provider in name
        model_dict = {"provider": "Amazon", "name": "amazon/titan-text-express-v1"}
        result = self.payload._legacy_model_dict_to_allowlist(model_dict)
        assert result == {"amazon": ["titan-text-express-v1"]}

    def test_new_model(self):
        """Test a real-world example that was broken where a new model was sent
        but just the model name, and the provider mapping was not working."""
        model_dict = {"provider": "Amazon", "name": "claude-4-sonnet"}
        result = self.payload._legacy_model_dict_to_allowlist(model_dict)
        assert result == {"anthropic": ["claude-4-sonnet"]}

    def test_resolves_to_azure(self):
        known_names = [
            "gpt-5-high",
            "gpt-5-medium",
            "gpt-5-low",
            "gpt-5-minimal",
            "gpt-5-mini",
            "gpt-5-nano",
            "gpt-4-1",
            "gpt-4-1-mini",
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4o-chatgpt",
            "o3-high",
            "o3-low",
            "o4-mini-high",
            "o4-mini-low",
        ]
        for name in known_names:
            model_dict = {"provider": "Azure", "name": name}
            result = self.payload._legacy_model_dict_to_allowlist(model_dict)
            # this looks weird, but remember that Azure may some day have deployment
            # of other models from other provides (not sure openai). We're future
            # proofing that here.
            assert result == {"openai": [name]}

        unknown_names = ["foo-bar-baz"]
        for name in unknown_names:
            model_dict = {"provider": "Azure", "name": name}
            result = self.payload._legacy_model_dict_to_allowlist(model_dict)
            # When we don't know the name, we just pass it through with the given provider
            assert result == {"azure": [name]}


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


def test_to_agent_preserves_runbook_timestamp_when_unchanged() -> None:
    existing_timestamp = datetime(2024, 1, 1, 9, 0, tzinfo=UTC)
    existing_agent = Agent(
        name="Existing",
        description="desc",
        user_id="u1",
        runbook_structured=Runbook(
            raw_text="Do the thing",
            content=[],
            updated_at=existing_timestamp,
        ),
        version="1.0.0",
        platform_configs=[],
        agent_architecture=DEFAULT_ARCH,
    )

    payload = UpsertAgentPayload(
        name="Existing",
        description="desc",
        version="1.0.1",
        structured_runbook=StructuredRunbookPayload(raw_text="Do the thing", content=[]),
        agent_architecture=DEFAULT_ARCH,
    )

    result = UpsertAgentPayload.to_agent(
        payload,
        user_id="u1",
        existing_agent=existing_agent,
    )

    assert result.runbook_structured.updated_at == existing_timestamp


def test_to_agent_updates_runbook_timestamp_when_changed() -> None:
    existing_timestamp = datetime(2024, 1, 1, 9, 0, tzinfo=UTC)
    existing_agent = Agent(
        name="Existing",
        description="desc",
        user_id="u1",
        runbook_structured=Runbook(
            raw_text="Do the thing",
            content=[],
            updated_at=existing_timestamp,
        ),
        version="1.0.0",
        platform_configs=[],
        agent_architecture=DEFAULT_ARCH,
    )

    payload = UpsertAgentPayload(
        name="Existing",
        description="desc",
        version="1.0.1",
        structured_runbook=StructuredRunbookPayload(raw_text="Do another thing", content=[]),
        agent_architecture=DEFAULT_ARCH,
    )

    result = UpsertAgentPayload.to_agent(
        payload,
        user_id="u1",
        existing_agent=existing_agent,
    )

    assert result.runbook_structured.updated_at > existing_timestamp
    assert result.runbook_structured.updated_at.tzinfo == UTC


def test_to_agent_sets_runbook_updated_at_on_create() -> None:
    payload = UpsertAgentPayload(
        name="Agent",
        description="desc",
        version="1.0.0",
        runbook="Do things",
        agent_architecture=DEFAULT_ARCH,
    )

    agent = UpsertAgentPayload.to_agent(payload, user_id="u1")

    assert agent.runbook_structured.updated_at is not None
    assert isinstance(agent.runbook_structured.updated_at, datetime)


def test_to_agent_preserves_runbook_updated_at_when_unchanged() -> None:
    payload = UpsertAgentPayload(
        name="Agent",
        description="desc",
        version="1.0.0",
        runbook="Do things",
        agent_architecture=DEFAULT_ARCH,
    )
    agent = UpsertAgentPayload.to_agent(payload, user_id="u1")
    # Use a deliberately old timestamp to ensure we can detect new updates even when
    # `datetime.now()` runs within the same microsecond during the test run.
    agent.runbook_structured.updated_at = datetime(2000, 1, 1, tzinfo=UTC)
    original_updated_at = agent.runbook_structured.updated_at

    same_payload = UpsertAgentPayload(
        name="Agent",
        description="desc",
        version="1.0.0",
        runbook="Do things",
        agent_architecture=DEFAULT_ARCH,
    )
    updated_agent = UpsertAgentPayload.to_agent(
        same_payload,
        user_id="u1",
        agent_id=agent.agent_id,
        existing_agent=agent,
    )

    assert updated_agent.runbook_structured.updated_at == original_updated_at


def test_to_agent_updates_runbook_updated_at_when_runbook_changes() -> None:
    base_runbook = StructuredRunbookPayload(raw_text="Do things", content=[])
    payload = UpsertAgentPayload(
        name="Agent",
        description="desc",
        version="1.0.0",
        structured_runbook=base_runbook,
        agent_architecture=DEFAULT_ARCH,
    )
    agent = UpsertAgentPayload.to_agent(payload, user_id="u1")
    # Use a deliberately old timestamp to ensure we can detect new updates even when
    # `datetime.now()` runs within the same microsecond during the test run.
    agent.runbook_structured.updated_at = datetime(2000, 1, 1, tzinfo=UTC)
    original_updated_at = agent.runbook_structured.updated_at

    changed_payload = UpsertAgentPayload(
        name="Agent",
        description="desc",
        version="1.0.0",
        runbook="Do different things",
        agent_architecture=DEFAULT_ARCH,
    )
    changed_agent = UpsertAgentPayload.to_agent(
        changed_payload,
        user_id="u1",
        agent_id=agent.agent_id,
        existing_agent=agent,
    )

    assert changed_agent.runbook_structured.updated_at is not None
    assert original_updated_at is not None
    assert changed_agent.runbook_structured.updated_at != original_updated_at
    assert changed_agent.runbook_structured.updated_at > original_updated_at


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
        MCPUnionOfVariableTypes,
        MCPVariableTypeSecret,
        MCPVariableTypeString,
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


def test_accept_new_architecture_in_legacy_payload():
    """Test that we can accept a new architecture in a legacy payload."""
    payload = UpsertAgentPayload(
        name="Test Agent",
        description="desc",
        version="2.0.0",
        runbook="hi",
        advanced_config={
            "architecture": "agent_platform.architectures.experimental_1",
        },
    )
    agent = UpsertAgentPayload.to_agent(payload, user_id="u1")
    assert agent.agent_architecture == AgentArchitecture(
        name="agent_platform.architectures.experimental_1",
        version="2.0.0",
    )


def test_non_new_architecture_gets_default_architecture():
    """Test that a non-new architecture still gets the default architecture."""
    payload = UpsertAgentPayload(
        name="Test Agent",
        description="desc",
        version="1.0.0",
        runbook="hi",
        advanced_config={
            "architecture": "plan_execute",
        },
    )
    agent = UpsertAgentPayload.to_agent(payload, user_id="u1")
    assert agent.agent_architecture == AgentArchitecture(
        name="agent_platform.architectures.default",
        version="1.0.0",
    )


class TestSelectedTools:
    """Test the SelectedTools functionality in UpsertAgentPayload."""

    def test_selected_tools_creation_and_validation(self):
        """Test SelectedTools creation, validation, and serialization."""
        # Test default factory
        payload = UpsertAgentPayload(
            name="Test Agent",
            description="desc",
            version="1.0.0",
            runbook="hi",
            agent_architecture=DEFAULT_ARCH,
        )
        assert isinstance(payload.selected_tools, SelectedTools)
        assert payload.selected_tools.tool_names == []

        # Test with specific tool names
        selected_tools = SelectedTools(
            tool_names=[
                SelectedToolConfig(tool_name="greet_country"),
                SelectedToolConfig(tool_name="search_web"),
            ]
        )
        payload_with_tools = UpsertAgentPayload(
            name="Test Agent",
            description="desc",
            version="1.0.0",
            runbook="hi",
            agent_architecture=DEFAULT_ARCH,
            selected_tools=selected_tools,
        )
        assert len(payload_with_tools.selected_tools.tool_names) == 2
        assert payload_with_tools.selected_tools.tool_names[0].tool_name == "greet_country"
        assert payload_with_tools.selected_tools.tool_names[1].tool_name == "search_web"

        # Test model_validate with dict
        data = {
            "name": "Test Agent",
            "description": "desc",
            "version": "1.0.0",
            "runbook": "hi",
            "agent_architecture": {
                "name": "agent_platform.architectures.default",
                "version": "1.0.0",
            },
            "selected_tools": {"tool_names": [{"tool_name": "tool1"}, {"tool_name": "tool2"}]},
        }
        validated_payload = UpsertAgentPayload.model_validate(data)
        assert isinstance(validated_payload.selected_tools, SelectedTools)
        assert len(validated_payload.selected_tools.tool_names) == 2
        assert validated_payload.selected_tools.tool_names[0].tool_name == "tool1"
        assert validated_payload.selected_tools.tool_names[1].tool_name == "tool2"

        # Test model_validate with missing selected_tools (should use default)
        data_no_tools = {
            "name": "Test Agent",
            "description": "desc",
            "version": "1.0.0",
            "runbook": "hi",
            "agent_architecture": {
                "name": "agent_platform.architectures.default",
                "version": "1.0.0",
            },
        }
        payload_no_tools = UpsertAgentPayload.model_validate(data_no_tools)
        assert isinstance(payload_no_tools.selected_tools, SelectedTools)
        assert payload_no_tools.selected_tools.tool_names == []

        # Test SelectedTools model_dump and model_validate
        selected_tools_obj = SelectedTools(
            tool_names=[
                SelectedToolConfig(tool_name="tool1"),
                SelectedToolConfig(tool_name="tool2"),
            ]
        )
        dumped = selected_tools_obj.model_dump()
        assert dumped == {"tool_names": [{"tool_name": "tool1"}, {"tool_name": "tool2"}]}

        validated_obj = SelectedTools.model_validate(
            {"tool_names": [{"tool_name": "tool3"}, {"tool_name": "tool4"}]}
        )
        assert len(validated_obj.tool_names) == 2
        assert validated_obj.tool_names[0].tool_name == "tool3"
        assert validated_obj.tool_names[1].tool_name == "tool4"

    def test_selected_tools_integration(self):
        """Test SelectedTools integration with Agent creation and serialization."""
        # Test to_agent preserves selected_tools
        selected_tools = SelectedTools(
            tool_names=[
                SelectedToolConfig(tool_name="greet_country"),
                SelectedToolConfig(tool_name="search_web"),
            ]
        )
        payload = UpsertAgentPayload(
            name="Test Agent",
            description="desc",
            version="1.0.0",
            runbook="hi",
            agent_architecture=DEFAULT_ARCH,
            selected_tools=selected_tools,
        )
        agent = UpsertAgentPayload.to_agent(payload, user_id="u1")
        assert isinstance(agent.selected_tools, SelectedTools)
        assert len(agent.selected_tools.tool_names) == 2
        assert agent.selected_tools.tool_names[0].tool_name == "greet_country"
        assert agent.selected_tools.tool_names[1].tool_name == "search_web"

        # Test agent model_dump includes selected_tools
        agent_dict = agent.model_dump()
        assert "selected_tools" in agent_dict
        assert agent_dict["selected_tools"]["tool_names"] == [
            {"tool_name": "greet_country"},
            {"tool_name": "search_web"},
        ]

        # Test process_payload function
        data = {
            "name": "Test Agent",
            "description": "desc",
            "version": "1.0.0",
            "runbook": "hi",
            "agent_architecture": {
                "name": "agent_platform.architectures.default",
                "version": "1.0.0",
            },
            "selected_tools": {"tool_names": [{"tool_name": "process_tool"}]},
        }
        processed_agent = process_payload(data)
        assert isinstance(processed_agent.selected_tools, SelectedTools)
        assert len(processed_agent.selected_tools.tool_names) == 1
        assert processed_agent.selected_tools.tool_names[0].tool_name == "process_tool"

    def test_backward_compatibility_with_string_format(self):
        """Test that SelectedTools can handle legacy string format for backward compatibility."""
        # Test with legacy format (list of strings)
        legacy_data = {
            "name": "Test Agent",
            "description": "desc",
            "version": "1.0.0",
            "runbook": "hi",
            "agent_architecture": {
                "name": "agent_platform.architectures.default",
                "version": "1.0.0",
            },
            "selected_tools": {"tool_names": ["legacy_tool1", "legacy_tool2"]},
        }
        validated_payload = UpsertAgentPayload.model_validate(legacy_data)
        assert isinstance(validated_payload.selected_tools, SelectedTools)
        assert len(validated_payload.selected_tools.tool_names) == 2
        assert validated_payload.selected_tools.tool_names[0].tool_name == "legacy_tool1"
        assert validated_payload.selected_tools.tool_names[1].tool_name == "legacy_tool2"


class TestArchitectureCompatibility:
    def test_allowlist_incompatible_architecture_switches(self):
        payload = UpsertAgentPayload(
            name="A",
            description="desc",
            version="1.0.0",
            runbook="hi",
            agent_architecture=AgentArchitecture(
                name="agent_platform.architectures.default",
                version="1.0.0",
            ),
            platform_configs=[
                {
                    "kind": "openai",
                    "name": "test",
                    "openai_api_key": "dummy",
                    "models": {"openai": ["gpt-5-high"]},
                }
            ],
        )

        agent = UpsertAgentPayload.to_agent(payload, user_id="u1")
        # Should switch from default to experimental arch to satisfy model requirement
        assert agent.agent_architecture.name == "agent_platform.architectures.experimental_1"

    def test_allowlist_compatible_architecture_passes(self):
        payload = UpsertAgentPayload(
            name="A",
            description="desc",
            version="1.0.0",
            runbook="hi",
            agent_architecture=AgentArchitecture(
                name="agent_platform.architectures.experimental_1",
                version="2.0.0",
            ),
            platform_configs=[
                {
                    "kind": "openai",
                    "name": "test",
                    "openai_api_key": "dummy",
                    "models": {"openai": ["gpt-5-high"]},
                }
            ],
        )

        agent = UpsertAgentPayload.to_agent(payload, user_id="u1")
        assert agent.agent_architecture.name == "agent_platform.architectures.experimental_1"


class TestArchitectureSolverResolution:
    def _patch_configs(
        self, monkeypatch, mapping_models: dict[str, str], mapping_reqs: dict[str, list[str]]
    ):
        # Patch the symbol used inside upsert_agent to a dummy object that
        # behaves both as a class (for attribute access) and as a callable
        # returning itself (for constructor calls).
        class DummyCfg:
            def __init__(self):
                self.models_to_platform_specific_model_ids = mapping_models
                self.models_to_architecture_overrides = mapping_reqs

            def __call__(self):
                return self

        dummy = DummyCfg()
        from agent_platform.core.payloads import upsert_agent as ua

        original = ua.PlatformModelConfigs
        monkeypatch.setattr(ua, "PlatformModelConfigs", dummy, raising=False)
        return original

    def _patch_arch_entry_points(self, monkeypatch, versions: dict[str, str]):
        import types
        from importlib import import_module as real_import_module

        class EP:
            def __init__(self, name, value):
                self.name = name
                self.value = value

        def fake_entry_points(group=None):
            if group == "agent_platform.architectures":
                return [EP(name, f"fake_{name}:entry") for name in versions.keys()]
            return []

        def fake_import_module(name):
            if name.startswith("fake_"):
                mod = types.ModuleType(name)
                arch_name = name.replace("fake_", "")
                mod.__version__ = versions.get(arch_name, "0.0.0")  # type: ignore[attr-defined]
                return mod
            return real_import_module(name)

        monkeypatch.setattr("importlib.metadata.entry_points", fake_entry_points)
        monkeypatch.setattr("importlib.import_module", fake_import_module)

    def test_resolves_to_stricter_arch_version_across_models(self, monkeypatch):
        # Require A>=1.0 for m1, and (B>=1.0 or A>=1.2) for m2; only A satisfies both -> A>=1.2
        models_map = {
            "openai/prov/m1": "m1",
            "openai/prov/m2": "m2",
        }
        reqs_map = {
            "openai/prov/m1": ["A>=1.0"],
            "openai/prov/m2": ["B>=1.0", "A>=1.2"],
        }

        original_cfg = self._patch_configs(monkeypatch, models_map, reqs_map)
        try:
            # Present arch versions: A==1.2.0, B==2.0.0
            self._patch_arch_entry_points(monkeypatch, {"A": "1.2.0", "B": "2.0.0"})

            payload = UpsertAgentPayload(
                name="X",
                description="d",
                version="1.0.0",
                runbook="hi",
                agent_architecture=AgentArchitecture(name="irrelevant.arch", version="1.0.0"),
                platform_configs=[{"kind": "openai", "name": "t", "openai_api_key": "k"}],
            )
            agent = UpsertAgentPayload.to_agent(payload, user_id="u1")
            assert agent.agent_architecture.name == "A"
            assert agent.agent_architecture.version == "1.2.0"
        finally:
            from agent_platform.core.payloads import upsert_agent as ua

            ua.PlatformModelConfigs = original_cfg

    def test_no_solution_raises(self, monkeypatch):
        # m1 requires A>=3.0, m2 requires B>=4.0; single arch cannot satisfy both -> error
        models_map = {
            "openai/prov/m1": "m1",
            "openai/prov/m2": "m2",
        }
        reqs_map = {
            "openai/prov/m1": ["A>=3.0"],
            "openai/prov/m2": ["B>=4.0"],
        }
        original_cfg = self._patch_configs(monkeypatch, models_map, reqs_map)
        try:
            self._patch_arch_entry_points(monkeypatch, {"A": "2.5.0", "B": "3.5.0"})

            payload = UpsertAgentPayload(
                name="X",
                description="d",
                version="1.0.0",
                runbook="hi",
                agent_architecture=AgentArchitecture(name="irrelevant.arch", version="1.0.0"),
                platform_configs=[{"kind": "openai", "name": "t", "openai_api_key": "k"}],
            )
            with pytest.raises(ArchitectureResolutionError):
                UpsertAgentPayload.to_agent(payload, user_id="u1")
        finally:
            from agent_platform.core.payloads import upsert_agent as ua

            ua.PlatformModelConfigs = original_cfg

    def test_preserve_default_arch_when_no_constraints(self, monkeypatch):
        # No requirements: preserve the provided architecture
        models_map = {
            "openai/prov/m1": "m1",
        }
        reqs_map = {}
        original_cfg = self._patch_configs(monkeypatch, models_map, reqs_map)
        try:
            payload = UpsertAgentPayload(
                name="X",
                description="d",
                version="1.0.0",
                runbook="hi",
                agent_architecture=AgentArchitecture(
                    name="agent_platform.architectures.default", version="1.0.0"
                ),
                platform_configs=[{"kind": "openai", "name": "t", "openai_api_key": "k"}],
            )
            agent = UpsertAgentPayload.to_agent(payload, user_id="u1")
            assert agent.agent_architecture.name == "agent_platform.architectures.default"
            assert agent.agent_architecture.version == "1.0.0"
        finally:
            from agent_platform.core.payloads import upsert_agent as ua

            ua.PlatformModelConfigs = original_cfg

    def test_no_allowlist_any_model_on_platform(self):
        # With no allowlist, we require the architecture to satisfy the conjunction
        # of all model constraints on the platform. OpenAI has models requiring
        # the experimental architecture, so the solver should switch to it.
        payload = UpsertAgentPayload(
            name="A",
            description="desc",
            version="1.0.0",
            runbook="hi",
            agent_architecture=AgentArchitecture(
                name="agent_platform.architectures.default",
                version="1.0.0",
            ),
            platform_configs=[
                {
                    "kind": "openai",
                    "name": "test",
                    "openai_api_key": "dummy",
                    # No models field -> treat as full platform set
                }
            ],
        )

        agent = UpsertAgentPayload.to_agent(payload, user_id="u1")
        assert agent.agent_architecture.name == "agent_platform.architectures.experimental_1"


def test_missing_name_azure_legacy():
    """Test we raise an error when missing the name"""
    with pytest.raises(ValueError) as e:  # noqa: PT011
        UpsertAgentPayload(
            name="Legacy Azure Agent",
            description="desc",
            version="1.0.0",
            runbook="hi",
            agent_architecture=DEFAULT_ARCH,
            model={
                "provider": "Azure",
                # Intentionally omitting the name.
                # "name": "gpt-5-low",
                "config": {
                    "chat_url": "https://myresource.openai.azure.com/openai/deployments/gpt-5-deployment/chat/completions?api-version=2024-02-01",
                    "chat_openai_api_key": "test-legacy-key",
                    "embeddings_url": "https://myresource.openai.azure.com/openai/deployments/embeddings-deployment/embeddings?api-version=2024-02-01",
                },
            },
        )
    assert "missing required 'name'" in str(e.value)


def test_legacy_azure_chat_openai_api_key_conversion():
    """Test that legacy chat_openai_api_key is converted to azure_api_key."""
    payload = UpsertAgentPayload(
        name="Legacy Azure Agent",
        description="desc",
        version="1.0.0",
        runbook="hi",
        agent_architecture=DEFAULT_ARCH,
        model={
            "provider": "Azure",
            "name": "gpt-5-low",
            "config": {
                "chat_url": "https://myresource.openai.azure.com/openai/deployments/gpt-5-deployment/chat/completions?api-version=2024-02-01",
                "chat_openai_api_key": "test-legacy-key",
                "embeddings_url": "https://myresource.openai.azure.com/openai/deployments/embeddings-deployment/embeddings?api-version=2024-02-01",
            },
        },
    )

    agent = UpsertAgentPayload.to_agent(payload, user_id="u1")

    assert len(agent.platform_configs) == 1
    azure_config = agent.platform_configs[0]
    assert azure_config.kind == "azure"
    assert azure_config.azure_api_key is not None
    assert azure_config.azure_api_key.get_secret_value() == "test-legacy-key"
    assert azure_config.azure_endpoint_url == "https://myresource.openai.azure.com"
    assert azure_config.azure_deployment_name == "gpt-5-deployment"
    assert azure_config.azure_model_backing_deployment_name == "gpt-5-low"
    assert azure_config.azure_deployment_name_embeddings == "embeddings-deployment"
    assert azure_config.azure_api_version == "2024-02-01"
    assert azure_config.models == {"openai": ["gpt-5-low"]}
