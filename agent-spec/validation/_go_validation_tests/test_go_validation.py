import logging
from pathlib import Path
from typing import Literal

import pytest

from _go_validation_tests.fixtures import RunResult
from pytest_regressions.data_regression import DataRegressionFixture

log = logging.getLogger(__name__)


def run_agent_cli(
    agent_cli: Path, args: list[str], cwd: Path, env: dict[str, str] | None = None
) -> RunResult:
    import os

    from _go_validation_tests.fixtures import DEBUG_GO, run

    if DEBUG_GO:
        full_args = [
            "dlv",
            "exec",
            str(agent_cli),
            "--listen=127.0.0.1:59000",
            "--allow-non-terminal-interactive=true",
            "--headless=true",
            "--",
        ]
    else:
        full_args = [str(agent_cli)]
    full_args.extend(args)

    use_env = os.environ.copy()
    if env:
        use_env.update(env)
    contents = run(full_args, cwd=cwd, env=use_env)
    return contents


def test_go_list_action_packages_from_agent(agent_cli: Path, datadir, data_regression):
    import json

    agent_dir = datadir / "agent2"
    contents = run_agent_cli(agent_cli, ["list-action-packages", "."], cwd=agent_dir)
    assert contents.returncode == 0
    actions = json.loads(contents.stdout)
    data_regression.check(actions)


def bad_format(agent_path):
    agent_spec = agent_path / "agent-spec.yaml"
    agent_spec.write_text(
        """
agent-package:
  spec-version: v1
  agents
"""
    )


@pytest.mark.parametrize("scenario", ["nested", "flat"])
def test_go_print_spec(agent_cli: Path, datadir, data_regression, scenario, str_regression):
    import json

    agent_dir = datadir / "agent2"
    additional_args = ["--nested"] if scenario == "nested" else []
    run_result = run_agent_cli(
        agent_cli, ["validate", "--show-spec", *additional_args], cwd=agent_dir
    )
    assert run_result.returncode == 0, str(run_result)
    if scenario == "nested":
        found = run_result.stdout
        str_regression.check(found)
    else:
        try:
            found = json.loads(run_result.stdout)
        except Exception as exc:
            raise Exception(f"Failed to parse stdout as JSON: {run_result.stdout!r}") from exc
        data_regression.check(found)


def _update_spec(agent_path, replace_func):
    agent_spec = agent_path / "agent-spec.yaml"
    txt = agent_spec.read_text()
    agent_spec.write_text(replace_func(txt))


def no_spec_version(agent_path):
    _update_spec(agent_path, lambda txt: txt.replace("spec-version: v1", ""))


def bad_spec_version(agent_path):
    _update_spec(agent_path, lambda txt: txt.replace("spec-version: v2", "spec-version: 22"))


def v2_bad_architecture(agent_path):
    _update_spec(
        agent_path,
        lambda txt: txt.replace("architecture: plan_execute", "architecture: bad-architecture"),
    )


def ok(agent_path):
    pass


def only_zip_mode_wrong(agent_path):
    pass


def no_agents_section(agent_path):
    agent_spec = agent_path / "agent-spec.yaml"
    txt = agent_spec.read_text()
    agent_spec.write_text(txt.replace("agents:", "no-agents:"))


def empty_agents(agent_path):
    agent_spec = agent_path / "agent-spec.yaml"
    txt = agent_spec.read_text()
    agent_spec.write_text(txt.replace("agents:", "agents: []\n  no-agents:"))


def bad_agent_items(agent_path):
    agent_spec = agent_path / "agent-spec.yaml"
    txt = agent_spec.read_text()
    agent_spec.write_text(txt.replace("reasoning: enabled", "no-reasoning: 'bad'"))


def v2_bad_type(agent_path):
    agent_spec = agent_path / "agent-spec.yaml"
    update(agent_spec, lambda txt: txt.replace("type: zip", "type: folder"))


def v2_bad_action_package_version(agent_path):
    package_yaml = (
        agent_path / "actions" / "MyActions" / "control-room-test" / "0.0.1" / "package.yaml"
    )
    txt = package_yaml.read_text()
    package_yaml.write_text(txt.replace("version: 0.0.1", "version: 1.1.1"))


def update(package_yaml, replace_func):
    txt = package_yaml.read_text()
    new = replace_func(txt)
    if txt == new:
        raise RuntimeError(
            f"Applying the replacement function on {package_yaml} did not change the file. Contents:\n{txt}"
        )
    package_yaml.write_text(new)


