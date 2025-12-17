from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError
from ruamel.yaml import YAML

from agent_platform.core.agent_package.spec import AgentSpec
from agent_platform.core.mcp.mcp_types import MCPVariableTypeOAuth2Secret, MCPVariableTypeSecret, MCPVariableTypeString


def _load_yaml_as_dict(yaml_bytes: bytes) -> dict[str, Any]:
    yaml = YAML(typ="safe")
    data = yaml.load(yaml_bytes)
    assert isinstance(data, dict)
    return data


def _assert_base_agent_fields(agent: Any, raw_agent: dict[str, Any]) -> None:
    """
    Assert "base-level" agent fields against the raw YAML agent dict.
    Intended for the passing (non-minimal) cases to avoid repeating boilerplate.
    """
    assert agent.name == raw_agent["name"]
    assert agent.description == raw_agent["description"]
    assert agent.version == raw_agent["version"]
    assert agent.architecture == raw_agent["architecture"]
    assert agent.reasoning == raw_agent["reasoning"]
    assert agent.runbook == raw_agent["runbook"]

    assert agent.model is not None
    assert raw_agent.get("model") is not None
    assert agent.model.provider == raw_agent["model"]["provider"]
    assert agent.model.name == raw_agent["model"]["name"]

    assert agent.metadata is not None
    assert raw_agent.get("metadata") is not None
    assert agent.metadata.mode == raw_agent["metadata"]["mode"]

    assert len(agent.action_packages) == len(raw_agent["action-packages"])
    for i, ap in enumerate(agent.action_packages):
        raw_ap = raw_agent["action-packages"][i]
        assert ap.name == raw_ap["name"]
        assert ap.organization == raw_ap["organization"]
        assert ap.type == raw_ap.get("type")
        assert ap.version == raw_ap["version"]
        assert ap.whitelist == raw_ap.get("whitelist")
        assert ap.path == raw_ap.get("path")


def test_spec_minimal() -> None:
    yaml_bytes = b"""\
agent-package:
  spec-version: v2
  agents:
  - name: Minimal v2 Agent
    description: Minimal valid agent spec for v2
    version: 1.0.0
    action-packages: []
"""

    raw = _load_yaml_as_dict(yaml_bytes)["agent-package"]
    raw_agent = raw["agents"][0]

    spec = AgentSpec.from_yaml(yaml_bytes)
    agent = spec.agent_package.agents[0]

    assert spec.agent_package.spec_version == raw["spec-version"]

    assert agent.name == raw_agent["name"]
    assert agent.description == raw_agent["description"]
    assert agent.version == raw_agent["version"]
    assert len(agent.action_packages) == 0

    assert agent.model is None
    assert agent.architecture is None
    assert agent.reasoning is None
    assert agent.runbook is None
    assert agent.knowledge is None
    assert agent.semantic_data_models is None
    assert agent.mcp_servers is None
    assert agent.docker_mcp_gateway is None
    assert agent.conversation_guide is None
    assert agent.conversation_starter is None
    assert agent.document_intelligence is None
    assert agent.welcome_message is None
    assert agent.metadata is None
    assert agent.selected_tools is None
    assert agent.agent_settings is None


def test_spec_with_conversation_guide() -> None:
    yaml_bytes = b"""\
agent-package:
  spec-version: v2
  agents:
  - name: v2 Agent with Conversation Fields
    description: Agent spec demonstrating conversation fields and document intelligence
    model:
      provider: OpenAI
      name: gpt-4o
    version: 1.2.3
    architecture: plan_execute
    reasoning: verbose
    runbook: runbook.md
    conversation-guide: conversation-guide.yaml
    conversation-starter: Hello! What would you like help with today?
    welcome-message: Ask me to search the web or summarize information.
    document-intelligence: v2
    action-packages:
    - name: free-web-search
      organization: Sema4.ai
      type: folder
      version: 1.0.0
      whitelist: search
      path: Sema4.ai/free-web-search
    metadata:
      mode: conversational
  exclude:
  - ./.git/**
  - ./.vscode/**
  - ./devdata/**
  - ./output/**
  - ./venv/**
  - ./.venv/**
  - ./**/.env
  - ./**/.DS_Store
  - ./**/*.pyc
  - ./*.zip
"""

    raw = _load_yaml_as_dict(yaml_bytes)["agent-package"]
    raw_agent = raw["agents"][0]

    spec = AgentSpec.from_yaml(yaml_bytes)
    agent = spec.agent_package.agents[0]

    assert spec.agent_package.spec_version == raw["spec-version"]
    assert "exclude" in raw
    assert spec.agent_package.exclude == raw["exclude"]

    _assert_base_agent_fields(agent, raw_agent)

    assert agent.mcp_servers is None
    assert agent.docker_mcp_gateway is None
    assert agent.agent_settings is None
    assert agent.selected_tools is None

    assert agent.conversation_guide == raw_agent["conversation-guide"]
    assert agent.conversation_starter == raw_agent["conversation-starter"]
    assert agent.welcome_message == raw_agent["welcome-message"]
    assert agent.document_intelligence == raw_agent["document-intelligence"]


