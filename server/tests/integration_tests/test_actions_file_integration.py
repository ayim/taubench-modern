import json
import urllib
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import pytest

from tests.integration_tests.agent_client import ActionPackageDataClass

if TYPE_CHECKING:
    from tests.integration_tests.bootstrap_action_server import ActionServerProcess

from dotenv import load_dotenv

load_dotenv()


def _raise_for_status(message: str, response, valid_statuses: tuple[int, ...] = (200,)):
    if response.status not in valid_statuses:
        raise ValueError(
            f"{message}\nStatus: {response.status}\nBody: {response.data!r}",
        )


@pytest.fixture
def files_dummy_server(tmpdir):
    from tests.integration_tests.files_dummy_server import FilesDummyServer

    ret = FilesDummyServer(Path(tmpdir) / "files")
    ret.start()
    yield ret
    ret.stop()


@pytest.mark.parametrize(
    "file_manager_type",
    (
        "cloud",
        "local",
    ),
)
def test_api_interaction_expected_from_actions(
    tmpdir, logs_dir, file_manager_type: Literal["cloud", "local"], files_dummy_server
):
    """
    This test checks that the API in the agent server matches what the
    actions call directly.
    """
    from tests.integration_tests.integration_fixtures import start_agent_server

    env = {"S4_AGENT_SERVER_FILE_MANAGER_TYPE": file_manager_type}

    # Note that in the local use-case it uses datadir/uploads.
    if file_manager_type == "cloud":
        env["FILE_MANAGEMENT_API_URL"] = (
            f"http://localhost:{files_dummy_server.get_port()}"
        )

    with start_agent_server(tmpdir, logs_dir, env) as url:
        check_files_integration(url, file_manager_type)


def check_files_integration(
    base_url_agent_server: str, file_manager_type: Literal["cloud", "local"]
):
    from agent_server_orchestrator.agent_server_client import AgentServerClient
    from agent_server_types.constants import NOT_CONFIGURED

    base_url_api = f"{base_url_agent_server}/api/v1"

    # As we're not talking to the agent, set it as not configured and don't
    # wait for it to be ready.
    with AgentServerClient(base_url_agent_server) as agent_client:
        agent_id = agent_client.create_agent_and_return_agent_id(
            NOT_CONFIGURED,
            wait_for_ready=False,
        )
        thread_id = agent_client.create_thread_and_return_thread_id(agent_id)
        import sema4ai_http

        filename = "foo.txt"
        content = "foo"

        url = f"{base_url_api}/threads/{thread_id}/files/request-upload"
        headers = {
            "Content-Type": "application/json",
        }
        data = json.dumps({"file_name": filename, "file_size": len(content)}).encode(
            "utf-8",
        )

        # Send the initial request
        response = sema4ai_http.post(url, body=data, headers=headers)
        _raise_for_status(
            f"Failed when requesting upload for file {filename} to {url}.",
            response,
            (200,),
        )

        response_data = response.json()
        file_url = response_data["url"]
        file_id = response_data["file_id"]
        file_ref = response_data["file_ref"]

        parsed_url = urllib.parse.urlparse(file_url)
        if file_manager_type == "local":
            assert parsed_url.scheme == "file"
            from sema4ai_agent_server.file_manager.local import url_to_fs_path

            p = Path(url_to_fs_path(file_url))
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
        else:
            assert parsed_url.scheme == "http"
            # Don't really upload in this case (the server isn't answering)

        # Send the upload complete notification
        url = f"{base_url_api}/threads/{thread_id}/files/confirm-upload"
        headers = {
            "Content-Type": "application/json",
        }
        data = json.dumps({"file_ref": file_ref, "file_id": file_id}).encode("utf-8")
        response = sema4ai_http.post(url, body=data, headers=headers)
        _raise_for_status(
            f"Failed when completing upload for file {filename} to {url}.",
            response,
            (303, 200),
        )

        url = f"{base_url_api}/threads/{thread_id}/file-by-ref"
        headers = {
            "Content-Type": "application/json",
        }

        # Send the initial request
        response = sema4ai_http.get(url, fields={"file_ref": filename}, headers=headers)
        _raise_for_status(
            f"Failed to get file {filename} from {url}.",
            response,
            (200,),
        )

        response_data = response.json()
        file_url = response_data.get("file_url")
        if not file_url:
            raise ValueError(
                f"Failed to get file {filename} from {url}. Response: {response_data}",
            )

        parsed_url = urllib.parse.urlparse(file_url)
        if file_manager_type == "local":
            assert parsed_url.scheme == "file"
            p = Path(url_to_fs_path(file_url))
            assert p.read_text() == content
        else:
            assert parsed_url.scheme == "http"

        # Ok, we're able to upload and retrieve a file.
        # Let's list the files in the thread and see if it's there.
        url = f"{base_url_api}/threads/{thread_id}/files"
        headers = {
            "Content-Type": "application/json",
        }
        response = sema4ai_http.get(url, headers=headers)
        assert response.status == 200
        response_data = response.json()
        for entry in response_data:
            if entry["file_ref"] == filename:
                break
        else:
            raise ValueError(
                f"Did not find the file {filename} in the thread files list: {response_data}",
            )