def v2_bad_action_package_name(agent_path):
    package_yaml = agent_path / "agent-spec.yaml"

    update(
        package_yaml,
        lambda txt: txt.replace("name: Control Room Test", "name: Some other name"),
    )


def v2_unreferenced_action_package(agent_path):
    import shutil

    zip_path = agent_path / "actions" / "MyActions" / "control-room-test" / "0.0.1" / "0.0.1.zip"
    new_zip_path = (
        agent_path / "actions" / "MyActions" / "control-room-test" / "0.0.1" / "new-path.zip"
    )
    shutil.move(zip_path, new_zip_path)


def check(  # noqa: PLR0913
    agent_name: str,
    datadir,
    scenario,
    data_regression,
    agent_cli: Path,
    returncode: int,
    action_server: Path,
    check: Literal["only_zip", "only_dir", "both"],
) -> None:
    import json
    import os
    import re

    agent_path = Path(datadir) / agent_name

    scenario(agent_path)

    if check in ["only_dir", "both"]:
        run_result = run_agent_cli(
            agent_cli, ["validate", str(agent_path), "--json"], cwd=agent_path
        )

        assert run_result.returncode == returncode, (
            f"Expected returncode {returncode}, but got {run_result.returncode}\n"
            f"stdout: {run_result.stdout}\n"
            f"stderr: {run_result.stderr}"
        )
        try:
            data = json.loads(run_result.stdout)
        except Exception as exc:
            raise Exception(
                f"Failed to parse stdout as json.\n"
                f"stdout: {run_result.stdout}\n"
                f"stderr: {run_result.stderr}"
            ) from exc
        data_regression.check(data)

        run_result_txt = run_agent_cli(agent_cli, ["validate", str(agent_path)], cwd=agent_path)

        assert run_result_txt.returncode == returncode, (
            f"Expected returncode {returncode}. Found:\n{run_result_txt}"
        )

        # Go through the output and match to Error at line: <line-number>: <message>
        found = []
        for line in run_result_txt.stdout.splitlines():
            if line.startswith("Error at line:"):
                regex = r"Error at line: (\d+): (.+)"
                match = re.match(regex, line)
                if match:
                    line_number = int(match.group(1))
                    message = match.group(2)
                    found.append({"line": line_number, "message": message})
        assert len(found) == len(data), (
            f"Expected {len(data)} errors, but found {len(found)}:\n{run_result_txt}"
        )

    if check in ["only_dir"]:
        return

    # Now, zip up the agent_path and try with the zip file
    run_result = run_agent_cli(
        agent_cli,
        [
            "package",
            "build",
            "--input-dir",
            str(agent_path),
            "--verbose",
            "--output-dir",
            str(agent_path.parent),
            "--name",
            "built-agent.zip",
            "--overwrite",
        ],
        cwd=agent_path,
        env={"ACTION_SERVER_BIN_PATH": f"{action_server!s}"},
    )
    assert run_result.returncode == 0, (
        f"Expected returncode {0}, but got {run_result.returncode}\n"
        f"stdout: {run_result.stdout}\n"
        f"stderr: {run_result.stderr}"
    )

    zip_path = agent_path.parent / "built-agent.zip"
    assert os.path.exists(zip_path)

    # Print agent-spec.yaml from the zip file

    run_result = run_agent_cli(agent_cli, ["validate", str(zip_path), "--json"], cwd=agent_path)

    assert run_result.returncode == returncode, (
        f"Expected returncode {returncode}, but got {run_result.returncode}\n{run_result}"
    )
    try:
        data_zip = json.loads(run_result.stdout)
    except Exception as exc:
        raise Exception(f"Failed to parse stdout as json.\n{run_result}") from exc
    data_regression.check(data_zip, basename=scenario.__name__ + "_zip")


@pytest.mark.parametrize(
    "scenario",
    [
        ok,
        bad_spec_version,
        bad_agent_items,
        v2_bad_architecture,
        v2_bad_action_package_version,
        v2_bad_action_package_name,
    ],
)
def test_agent_spec_analysis(
    datadir, scenario, data_regression, agent_cli: Path, action_server: Path
) -> None:
    do_check: Literal["both", "only_dir", "only_zip"]
    do_check = "both"

    check(
        "agent2",
        datadir,
        scenario,
        data_regression,
        agent_cli,
        returncode=0 if scenario is ok else 1,
        action_server=action_server,
        check=do_check,
        # check="only_dir",
        # check="only_zip",
    )


