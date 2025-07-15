import json
import os
from pathlib import Path

import pytest

from _spec_validation_tests._spec_validation import InvalidSpec, validate_from_spec


DOCS_DIR = Path(__file__).parent.parent.parent / "versions"
assert os.path.exists(DOCS_DIR), f"Expected docs dir to exist. Found {DOCS_DIR}"


@pytest.fixture(scope="session")
def v3_spec():
    specs_found = list(DOCS_DIR.glob("**/v3/agent-package-specification-v3.json"))
    assert len(specs_found) == 1, f"Expected exactly one spec file. Found {specs_found}"

    json_spec_path = next(iter(specs_found))
    spec = json.loads(json_spec_path.read_text())
    return spec


@pytest.fixture
def _gen_runbook(datadir: Path):
    (datadir / "runbook.md").write_text("")


@pytest.fixture
def _gen_action_package_files(datadir: Path):
    (datadir / "runbook.md").write_text("")
    (datadir / "actions" / "Sema4.ai" / "browsing").mkdir(parents=True)
    (datadir / "actions" / "Sema4.ai" / "browsing" / "1.0.1.zip").write_text("")
    (datadir / "actions" / "MyActions" / "another" / "my-action").mkdir(parents=True)


@pytest.mark.usefixtures("_gen_runbook")
def test_spec_validation_ok(datadir: Path, v3_spec: dict):
    from ._spec_validation import load_spec

    valid_yaml = """
agent-package:
  spec-version: v3
  agents: # agents node
    - name: Agent1
      description: This is the description
      version: 0.0.1
      model:
        provider: OpenAI
        name: GPT 4o
      architecture: plan_execute
      reasoning: enabled
      runbook: runbook.md
      action-packages: []  # action-packages node
      knowledge: []
      metadata:
        mode: conversational
    """

    validate_from_spec(load_spec(v3_spec), valid_yaml, datadir)


def test_spec_validation_missing_required(datadir: Path, v3_spec: dict, data_regression):
    from _spec_validation_tests._spec_validation import load_spec

    bad_yaml = """
agent-package:
  spec-version: v3
  agents: # Defines the agents available
    - description: This is the description # Description for the agent (any string)
      metadata:
        mode: conversational
    """

    errors = validate_from_spec(load_spec(v3_spec), bad_yaml, datadir, raise_on_error=False)
    assert errors, "Expected errors"
    errors_str = [e.message for e in errors]
    assert "Missing required entry: agent-package/agents/name." in errors_str
    data_regression.check(errors_str)


def test_yaml_categorization(datadir: Path, v3_spec: dict, data_regression):
    import sys
    from contextlib import redirect_stdout
    from io import StringIO

    from _spec_validation_tests._spec_validation import Validator, load_spec

    bad_yaml = """
object:
  key1: str_value
  key2:
    - list-item: 1
    - list-item: 2
    - another-item: 3
    - foo:
      - a: 1
      - b: "2"
      - c: '2'
  key3:
    attr1: true
    attr2: a, b
    attr3: 122
    attr4: 1.2
    attr5: [a, b]
    """

    sio = StringIO()
    sys.stdout = sio
    with redirect_stdout(sio):
        Validator.PRINT_YAML_TREE = True
        try:
            _errors = validate_from_spec(
                load_spec(v3_spec), bad_yaml, datadir, raise_on_error=False
            )
        finally:
            Validator.PRINT_YAML_TREE = False
    yaml_tree = sio.getvalue()
    data_regression.check(yaml_tree.splitlines(keepends=False))


def test_spec_validation_not_a_list(datadir: Path, v3_spec: dict):
    from _spec_validation_tests._spec_validation import load_spec

    bad_yaml = """
agent-package:
  spec-version: v3
  agents: # Defines the agents available
    description: This is not a list, just an attribute in an object...
    """

    errors = validate_from_spec(load_spec(v3_spec), bad_yaml, datadir, raise_on_error=False)
    assert errors, "Expected errors"
    errors_str = [e.message for e in errors]
    assert ["Expected agent-package/agents to be a list."] == errors_str


