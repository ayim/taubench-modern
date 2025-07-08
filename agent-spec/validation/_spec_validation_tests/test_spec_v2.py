import json
import os
from pathlib import Path

import pytest

from ._spec_validation import InvalidSpec, validate_from_spec

DOCS_DIR = Path(__file__).parent.parent.parent / "versions"
assert os.path.exists(DOCS_DIR), f"Expected docs dir to exist. Found {DOCS_DIR}"


@pytest.fixture(scope="session")
def v2_spec():
    specs_found = list(DOCS_DIR.glob("**/v2/agent-package-specification-v2.json"))
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
def test_spec_validation_ok(datadir: Path, v2_spec: dict):
    from ._spec_validation import load_spec

    valid_yaml = """
agent-package:
  spec-version: v2
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

    validate_from_spec(load_spec(v2_spec), valid_yaml, datadir)


def test_spec_validation_missing_required(datadir: Path, v2_spec: dict, data_regression):
    from _spec_validation_tests._spec_validation import load_spec

    bad_yaml = """
agent-package:
  spec-version: v2
  agents: # Defines the agents available
    - description: This is the description # Description for the agent (any string)
      metadata:
        mode: conversational
    """

    errors = validate_from_spec(load_spec(v2_spec), bad_yaml, datadir, raise_on_error=False)
    assert errors, "Expected errors"
    errors_str = [e.message for e in errors]
    assert "Missing required entry: agent-package/agents/name." in errors_str
    data_regression.check(errors_str)


def test_yaml_categorization(datadir: Path, v2_spec: dict, data_regression):
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
                load_spec(v2_spec), bad_yaml, datadir, raise_on_error=False
            )
        finally:
            Validator.PRINT_YAML_TREE = False
    yaml_tree = sio.getvalue()
    data_regression.check(yaml_tree.splitlines(keepends=False))


def test_spec_validation_not_a_list(datadir: Path, v2_spec: dict):
    from _spec_validation_tests._spec_validation import load_spec

    bad_yaml = """
agent-package:
  spec-version: v2
  agents: # Defines the agents available
    description: This is not a list, just an attribute in an object...
    """

    errors = validate_from_spec(load_spec(v2_spec), bad_yaml, datadir, raise_on_error=False)
    assert errors, "Expected errors"
    errors_str = [e.message for e in errors]
    assert ["Expected agent-package/agents to be a list."] == errors_str


@pytest.mark.usefixtures("_gen_runbook")
def test_spec_validation_not_string(datadir: Path, v2_spec: dict, data_regression):
    from _spec_validation_tests._spec_validation import load_spec

    bad_yaml = """
agent-package: # Root element
  spec-version: v2 # The version of the spec being used
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

    errors = validate_from_spec(load_spec(v2_spec), bad_yaml, datadir, raise_on_error=False)
    assert errors, "Expected errors"
    errors_str = [e.message for e in errors]
    data_regression.check(errors_str)


@pytest.mark.usefixtures("_gen_runbook")
def test_spec_validation_not_in_enum(datadir: Path, v2_spec: dict, data_regression):
    from _spec_validation_tests._spec_validation import load_spec

    bad_yaml = """
agent-package: # Root element
  spec-version: v2 # The version of the spec being used
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

    errors = validate_from_spec(load_spec(v2_spec), bad_yaml, datadir, raise_on_error=False)
    assert errors, "Expected errors"
    errors_str = [e.message for e in errors]
    data_regression.check(errors_str)


def test_spec_validation_no_file(datadir: Path, v2_spec: dict, data_regression):
    from _spec_validation_tests._spec_validation import load_spec

    bad_yaml = """
agent-package: # Root element
  spec-version: v2 # The version of the spec being used
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

    errors = validate_from_spec(load_spec(v2_spec), bad_yaml, datadir, raise_on_error=False)
    assert errors, "Expected errors"
    errors_str = [e.message for e in errors]
    data_regression.check(errors_str)

    (datadir / "no-runbook.md").write_text("")
    (datadir / "knowledge").mkdir()
    (datadir / "knowledge" / "knowledge-file.txt").write_text("")

    errors = validate_from_spec(load_spec(v2_spec), bad_yaml, datadir, raise_on_error=True)


@pytest.mark.usefixtures("_gen_action_package_files", "_gen_runbook")
def test_spec_validation_multiple_action_packages(
    datadir: Path,
    v2_spec: dict,
    data_regression,
):
    from _spec_validation_tests._spec_validation import load_spec

    bad_yaml = r"""
agent-package: # Root element
  spec-version: v2 # The version of the spec being used
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
    errors = validate_from_spec(load_spec(v2_spec), bad_yaml, datadir, raise_on_error=False)
    assert errors, "Expected errors"
    errors_str = [e.message for e in errors]
    data_regression.check(errors_str)


@pytest.mark.usefixtures("_gen_runbook")
def test_spec_validation_deprecated(datadir: Path, v2_spec: dict, data_regression):
    from _spec_validation_tests._spec_validation import load_spec

    bad_yaml = """
agent-package:
  spec-version: v2
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
    errors = validate_from_spec(load_spec(v2_spec), bad_yaml, datadir, raise_on_error=False)

    assert errors, "Expected errors"
    errors_str = [e.message for e in errors]
    data_regression.check(errors_str)

    data_regression.check(
        [e.as_diagostic(None) for e in errors],
        basename="test_spec_validation_deprecated_as_diagnostics",
    )


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