@pytest.mark.parametrize(
    "scenario",
    [
        only_zip_mode_wrong,
        v2_bad_type,
        v2_bad_action_package_name,
        v2_unreferenced_action_package,
    ],
)
def test_agent_spec_analysis_v2_agent3(
    datadir, scenario, data_regression, agent_cli: Path, action_server: Path
) -> None:
    check(
        "agent3",
        datadir,
        scenario,
        data_regression,
        agent_cli,
        returncode=0 if scenario is ok else 1,
        action_server=action_server,
        check="only_dir",
    )


def _run_agent_cli_in_folder(
    agent_path: Path,
    agent_cli: Path,
    returncode: int,
    data_regression: DataRegressionFixture | None,
):
    import json
    import re
    import typing

    run_result = run_agent_cli(agent_cli, ["validate", str(agent_path), "--json"], cwd=agent_path)

    assert run_result.returncode == returncode, (
        f"Expected returncode {returncode}, but got {run_result.returncode}\n"
        f"stdout: {run_result.stdout}\n"
        f"stderr: {run_result.stderr}"
    )
    try:
        data = json.loads(run_result.stdout)
    except Exception as exc:
        raise Exception(
            f"Failed to parse stdout as json.\n"
            f"stdout: {run_result.stdout}\n"
            f"stderr: {run_result.stderr}"
        ) from exc

    # Sort the data by message and line
    data = sorted(data, key=lambda e: (e["message"], e["range"]["start"]["line"]))
    if data_regression:
        data_regression.check(typing.cast(typing.Any, data))
    elif data:
        # If data regression is not given, we cannot have any errors.
        raise AssertionError(
            "Expected no errors. Found:\n%s\nStderr: %s\nStdout: %s"
            % (
                "\n".join(str(x) for x in data),
                run_result.stderr,
                run_result.stdout,
            )
        )

    run_result_txt = run_agent_cli(agent_cli, ["validate", str(agent_path)], cwd=agent_path)

    assert run_result_txt.returncode == returncode, (
        f"Expected returncode {returncode}. Found:\n{run_result_txt}"
    )

    # Go through the output and match to Error at line: <line-number>: <message>
    found = []
    for line in run_result_txt.stdout.splitlines():
        if line.startswith("Error at line:"):
            regex = r"Error at line: (\d+): (.+)"
            match = re.match(regex, line)
            if match:
                line_number = int(match.group(1))
                message = match.group(2)
                found.append({"line": line_number, "message": message})
    assert len(found) == len(data), (
        f"Expected {len(data)} errors, but found {len(found)}:\n{run_result_txt}"
    )


def check_with_spec(
    agent_cli: Path, data_regression, valid_yaml, datadir, create_folders=(), returncode=1
):
    (datadir / "runbook.md").write_text("")
    for folder in create_folders:
        (datadir / folder).mkdir(parents=True)
    (datadir / "agent-spec.yaml").write_text(valid_yaml)
    _run_agent_cli_in_folder(datadir, agent_cli, returncode, data_regression)


def test_spec_validation_mcp_servers_ok(agent_cli: Path, datadir: Path, data_regression):
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
            Authorization: "Bearer ${oauth2_api_key}"
            Content-Type: "${content_type}"
          force-serial-tool-calls: false
        - name: mcp-server-2
          transport: stdio
          description: MCP Server 2 for stdio transport.
          command-line: ['uv', 'run', 'python', '-m', 'my-server']
          env:
            API_KEY: "${api_key}"
            DATABASE_URL: "${database_url}"
          cwd: ./mcp-server/path
          force-serial-tool-calls: true
        - name: mcp-server-3
          transport: sse
          description: MCP Server 3 for SSE transport.
          url: http://localhost:9000
          headers:
            X-API-Key: "${api_key}"
    """

    check_with_spec(
        agent_cli,
        data_regression,
        valid_yaml,
        datadir,
        create_folders=["./mcp-server/path"],
        returncode=0,
    )


def test_spec_validation_mcp_servers_missing_required(
    agent_cli: Path, datadir: Path, data_regression
):
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

    check_with_spec(
        agent_cli,
        data_regression,
        bad_yaml,
        datadir,
    )


def test_spec_validation_mcp_servers_invalid_transport(
    agent_cli: Path, datadir: Path, data_regression
):
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

    check_with_spec(
        agent_cli,
        data_regression,
        bad_yaml,
        datadir,
    )


def test_spec_validation_mcp_servers_missing_url_for_http(
    agent_cli: Path, datadir: Path, data_regression
):
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
            Authorization: "Bearer ${oauth2_api_key}"
        - name: mcp-server-2
          transport: sse
          description: MCP Server missing URL for SSE
    """

    check_with_spec(
        agent_cli,
        data_regression,
        bad_yaml,
        datadir,
    )