@pytest.mark.usefixtures("_gen_runbook")
def test_spec_validation_not_string(datadir: Path, v3_spec: dict, data_regression):
    from _spec_validation_tests._spec_validation import load_spec

    bad_yaml = """
agent-package: # Root element
  spec-version: v3 # The version of the spec being used
  agents: # Defines the agents available
    - name: Agent1
      description: This is the description # Description for the agent (any string)
      version: 1
      model:
        provider: OpenAI
        name: GPT 4o
      architecture: plan_execute
      reasoning: enabled
      runbook: runbook.md
      action-packages: []
      knowledge: []
      metadata:
        mode: conversational
    """

    errors = validate_from_spec(load_spec(v3_spec), bad_yaml, datadir, raise_on_error=False)
    assert errors, "Expected errors"
    errors_str = [e.message for e in errors]
    data_regression.check(errors_str)


@pytest.mark.usefixtures("_gen_runbook")
def test_spec_validation_not_in_enum(datadir: Path, v3_spec: dict, data_regression):
    from _spec_validation_tests._spec_validation import load_spec

    bad_yaml = """
agent-package: # Root element
  spec-version: v3 # The version of the spec being used
  agents: # Defines the agents available
    - name: Agent1
      description: This is the description # Description for the agent (any string)
      version: '0.0.1'
      model:
        provider: OpenAI
        name: GPT 4o
      architecture: not-defined
      reasoning: enabled
      runbook: runbook.md
      action-packages: []
      knowledge: []
      metadata:
        mode: conversational
    """

    errors = validate_from_spec(load_spec(v3_spec), bad_yaml, datadir, raise_on_error=False)
    assert errors, "Expected errors"
    errors_str = [e.message for e in errors]
    data_regression.check(errors_str)


def test_spec_validation_no_file(datadir: Path, v3_spec: dict, data_regression):
    from _spec_validation_tests._spec_validation import load_spec

    bad_yaml = """
agent-package: # Root element
  spec-version: v3 # The version of the spec being used
  agents: # Defines the agents available
    - name: Agent1
      description: This is the description # Description for the agent (any string)
      version: '0.0.1'
      model:
        provider: OpenAI
        name: GPT 4o
      architecture: agent
      reasoning: enabled
      runbook: no-runbook.md
      action-packages: []
      knowledge:
        - name: knowledge-file.txt
          embedded: true
      metadata:
        mode: conversational
    """

    errors = validate_from_spec(load_spec(v3_spec), bad_yaml, datadir, raise_on_error=False)
    assert errors, "Expected errors"
    errors_str = [e.message for e in errors]
    data_regression.check(errors_str)

    (datadir / "no-runbook.md").write_text("")
    (datadir / "knowledge").mkdir()
    (datadir / "knowledge" / "knowledge-file.txt").write_text("")

    errors = validate_from_spec(load_spec(v3_spec), bad_yaml, datadir, raise_on_error=True)


@pytest.mark.usefixtures("_gen_action_package_files", "_gen_runbook")
def test_spec_validation_multiple_action_packages(
    datadir: Path,
    v3_spec: dict,
    data_regression,
):
    from _spec_validation_tests._spec_validation import load_spec

    bad_yaml = r"""
agent-package: # Root element
  spec-version: v3 # The version of the spec being used
  agents: # Defines the agents available
    - name: Agent1
      description: This is the description # Description for the agent (any string)
      version: '0.0.1'
      model:
        provider: OpenAI
        name: GPT 4o
      architecture: agent
      reasoning: enabled
      runbook: runbook.md
      metadata:
        mode: conversational
      action-packages:
        - name: Browsing
          organization: Sema4.ai
          type: err # Bad value
          version: 1.0.1
          whitelist: get_website_content,download_file
          path: Sema4.ai/browsing/1.0.1.zip
        - name: MyAction
          organization: MyActions
          type: folder
          version: 22.0.1
          whitelist: 1 # Bad value
          path: MyActions/another/my-action
      # Note: no knowledge node (should be ok as it's not marked as required)
    """
    errors = validate_from_spec(load_spec(v3_spec), bad_yaml, datadir, raise_on_error=False)
    assert errors, "Expected errors"
    errors_str = [e.message for e in errors]
    data_regression.check(errors_str)