def test_spec_with_agent_settings() -> None:
    yaml_bytes = b"""\
agent-package:
  spec-version: v2
  agents:
  - name: v2 Agent with Agent Settings
    description: Agent spec demonstrating agent settings dict
    model:
      provider: Azure
      name: gpt-4o
    version: 0.9.0
    architecture: agent
    reasoning: disabled
    runbook: runbook.md
    action-packages:
    - name: crm-actions
      organization: MyActions
      type: folder
      version: 2.0.0
      whitelist: lookup_customer,create_case
      path: MyActions/crm-actions
    agent-settings:
      enable_data_frames: true
      conversation-turns-kept-in-context: 10
      max_iterations: 6
      temperature: 0.2
    metadata:
      mode: conversational
"""

    raw = _load_yaml_as_dict(yaml_bytes)["agent-package"]
    raw_agent = raw["agents"][0]

    spec = AgentSpec.from_yaml(yaml_bytes)
    agent = spec.agent_package.agents[0]

    assert spec.agent_package.spec_version == raw["spec-version"]
    assert spec.agent_package.exclude is None

    _assert_base_agent_fields(agent, raw_agent)

    assert agent.mcp_servers is None
    assert agent.docker_mcp_gateway is None
    assert agent.selected_tools is None

    assert agent.agent_settings is not None
    assert agent.agent_settings["enable_data_frames"] is True
    assert (
        agent.agent_settings["conversation-turns-kept-in-context"]
        == raw_agent["agent-settings"]["conversation-turns-kept-in-context"]
    )
    assert agent.agent_settings["max_iterations"] == raw_agent["agent-settings"]["max_iterations"]
    assert agent.agent_settings["temperature"] == raw_agent["agent-settings"]["temperature"]