def test_spec_validation_mcp_servers_missing_command_line_for_stdio(
    agent_cli: Path, datadir: Path, data_regression
):
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

    check_with_spec(
        agent_cli,
        data_regression,
        bad_yaml,
        datadir,
    )


def test_spec_validation_mcp_servers_invalid_headers_format(
    agent_cli: Path, datadir: Path, data_regression
):
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

    check_with_spec(
        agent_cli,
        data_regression,
        bad_yaml,
        datadir,
    )


def test_spec_validation_mcp_servers_invalid_command_line_format(
    agent_cli: Path, datadir: Path, data_regression
):
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

    check_with_spec(
        agent_cli,
        data_regression,
        bad_yaml,
        datadir,
    )


def test_spec_validation_mcp_servers_invalid_env_vars_format(
    agent_cli: Path, datadir: Path, data_regression
):
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
          env: "not-a-list"
        - name: mcp-server-2
          transport: stdio
          description: MCP Server with invalid env vars content
          command-line: ['python', '-m', 'server']
          env: [123, "API_KEY"]
    """

    check_with_spec(
        agent_cli,
        data_regression,
        bad_yaml,
        datadir,
    )


def test_spec_validation_mcp_servers_invalid_cwd_format(
    agent_cli: Path, datadir: Path, data_regression
):
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

    check_with_spec(
        agent_cli,
        data_regression,
        bad_yaml,
        datadir,
    )


def test_spec_validation_mcp_servers_invalid_force_serial_tool_calls_format(
    agent_cli: Path, datadir: Path, data_regression
):
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

    check_with_spec(
        agent_cli,
        data_regression,
        bad_yaml,
        datadir,
    )


def test_spec_validation_mcp_servers_mixed_transport_configurations(
    agent_cli: Path, datadir: Path, data_regression
):
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
          env:
            API_KEY: "${api_key}"  # Should not be here for http
        - name: mcp-server-2
          transport: stdio
          description: MCP Server with http fields
          command-line: ['python', '-m', 'server']
          url: http://localhost:8000  # Should not be here for stdio
          headers:
            Authorization: "Bearer ${oauth2_api_key}"  # Should not be here for stdio
    """

    check_with_spec(
        agent_cli,
        data_regression,
        bad_yaml,
        datadir,
    )


def test_spec_validation_mcp_servers_headers_bad_type(
    agent_cli: Path, datadir: Path, data_regression
):
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

    check_with_spec(
        agent_cli,
        data_regression,
        bad_yaml,
        datadir,
        create_folders=["./mcp-server/path"],
    )


def test_spec_validation_bad_oauth2_secret_type(agent_cli: Path, datadir: Path, data_regression):
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

    check_with_spec(
        agent_cli,
        data_regression,
        bad_yaml,
        datadir,
    )


def test_spec_validation_bad_auto_transport(agent_cli: Path, datadir: Path, data_regression):
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
      conversation-starter: 1
      welcome-message: 1
      metadata:
        mode: conversational
      mcp-servers:
        - name: mcp-server-1
          transport: auto
          description: MCP Server with auto transport
    """

    check_with_spec(
        agent_cli,
        data_regression,
        bad_yaml,
        datadir,
    )


def test_spec_bad_mcp_gateway(agent_cli: Path, datadir: Path, data_regression):
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
      mcp-gateway:
        servers:
          atlassian:
            tools: 1
          duckduckgo:
            tools: 'wrong'
          bar:
            tools:
            - tool1
            - 1
          wrong-too: []
    """

    check_with_spec(
        agent_cli,
        data_regression,
        bad_yaml,
        datadir,
    )


def test_spec(agent_cli: Path):
    import os

    DOCS_DIR = Path(__file__).parent.parent.parent / "versions"
    assert os.path.exists(DOCS_DIR), f"Expected docs dir to exist. Found {DOCS_DIR}"

    specs_found = DOCS_DIR.glob("**/agent-package-specification*.json")
    for json_spec_path in specs_found:
        for yaml_spec_path in json_spec_path.parent.glob("**/agent-spec*.yaml"):
            _run_agent_cli_in_folder(yaml_spec_path.parent, agent_cli, 0, None)