@pytest.mark.usefixtures("_gen_runbook")
def test_spec_validation_deprecated(datadir: Path, v3_spec: dict, data_regression):
    from _spec_validation_tests._spec_validation import load_spec

    bad_yaml = """
agent-package:
  spec-version: v3
  agents: # agents node
    - name: Agent1
      type: agent # deprecated
      description: This is the description
      metadata:
        mode: conversational
      version: 0.0.1
      model:
        provider: OpenAI
        name: GPT 4o
      architecture: plan_execute
      reasoning: enabled
      runbook: runbook.md
      runbooks:
        system: runbook.md
        retrieval: runbook.md
      action-packages: []
      knowledge: []
      resources: [] # deprecated
      reasoningLevel: 1 # deprecated
    """
    errors = validate_from_spec(load_spec(v3_spec), bad_yaml, datadir, raise_on_error=False)

    assert errors, "Expected errors"
    errors_str = [e.message for e in errors]
    data_regression.check(errors_str)

    data_regression.check(
        [e.as_diagostic(None) for e in errors],
        basename="test_spec_validation_deprecated_as_diagnostics",
    )


@pytest.mark.usefixtures("_gen_runbook")
def test_spec_validation_mcp_servers_ok(datadir: Path, v3_spec: dict):
    from _spec_validation_tests._spec_validation import load_spec

    valid_yaml = """
agent-package:
  spec-version: v3
  agents:
    - name: Agent1
      description: This is the description
      version: 0.0.1
      model:
        provider: OpenAI
        name: GPT 4o
      architecture: plan_execute
      reasoning: enabled
      runbook: runbook.md
      action-packages: []
      knowledge: []
      metadata:
        mode: conversational
      mcp-servers:
        - name: mcp-server-1
          transport: streamable-http
          description: MCP Server 1 (description of the server, user could add instructions to configure here).
          url: http://localhost:8000
          headers:
            Authorization:
              type: oauth2-secret
              description: Your OAuth2 API key for authentication
              provider: Microsoft
              scopes:
                - user.read
                - user.write
            Content-Type:
              type: string
              description: Content type header
              default: application/json
          force-serial-tool-calls: false
        - name: mcp-server-2
          transport: stdio
          description: MCP Server 2 for stdio transport.
          command-line: ['uv', 'run', 'python', '-m', 'my-server']
          env:
            API_KEY:
              type: secret
              description: Your API key for authentication
            DATABASE_URL:
              type: string
              description: Database connection URL
              default: postgresql://localhost:5432/mydb
          cwd: ./mcp-server/path
          force-serial-tool-calls: true
        - name: mcp-server-3
          transport: sse
          description: MCP Server 3 for SSE transport.
          url: http://localhost:9000
          headers:
            X-API-Key:
              type: secret
              description: Your API key for authentication
    """

    validate_from_spec(load_spec(v3_spec), valid_yaml, datadir)


@pytest.mark.usefixtures("_gen_runbook")
def test_spec_validation_mcp_servers_headers_bad_type(
    datadir: Path, v3_spec: dict, data_regression
):
    from _spec_validation_tests._spec_validation import load_spec

    valid_yaml = """
agent-package:
  spec-version: v3
  agents:
    - name: Agent1
      description: This is the description
      version: 0.0.1
      model:
        provider: OpenAI
        name: GPT 4o
      architecture: plan_execute
      reasoning: enabled
      runbook: runbook.md
      action-packages: []
      knowledge: []
      metadata:
        mode: conversational
      mcp-servers:
        - name: mcp-server-1
          transport: streamable-http
          description: MCP Server 1 (description of the server, user could add instructions to configure here).
          url: http://localhost:8000
          headers:
            Authorization:
              type: oauth2-secret
              description: Your OAuth2 API key for authentication
              provider: Microsoft
              scopes:
                - user.read
                - user.write
            Content-Type:
              type: wrong-type-in-header
              description: Content type header
              default: application/json
          force-serial-tool-calls: false
        - name: mcp-server-2
          transport: stdio
          description: MCP Server 2 for stdio transport.
          command-line: ['uv', 'run', 'python', '-m', 'my-server']
          env:
            API_KEY:
              type: secret
              description: Your API key for authentication
            DATABASE_URL:
              type: wrong-type-in-env
              description: Database connection URL
              default: postgresql://localhost:5432/mydb
          cwd: ./mcp-server/path
          force-serial-tool-calls: true
        - name: mcp-server-3
          transport: sse
          description: MCP Server 3 for SSE transport.
          url: http://localhost:9000
          headers:
            X-API-Key:
              type: secret
              description: Your API key for authentication
    """

    errors = validate_from_spec(load_spec(v3_spec), valid_yaml, datadir, raise_on_error=False)
    assert errors, "Expected errors"
    errors_str = [e.message for e in errors]
    data_regression.check(errors_str)