def test_spec_with_mcp_servers() -> None:
    yaml_bytes = b"""\
agent-package:
  spec-version: v2
  agents:
  - name: v2 Agent with MCP Servers
    description: Agent spec demonstrating MCP server configurations (and selected-tools)
    model:
      provider: OpenAI
      name: gpt-4o
    version: 2.1.0
    architecture: agent
    reasoning: enabled
    runbook: runbook.md
    action-packages:
    - name: free-web-search
      organization: Sema4.ai
      type: folder
      version: 1.0.0
      whitelist: ""
      path: Sema4.ai/free-web-search
    mcp-servers:
    - name: catalog-http
      transport: streamable-http
      url: http://localhost:8000/mcp
      headers:
        Authorization:
          type: secret
          description: Bearer token
          value: REDACTED
    - name: events-sse
      transport: sse
      url: http://localhost:9000/sse
      headers:
        Authorization:
          type: string
          value: Bearer 123
        X_VALUE_ONE: Test
    - name: local-stdio
      transport: stdio
      command-line: [uv, run, python, -m, my_mcp_server]
      env:
        MCP_API_KEY:
          type: secret
          description: API key for local MCP server
          value: REDACTED
        MCP_BEARER_TOKEN:
          type: oauth2-secret
          provider: auth0
          scopes: ["read:messages"]
          description: Bearer token for local MCP server
      force-serial-tool-calls: true
    selected-tools:
      tools:
      - name: query
      - name: describe
    metadata:
      mode: conversational
"""

    raw = _load_yaml_as_dict(yaml_bytes)["agent-package"]
    raw_agent = raw["agents"][0]

    spec = AgentSpec.from_yaml(yaml_bytes)
    agent = spec.agent_package.agents[0]

    assert spec.agent_package.spec_version == raw["spec-version"]
    assert spec.agent_package.exclude is None

    _assert_base_agent_fields(agent, raw_agent)

    assert agent.mcp_servers is not None
    assert len(agent.mcp_servers) == len(raw_agent["mcp-servers"])

    assert agent.mcp_servers[0].name == raw_agent["mcp-servers"][0]["name"]
    assert agent.mcp_servers[0].transport == raw_agent["mcp-servers"][0]["transport"]
    assert agent.mcp_servers[0].url == raw_agent["mcp-servers"][0]["url"]
    assert agent.mcp_servers[0].command_line is None
    assert agent.mcp_servers[0].headers is not None

    assert len(agent.mcp_servers[0].headers) == 1
    assert "Authorization" in agent.mcp_servers[0].headers
    assert "Authorization" in raw_agent["mcp-servers"][0]["headers"]

    auth_header_var = agent.mcp_servers[0].headers["Authorization"]
    raw_auth_header_var = raw_agent["mcp-servers"][0]["headers"]["Authorization"]

    assert isinstance(auth_header_var, MCPVariableTypeSecret)
    assert auth_header_var.type == raw_auth_header_var["type"]
    assert auth_header_var.description == raw_auth_header_var["description"]
    assert auth_header_var.value == raw_auth_header_var["value"]

    assert agent.mcp_servers[1].name == raw_agent["mcp-servers"][1]["name"]
    assert agent.mcp_servers[1].transport == raw_agent["mcp-servers"][1]["transport"]
    assert agent.mcp_servers[1].url == raw_agent["mcp-servers"][1]["url"]
    assert agent.mcp_servers[1].headers is not None

    auth_header_var = agent.mcp_servers[1].headers["Authorization"]
    raw_auth_header_var = raw_agent["mcp-servers"][1]["headers"]["Authorization"]
    x_value_one_header_var = agent.mcp_servers[1].headers["X_VALUE_ONE"]
    raw_x_value_one_header_var = raw_agent["mcp-servers"][1]["headers"]["X_VALUE_ONE"]

    assert isinstance(auth_header_var, MCPVariableTypeString)
    assert auth_header_var.value == raw_auth_header_var["value"]

    assert isinstance(x_value_one_header_var, str)
    assert x_value_one_header_var == raw_x_value_one_header_var

    assert agent.mcp_servers[2].name == raw_agent["mcp-servers"][2]["name"]
    assert agent.mcp_servers[2].transport == raw_agent["mcp-servers"][2]["transport"]
    assert agent.mcp_servers[2].command_line == raw_agent["mcp-servers"][2]["command-line"]
    assert agent.mcp_servers[2].headers is None
    assert agent.mcp_servers[2].env is not None

    assert len(agent.mcp_servers[2].env) == 2
    assert "MCP_API_KEY" in agent.mcp_servers[2].env
    assert "MCP_BEARER_TOKEN" in agent.mcp_servers[2].env
    assert "MCP_API_KEY" in raw_agent["mcp-servers"][2]["env"]
    assert "MCP_BEARER_TOKEN" in raw_agent["mcp-servers"][2]["env"]

    env_api_key_var = agent.mcp_servers[2].env["MCP_API_KEY"]
    raw_env_api_key_var = raw_agent["mcp-servers"][2]["env"]["MCP_API_KEY"]
    env_bearer_token_var = agent.mcp_servers[2].env["MCP_BEARER_TOKEN"]
    raw_env_bearer_token_var = raw_agent["mcp-servers"][2]["env"]["MCP_BEARER_TOKEN"]

    assert isinstance(env_api_key_var, MCPVariableTypeSecret)
    assert env_api_key_var.type == raw_env_api_key_var["type"]
    assert env_api_key_var.description == raw_env_api_key_var["description"]
    assert env_api_key_var.value == raw_env_api_key_var["value"]

    assert isinstance(env_bearer_token_var, MCPVariableTypeOAuth2Secret)
    assert env_bearer_token_var.type == raw_env_bearer_token_var["type"]
    assert env_bearer_token_var.provider == raw_env_bearer_token_var["provider"]
    assert env_bearer_token_var.scopes == raw_env_bearer_token_var["scopes"]
    assert env_bearer_token_var.description == raw_env_bearer_token_var["description"]

    assert agent.selected_tools is not None
    assert agent.selected_tools.tools is not None
    assert len(agent.selected_tools.tools) == 2
    assert agent.selected_tools.tools[0].name == raw_agent["selected-tools"]["tools"][0]["name"]
    assert agent.selected_tools.tools[1].name == raw_agent["selected-tools"]["tools"][1]["name"]