def test_api_interaction_with_chat_files(
    base_url_agent_server: str,
    openai_api_key: str,
    action_server_process: "ActionServerProcess",
    logs_dir: Path,
    resources_dir: Path,
):
    """
    This test is a full integration test that checks that actions can
    upload and retrieve files from the agent server thread.
    """
    from tests.integration_tests.agent_client import AgentServerClient

    base_url_api = f"{base_url_agent_server}/api/v1"
    env = {"SEMA4AI_FILE_MANAGEMENT_URL": base_url_api}
    cwd = resources_dir / "simple_action_package"
    api_key = "test"
    action_server_process.start(
        logs_dir=logs_dir,
        cwd=cwd,
        actions_sync=True,
        min_processes=1,
        max_processes=1,
        reuse_processes=True,
        lint=True,
        timeout=500,  # Can be slow (time to bootstrap env)
        additional_args=["--api-key", api_key],
        env=env,
    )
    action_server_url = (
        f"http://{action_server_process.host}:{action_server_process.port}"
    )

    runbook = """
You are an agent just to call other tools actions as requested.
"""
    description = "Agent caller"

    with AgentServerClient(base_url_agent_server) as agent_client:
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

        thread_id = agent_client.create_thread_and_return_thread_id(agent_id)
        result = agent_client.send_message_to_agent_thread_collect_all(
            thread_id,
            "Hello, can you please call the save_runbook action with `this is my runbook` as the contents?",
        )

        result.print_info()

        file_refs = agent_client.list_files(thread_id)
        assert (
            "full-action-contents.json" in file_refs
        ), f"Did not find the file full-action-contents.json in the thread files list: {file_refs}"

        result_json_txt = agent_client.get_file_by_ref(
            thread_id,
            "full-action-contents.json",
        )
        try:
            result_json_dict = json.loads(result_json_txt)
        except Exception:
            raise RuntimeError(f"Failed to parse result_json: {result_json_txt}")

        assert result_json_dict.get(
            "runbook"
        ), f"Found result_json_dict: {json.dumps(result_json_dict, indent=2)}"

        # Change it and make sure we can get the new version
        result = agent_client.send_message_to_agent_thread_collect_all(
            thread_id,
            "Hello, can you please call the save_runbook action with `updated version of the runbook` as the contents?",
        )
        result.print_info()

        result_json_txt = agent_client.get_file_by_ref(
            thread_id,
            "full-action-contents.json",
        )
        assert (
            "updated version" in result_json_txt
        ), f"Did not find the updated version in the file: {result_json_txt}"