@pytest.mark.usefixtures("_gen_runbook")
def test_spec_validation_mcp_servers_missing_required(
    datadir: Path, v3_spec: dict, data_regression
):
    from _spec_validation_tests._spec_validation import load_spec

    bad_yaml = """
agent-package:
  spec-version: v3
  agents:
    - name: Agent1
      description: This is the description
      version: 0.0.1
      model:
        provider: OpenAI
        name: GPT 4o
      architecture: plan_execute
      reasoning: enabled
      runbook: runbook.md
      action-packages: []
      knowledge: []
      metadata:
        mode: conversational
      mcp-servers:
        - transport: streamable-http
          url: http://localhost:8000
          # error: name required
        - name: mcp-server-2
          description: Missing transport
        - name: mcp-server-3
          transport: stdio
          # Missing description (ok as it's not required)
    """

    errors = validate_from_spec(load_spec(v3_spec), bad_yaml, datadir, raise_on_error=False)
    assert errors, "Expected errors"
    errors_str = [e.message for e in errors]
    data_regression.check(errors_str)


@pytest.mark.usefixtures("_gen_runbook")
def test_spec_validation_mcp_servers_invalid_transport(
    datadir: Path, v3_spec: dict, data_regression
):
    from _spec_validation_tests._spec_validation import load_spec

    bad_yaml = """
agent-package:
  spec-version: v3
  agents:
    - name: Agent1
      description: This is the description
      version: 0.0.1
      model:
        provider: OpenAI
        name: GPT 4o
      architecture: plan_execute
      reasoning: enabled
      runbook: runbook.md
      action-packages: []
      knowledge: []
      metadata:
        mode: conversational
      mcp-servers:
        - name: mcp-server-1
          transport: invalid-transport
          description: MCP Server with invalid transport
        - name: mcp-server-2
          transport: websocket # also currently not supported
          description: MCP Server with another invalid transport
    """

    errors = validate_from_spec(load_spec(v3_spec), bad_yaml, datadir, raise_on_error=False)
    assert errors, "Expected errors"
    errors_str = [e.message for e in errors]
    data_regression.check(errors_str)


@pytest.mark.usefixtures("_gen_runbook")
def test_spec_validation_mcp_servers_missing_url_for_http(
    datadir: Path, v3_spec: dict, data_regression
):
    from _spec_validation_tests._spec_validation import load_spec

    bad_yaml = """
agent-package:
  spec-version: v3
  agents:
    - name: Agent1
      description: This is the description
      version: 0.0.1
      model:
        provider: OpenAI
        name: GPT 4o
      architecture: plan_execute
      reasoning: enabled
      runbook: runbook.md
      action-packages: []
      knowledge: []
      metadata:
        mode: conversational
      mcp-servers:
        - name: mcp-server-1
          transport: streamable-http
          description: MCP Server missing URL
          headers:
            Authorization:
              type: oauth2-secret
              description: Your OAuth2 API key for authentication
              provider: Microsoft
              scopes:
                - user.read
                - user.write
        - name: mcp-server-2
          transport: sse
          description: MCP Server missing URL for SSE
    """

    errors = validate_from_spec(load_spec(v3_spec), bad_yaml, datadir, raise_on_error=False)
    assert errors, "Expected errors"
    errors_str = [e.message for e in errors]
    data_regression.check(errors_str)