def test_spec_with_docker_gateway() -> None:
    yaml_bytes = b"""\
agent-package:
  spec-version: v2
  agents:
  - name: v2 Agent with Docker MCP Gateway
    description: Agent spec demonstrating docker-mcp-gateway configuration
    model:
      provider: OpenAI
      name: gpt-4o
    version: 3.0.0
    architecture: plan_execute
    reasoning: enabled
    runbook: runbook.md
    action-packages:
    - name: crm-actions
      organization: MyActions
      type: folder
      version: 2.0.0
      whitelist: ""
      path: MyActions/crm-actions
    docker-mcp-gateway:
      catalog: ./custom-catalog.yml
      servers:
        postgres:
          tools: [query, describe]
        slack:
          tools: []
    metadata:
      mode: conversational
"""

    raw = _load_yaml_as_dict(yaml_bytes)["agent-package"]
    raw_agent = raw["agents"][0]

    spec = AgentSpec.from_yaml(yaml_bytes)
    agent = spec.agent_package.agents[0]

    assert spec.agent_package.spec_version == raw["spec-version"]
    assert "exclude" not in raw

    _assert_base_agent_fields(agent, raw_agent)

    assert agent.docker_mcp_gateway is not None

    assert agent.docker_mcp_gateway.catalog == raw_agent["docker-mcp-gateway"]["catalog"]
    assert agent.docker_mcp_gateway.servers is not None
    assert len(agent.docker_mcp_gateway.servers) == 2
    assert agent.docker_mcp_gateway.servers["postgres"].tools is not None
    assert len(agent.docker_mcp_gateway.servers["postgres"].tools) == 2
    assert agent.docker_mcp_gateway.servers["slack"].tools == []


def test_agent_spec_missing_root_key() -> None:
    with pytest.raises(ValidationError):
        AgentSpec.from_yaml(b"spec-version: v2\n")


def test_agent_spec_missing_spec_version() -> None:
    yaml_bytes = b"""
agent-package:
  agents:
  - name: A
    description: B
    model:
      provider: OpenAI
      name: gpt-4o
    version: 1.0.0
    architecture: agent
    reasoning: enabled
    runbook: runbook.md
    action-packages:
    - name: ap
      organization: org
      type: folder
      version: 1.0.0
      whitelist: ""
      path: org/ap
    metadata:
      mode: conversational
"""
    with pytest.raises(ValidationError):
        AgentSpec.from_yaml(yaml_bytes)


def test_agent_spec_missing_agents_list() -> None:
    yaml_bytes = b"""
agent-package:
  spec-version: v2
"""
    with pytest.raises(ValidationError):
        AgentSpec.from_yaml(yaml_bytes)


def test_agent_spec_rejects_multiple_agents() -> None:
    yaml_bytes = b"""
agent-package:
  spec-version: v2
  agents:
  - name: Agent 1
    description: Desc 1
    model:
      provider: OpenAI
      name: gpt-4o
    version: 1.0.0
    architecture: agent
    reasoning: enabled
    runbook: runbook.md
    action-packages:
    - name: ap
      organization: org
      type: folder
      version: 1.0.0
      whitelist: ""
      path: org/ap
    metadata:
      mode: conversational
  - name: Agent 2
    description: Desc 2
    model:
      provider: OpenAI
      name: gpt-4o
    version: 1.0.0
    architecture: agent
    reasoning: enabled
    runbook: runbook.md
    action-packages:
    - name: ap
      organization: org
      type: folder
      version: 1.0.0
      whitelist: ""
      path: org/ap
    metadata:
      mode: conversational
"""
    with pytest.raises(ValueError, match="single Agent definition only"):
        AgentSpec.from_yaml(yaml_bytes)


def test_spec_from_yaml_ignores_unknown_fields() -> None:
    """
    from_yaml should be permissive and not fail when extra/unknown keys are present in YAML.
    """
    yaml_bytes = b"""\
agent-package:
  spec-version: v2
  unknown-root-field: should-be-ignored
  agents:
  - name: Agent With Unknown Fields
    description: Unknown fields should not break parsing
    version: 1.0.0
    action-packages: []
    unknown-agent-field: 123
    model:
      provider: OpenAI
      name: gpt-4o
      unknown-model-field: ignored
"""

    spec = AgentSpec.from_yaml(yaml_bytes)
    agent = spec.agent_package.agents[0]

    assert spec.agent_package.spec_version == "v2"
    assert agent.name == "Agent With Unknown Fields"
    assert agent.description == "Unknown fields should not break parsing"
    assert agent.version == "1.0.0"
    assert agent.action_packages == []
    assert agent.model is not None
    assert agent.model.provider == "OpenAI"
    assert agent.model.name == "gpt-4o"
