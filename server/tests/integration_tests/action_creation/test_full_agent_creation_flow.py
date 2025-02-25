from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from tests.integration_tests.agent_client import ActionPackageDataClass

if TYPE_CHECKING:
    from tests.integration_tests.agent_client import AgentServerClient


@pytest.fixture
def agents_dir() -> Path:
    return Path(__file__).parent / "agents"


class BootstrapAgentsResult:
    def __init__(
        self,
        dir_name_to_agent_id: dict[str, str],
        agent_client: "AgentServerClient",
    ):
        self.dir_name_to_agent_id = dir_name_to_agent_id
        self.agent_client = agent_client


@pytest.fixture
def bootstrap_agents(
    agents_dir: Path,
    action_server_executable_path: Path,
    tmpdir: Path,
    base_url_agent_server: str,
    logs_dir: Path,
    openai_api_key: str,
) -> Iterator[BootstrapAgentsResult]:
    from tests.integration_tests.agent_client import AgentServerClient, print_info
    from tests.integration_tests.bootstrap_action_server import ActionServerProcess

    dir_name_to_agent_id: dict[str, str] = {}
    with AgentServerClient(base_url_agent_server) as agent_client:
        action_servers: list[ActionServerProcess] = []
        for agent_directory in ("runbook_and_actions_creator", "package_builder"):
            action_server_process = ActionServerProcess(
                Path(tmpdir) / agent_directory,
                action_server_executable_path,
            )
            action_servers.append(action_server_process)
            base_url_api = f"{base_url_agent_server}/api/v1"
            env = {"SEMA4AI_FILE_MANAGEMENT_URL": base_url_api}
            cwd = agents_dir / agent_directory
            api_key = "test"
            action_server_process.start(
                logs_dir=logs_dir,
                cwd=cwd,
                actions_sync=True,
                min_processes=2,
                max_processes=2,
                reuse_processes=True,
                lint=True,
                timeout=500,  # Can be slow (time to bootstrap env)
                additional_args=["--api-key", api_key],
                env=env,
            )

            action_server_url = (
                f"http://{action_server_process.host}:{action_server_process.port}"
            )
            print_info(
                f"Action server URL: {action_server_url} for agent {agent_directory}",
            )

            description = "Agent caller"

            runbook = (cwd / "runbook.md").read_text()

            agent_id = agent_client.create_agent_and_return_agent_id(
                openai_api_key,
                runbook=runbook,
                description=description,
                action_packages=[
                    ActionPackageDataClass(
                        name="ActionPackage",
                        organization="Organization",
                        version="0.0.1",
                        url=action_server_url,
                        api_key=api_key,
                        whitelist="",
                    ),
                ],
            )

            dir_name_to_agent_id[agent_directory] = agent_id

        yield BootstrapAgentsResult(
            dir_name_to_agent_id=dir_name_to_agent_id,
            agent_client=agent_client,
        )

        for action_server in action_servers:
            action_server.stop()


def test_full_agent_creation_flow(bootstrap_agents: BootstrapAgentsResult, tmpdir):
    """
    This test is a full integration test that checks that actions can
    upload and retrieve files from the agent server thread.
    """
    import json
    import typing
    import zipfile

    from tests.integration_tests.agent_client import print_info

    # Could be used to put output locally.
    # output_dir = Path(__file__).parent / "__output__"
    output_dir = Path(tmpdir) / "__output__"

    agent_client = bootstrap_agents.agent_client
    agent_id = bootstrap_agents.dir_name_to_agent_id["runbook_and_actions_creator"]
    package_builder_agent_id = bootstrap_agents.dir_name_to_agent_id["package_builder"]

    thread_id_runbook_and_actions_creator = (
        agent_client.create_thread_and_return_thread_id(agent_id)
    )
    result = agent_client.send_message_to_agent_thread_collect_all(
        thread_id_runbook_and_actions_creator,
        """Hello, can you please create me an agent which will help me to reconcile the invoices of my company?

My company receives invoices from suppliers through pdfs sent through e-mails 
and I need to reconcile them with the invoices in my accounting software.
""",
    )

    result.print_info()

    file_refs = agent_client.list_files(thread_id_runbook_and_actions_creator)
    assert set(file_refs) == {"runbook.md", "actions.py"}
    for file_ref in file_refs:
        contents: bytes = typing.cast(
            bytes,
            agent_client.get_file_by_ref(
                thread_id_runbook_and_actions_creator,
                file_ref,
                output_type="bytes",
            ),
        )

        print_info(file_ref)
        print_info(json.dumps(json.loads(contents.decode("utf-8")), indent=2))
        # Write this structure to the disk under '__output__'
        output_dir.mkdir(parents=True, exist_ok=True)
        with open(output_dir / file_ref, "w") as f:
            f.write(json.loads(contents.decode("utf-8")))

    # Ok, we have the runbook and the actions, now we need to build the agent
    thread_id_package_builder = agent_client.create_thread_and_return_thread_id(
        package_builder_agent_id,
    )

    # As we're in a new thread, the files are empty and we need to upload the runbook and the actions
    agent_client.upload_file_to_thread(
        thread_id_package_builder,
        "runbook.md",
        content=contents,
        embedded=False,
    )
    file_contents = agent_client.get_file_by_ref(
        thread_id_package_builder,
        "runbook.md",
    )
    assert file_contents == contents.decode("utf-8")

    agent_client.upload_file_to_thread(
        thread_id_package_builder,
        "actions.py",
        content=contents,
        embedded=False,
    )

    agent_client.send_message_to_agent_thread_collect_all(
        thread_id_package_builder,
        "Hello, can you please build the agent?",
    )

    file_refs = agent_client.list_files(thread_id_package_builder)
    assert set(file_refs) == {
        "runbook.md",
        "actions.py",
        "full-agent.zip",
        "full-agent.json",
    }
    contents = typing.cast(
        bytes,
        agent_client.get_file_by_ref(
            thread_id_package_builder,
            "full-agent.zip",
            output_type="bytes",
        ),
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    with open(output_dir / "full-agent.zip", "wb") as f:
        f.write(contents)

    # Now, list the contents from the full-agent.zip

    with zipfile.ZipFile(output_dir / "full-agent.zip", "r") as zip_ref:
        assert set(zip_ref.namelist()) == {
            "runbook.md",
            "actions.py",
        }