@pytest.mark.usefixtures("_gen_runbook")
def test_spec_validation_mcp_servers_missing_command_line_for_stdio(
    datadir: Path, v3_spec: dict, data_regression
):
    from _spec_validation_tests._spec_validation import load_spec

    bad_yaml = """
agent-package:
  spec-version: v3
  agents:
    - name: Agent1
      description: This is the description
      version: 0.0.1
      model:
        provider: OpenAI
        name: GPT 4o
      architecture: plan_execute
      reasoning: enabled
      runbook: runbook.md
      action-packages: []
      knowledge: []
      metadata:
        mode: conversational
      mcp-servers:
        - name: mcp-server-1
          transport: stdio
          description: MCP Server missing command-line
          required-env-vars: ['API_KEY']
          cwd: ./mcp-server/path
    """

    errors = validate_from_spec(load_spec(v3_spec), bad_yaml, datadir, raise_on_error=False)
    assert errors, "Expected errors"
    errors_str = [e.message for e in errors]
    data_regression.check(errors_str)


@pytest.mark.usefixtures("_gen_runbook")
def test_spec_validation_mcp_servers_invalid_headers_format(
    datadir: Path, v3_spec: dict, data_regression
):
    from _spec_validation_tests._spec_validation import load_spec

    bad_yaml = """
agent-package:
  spec-version: v3
  agents:
    - name: Agent1
      description: This is the description
      version: 0.0.1
      model:
        provider: OpenAI
        name: GPT 4o
      architecture: plan_execute
      reasoning: enabled
      runbook: runbook.md
      action-packages: []
      knowledge: []
      metadata:
        mode: conversational
      mcp-servers:
        - name: mcp-server-1
          transport: streamable-http
          description: MCP Server with invalid headers format
          url: http://localhost:8000
          headers: "not-a-dict"
        - name: mcp-server-2
          transport: sse
          description: MCP Server with invalid headers content
          url: http://localhost:9000
          headers:
            123: "valid-header"
    """

    errors = validate_from_spec(load_spec(v3_spec), bad_yaml, datadir, raise_on_error=False)
    assert errors, "Expected errors"
    errors_str = [e.message for e in errors]
    data_regression.check(errors_str)


@pytest.mark.usefixtures("_gen_runbook")
def test_spec_validation_mcp_servers_invalid_command_line_format(
    datadir: Path, v3_spec: dict, data_regression
):
    from _spec_validation_tests._spec_validation import load_spec

    bad_yaml = """
agent-package:
  spec-version: v3
  agents:
    - name: Agent1
      description: This is the description
      version: 0.0.1
      model:
        provider: OpenAI
        name: GPT 4o
      architecture: plan_execute
      reasoning: enabled
      runbook: runbook.md
      action-packages: []
      knowledge: []
      metadata:
        mode: conversational
      mcp-servers:
        - name: mcp-server-1
          transport: stdio
          description: MCP Server with invalid command-line format
          command-line: "not-a-list"
        - name: mcp-server-2
          transport: stdio
          description: MCP Server with invalid command-line content
          command-line: [123, "python", "-m", "server"]
    """

    errors = validate_from_spec(load_spec(v3_spec), bad_yaml, datadir, raise_on_error=False)
    assert errors, "Expected errors"
    errors_str = [e.message for e in errors]
    data_regression.check(errors_str)


@pytest.mark.usefixtures("_gen_runbook")
def test_spec_validation_mcp_servers_invalid_env_vars_format(
    datadir: Path, v3_spec: dict, data_regression
):
    from _spec_validation_tests._spec_validation import load_spec

    bad_yaml = """
agent-package:
  spec-version: v3
  agents:
    - name: Agent1
      description: This is the description
      version: 0.0.1
      model:
        provider: OpenAI
        name: GPT 4o
      architecture: plan_execute
      reasoning: enabled
      runbook: runbook.md
      action-packages: []
      knowledge: []
      metadata:
        mode: conversational
      mcp-servers:
        - name: mcp-server-1
          transport: stdio
          description: MCP Server with invalid env vars format
          command-line: ['python', '-m', 'server']
          env: "not-a-dict"
        - name: mcp-server-2
          transport: stdio
          description: MCP Server with invalid env vars content
          command-line: ['python', '-m', 'server']
          env: {123: "API_KEY"}
    """

    errors = validate_from_spec(load_spec(v3_spec), bad_yaml, datadir, raise_on_error=False)
    assert errors, "Expected errors"
    errors_str = [e.message for e in errors]
    data_regression.check(errors_str)


