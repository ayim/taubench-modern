import logging
from pathlib import Path
from typing import Literal

import pytest

from _go_validation_tests.fixtures import RunResult

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


def no_spec_version(agent_path):
    agent_spec = agent_path / "agent-spec.yaml"
    txt = agent_spec.read_text()
    agent_spec.write_text(txt.replace("spec-version: v1", ""))


def bad_spec_version(agent_path):
    agent_spec = agent_path / "agent-spec.yaml"
    txt = agent_spec.read_text()
    agent_spec.write_text(txt.replace("spec-version: v2", "spec-version: 22"))


def v2_bad_architecture(agent_path):
    agent_spec = agent_path / "agent-spec.yaml"
    txt = agent_spec.read_text()
    agent_spec.write_text(
        txt.replace("architecture: plan_execute", "architecture: bad-architecture")
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
    assert txt != new
    package_yaml.write_text(new)


def v2_bad_action_package_name(agent_path):
    package_yaml = agent_path / "agent-spec.yaml"

    update(
        package_yaml,
        lambda txt: txt.replace("name: Control Room Test", "name: Some other name"),
    )


def v2_no_knowledge(agent_path):
    package_yaml = agent_path / "agent-spec.yaml"

    update(
        package_yaml,
        lambda txt: txt.replace(
            "          knowledge:",
            """
          knowledge: []
          bad-knowledge:
""",
        ),
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
        v2_no_knowledge,
    ],
)
def test_agent_spec_analysis(
    datadir, scenario, data_regression, agent_cli: Path, action_server: Path
) -> None:
    do_check: Literal["both", "only_dir", "only_zip"]
    if scenario is v2_no_knowledge:
        do_check = "only_dir"
    else:
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