@pytest.mark.usefixtures("_gen_runbook")
def test_spec_validation_mcp_servers_invalid_cwd_format(
    datadir: Path, v3_spec: dict, data_regression
):
    from _spec_validation_tests._spec_validation import load_spec

    bad_yaml = """
agent-package:
  spec-version: v3
  agents:
    - name: Agent1
      description: This is the description
      version: 0.0.1
      model:
        provider: OpenAI
        name: GPT 4o
      architecture: plan_execute
      reasoning: enabled
      runbook: runbook.md
      action-packages: []
      knowledge: []
      metadata:
        mode: conversational
      mcp-servers:
        - name: mcp-server-1
          transport: stdio
          description: MCP Server with invalid cwd format
          command-line: ['python', '-m', 'server']
          cwd: 123
        - name: mcp-server-2
          transport: stdio
          description: MCP Server with invalid cwd content
          command-line: ['python', '-m', 'server']
          cwd: ["./path"]
    """

    errors = validate_from_spec(load_spec(v3_spec), bad_yaml, datadir, raise_on_error=False)
    assert errors, "Expected errors"
    errors_str = [e.message for e in errors]
    data_regression.check(errors_str)


@pytest.mark.usefixtures("_gen_runbook")
def test_spec_validation_mcp_servers_invalid_force_serial_tool_calls_format(
    datadir: Path, v3_spec: dict, data_regression
):
    from _spec_validation_tests._spec_validation import load_spec

    bad_yaml = """
agent-package:
  spec-version: v3
  agents:
    - name: Agent1
      description: This is the description
      version: 0.0.1
      model:
        provider: OpenAI
        name: GPT 4o
      architecture: plan_execute
      reasoning: enabled
      runbook: runbook.md
      action-packages: []
      knowledge: []
      metadata:
        mode: conversational
      mcp-servers:
        - name: mcp-server-1
          transport: streamable-http
          description: MCP Server with invalid force-serial-tool-calls format
          url: http://localhost:8000
          force-serial-tool-calls: "not-a-boolean"
        - name: mcp-server-2
          transport: stdio
          description: MCP Server with invalid force-serial-tool-calls content
          command-line: ['python', '-m', 'server']
          force-serial-tool-calls: 123
    """

    errors = validate_from_spec(load_spec(v3_spec), bad_yaml, datadir, raise_on_error=False)
    assert errors, "Expected errors"
    errors_str = [e.message for e in errors]
    data_regression.check(errors_str)


@pytest.mark.usefixtures("_gen_runbook")
def test_spec_validation_bad_oauth2_secret_type(datadir: Path, v3_spec: dict, data_regression):
    from _spec_validation_tests._spec_validation import load_spec

    bad_yaml = """
agent-package:
  spec-version: v3
  agents:
    - name: Agent1
      description: This is the description
      version: 0.0.1
      model:
        provider: OpenAI
        name: GPT 4o
      architecture: plan_execute
      reasoning: enabled
      runbook: runbook.md
      action-packages: []
      knowledge: []
      metadata:
        mode: conversational
      mcp-servers:
        - name: mcp-server-1
          transport: streamable-http
          description: MCP Server with invalid oauth2-secret type
          url: http://localhost:8000
          headers:
            Authorization:
              type: oauth2-secret
              description: Your OAuth2 API key for authentication
              missing-provider: Microsoft
              missing-scopes: 11
            A-secret:
              type: secret
              description: Your secret
              default: "secret"
              provider: "not-allowed"
              scopes:
                - not-allowed
            A-string:
              type: string
              description: Your string
              default: "string"
              provider: "not-allowed"
              scopes:
                - not-allowed
            A-data-server-info:
              type: data-server-info
              description: Your data-server-info
              default: "not-allowed"
              provider: "not-allowed"
              scopes:
                - not-allowed
    """

    errors = validate_from_spec(load_spec(v3_spec), bad_yaml, datadir, raise_on_error=False)
    assert errors, "Expected errors"
    errors_str = [e.message for e in errors]
    data_regression.check(errors_str)


@pytest.mark.usefixtures("_gen_runbook")
def test_spec_validation_mcp_servers_unexpected_fields(
    datadir: Path, v3_spec: dict, data_regression
):
    from _spec_validation_tests._spec_validation import load_spec

    bad_yaml = """
agent-package:
  spec-version: v3
  agents:
    - name: Agent1
      description: This is the description
      version: 0.0.1
      model:
        provider: OpenAI
        name: GPT 4o
      architecture: plan_execute
      reasoning: enabled
      runbook: runbook.md
      action-packages: []
      knowledge: []
      metadata:
        mode: conversational
      mcp-servers:
        - name: mcp-server-1
          transport: streamable-http
          description: MCP Server with unexpected fields
          url: http://localhost:8000
          unexpected_field: "should not be here"
          another_unexpected: 123
        - name: mcp-server-2
          transport: stdio
          description: MCP Server with more unexpected fields
          command-line: ['python', '-m', 'server']
          invalid_property: "should not exist"
    """

    errors = validate_from_spec(load_spec(v3_spec), bad_yaml, datadir, raise_on_error=False)
    assert errors, "Expected errors"
    errors_str = [e.message for e in errors]
    data_regression.check(errors_str)


@pytest.mark.usefixtures("_gen_runbook")
def test_spec_validation_mcp_servers_mixed_transport_configurations(
    datadir: Path, v3_spec: dict, data_regression
):
    from _spec_validation_tests._spec_validation import load_spec

    bad_yaml = """
agent-package:
  spec-version: v3
  agents:
    - name: Agent1
      description: This is the description
      version: 0.0.1
      model:
        provider: OpenAI
        name: GPT 4o
      architecture: plan_execute
      reasoning: enabled
      runbook: runbook.md
      action-packages: []
      knowledge: []
      metadata:
        mode: conversational
      mcp-servers:
        - name: mcp-server-1
          transport: streamable-http
          description: MCP Server with stdio fields
          url: http://localhost:8000
          command-line: ['python', '-m', 'server']  # Should not be here for http
          wrong-required-env-vars: ['API_KEY']  # Should not be here for http
        - name: mcp-server-2
          transport: stdio
          description: MCP Server with http fields
          command-line: ['python', '-m', 'server']
          url: http://localhost:8000  # Should not be here for stdio
          headers:
            Authorization:
              type: oauth2-secret
              description: Your OAuth2 API key for authentication
              provider: Microsoft
              scopes:
                - user.read
                - user.write
    """

    errors = validate_from_spec(load_spec(v3_spec), bad_yaml, datadir, raise_on_error=False)
    assert errors, "Expected errors"
    errors_str = [e.message for e in errors]
    data_regression.check(errors_str)


@pytest.mark.usefixtures("_gen_runbook")
def test_spec_bad_conversation_guide(datadir: Path, v3_spec: dict, data_regression):
    from _spec_validation_tests._spec_validation import load_spec

    bad_yaml = """
agent-package:
  spec-version: v3
  agents:
    - name: Agent1
      description: This is the description
      version: 0.0.1
      model:
        provider: OpenAI
        name: GPT 4o
      architecture: plan_execute
      reasoning: enabled
      runbook: runbook.md
      action-packages: []
      knowledge: []
      metadata:
        mode: conversational
      conversation-guide: "not-a-file"
    """

    errors = validate_from_spec(load_spec(v3_spec), bad_yaml, datadir, raise_on_error=False)
    assert errors, "Expected errors"
    errors_str = [e.message for e in errors]
    data_regression.check(errors_str)


def test_spec():
    from _spec_validation_tests._spec_validation import load_spec

    specs_found = DOCS_DIR.glob("**/agent-package-specification*.json")
    for json_spec_path in specs_found:
        spec = json.loads(json_spec_path.read_text())

        for yaml_spec_path in json_spec_path.parent.glob("**/agent-spec*.yaml"):
            yaml_agent_spec_contents = yaml_spec_path.read_text()
            try:
                validate_from_spec(
                    load_spec(spec),
                    yaml_agent_spec_contents,
                    yaml_spec_path.parent,
                    raise_on_error=True,
                )
            except InvalidSpec as e:
                raise Exception(
                    f"Invalid spec: {yaml_spec_path} does not match {json_spec_path}"
                ) from e
