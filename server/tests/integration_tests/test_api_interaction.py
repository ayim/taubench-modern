import os
import sys
import traceback
from typing import Callable

import pytest
from agent_server_types import (
    DEFAULT_ARCHITECTURE,
    RAW_CONTEXT,
    AgentAdvancedConfig,
    AgentMetadata,
    AgentMode,
    AgentReasoning,
    AgentStatus,
    LLMProvider,
    OpenAIGPT,
    OpenAIGPTConfig,
)
from dotenv import load_dotenv

from tests.integration_tests.agent_client import (
    ActionPackageDataClass,
    AgentServerClient,
)

load_dotenv()


def test_api_interaction_with_action_server(
    base_url_agent_server,
    openai_api_key,
    action_server_process,
    logs_dir,
    resources_dir,
):
    cwd = resources_dir / "simple_action_package"
    api_key = "test"
    action_server_process.start(
        cwd=cwd,
        actions_sync=True,
        min_processes=1,
        max_processes=1,
        reuse_processes=True,
        lint=True,
        timeout=500,  # Can be slow (time to bootstrap env)
        additional_args=["--api-key", api_key],
        logs_dir=logs_dir,
    )
    url = f"http://{action_server_process.host}:{action_server_process.port}"

    with AgentServerClient(base_url_agent_server) as agent_client:
        agent_id = agent_client.create_agent_and_return_agent_id(
            openai_api_key,
            action_packages=[
                ActionPackageDataClass(
                    name="ActionPackage",
                    organization="Organization",
                    version="0.0.1",
                    url=url,
                    api_key=api_key,
                    whitelist="",
                )
            ],
        )

        thread_id = agent_client.create_thread_and_return_thread_id(agent_id)
        result = agent_client.send_message_to_agent_thread(
            thread_id, "Which tools/actions can you call?"
        ).lower()
        if "list" not in result or "contact" not in result:
            raise AssertionError(
                "Agent did not provide that it has the list contact action. Found result: "
                f"{result!r}"
            )
        result = agent_client.send_message_to_agent_thread(
            thread_id, "Please list all contacts"
        ).lower()
        if "john doe" not in result and "jane doe" not in result:
            raise AssertionError(
                "Agent did not find contacts: 'john doe' or 'jane doe'. Found result: "
                f"{result!r}"
            )


@pytest.fixture
def create_sample_file(tmpdir):
    def _do_create():
        import random
        import string
        import tempfile

        key = "".join(random.choices(string.ascii_lowercase, k=5))
        value = "".join(random.choices(string.ascii_lowercase, k=5))
        content = f"This is a sample file for testing. Key: {key}, Value: {value}"

        temp_file = tempfile.NamedTemporaryFile(
            mode="w+", delete=False, suffix=".txt", dir=str(tmpdir)
        )
        temp_file.write(content)
        temp_file.close()
        return temp_file.name, key, value

    return _do_create


def test_api_interaction(
    base_url_agent_server: str,
    openai_api_key: str,
    create_sample_file: Callable[[], tuple[str, str, str]],
):
    import random

    from tests.integration_tests.agent_client import (
        print_header,
        print_info,
        print_success,
    )

    uploaded_agent_files: list[str] = []
    uploaded_thread_files: list[str] = []
    try:
        with AgentServerClient(base_url_agent_server) as agent_client:

            def make_file_uploads(
                thread_id: str, agent_id: str
            ) -> tuple[list[str], list[str], list[tuple[str, str]]]:
                print_header("TESTING FILE UPLOADS")

                # Thread file upload
                thread_file, thread_key, thread_value = create_sample_file()
                thread_response = agent_client.upload_file_to_thread(
                    thread_id, thread_file, embedded=True
                )
                assert (
                    thread_response.status_code == 200
                ), f"File upload to thread: bad response: {thread_response.status_code} {thread_response.text}"

                # Agent file upload
                agent_file, agent_key, agent_value = create_sample_file()
                agent_response = agent_client.upload_file_to_agent(agent_id, agent_file)
                assert (
                    agent_response.status_code == 200
                ), f"File upload to agent: bad response: {agent_response.status_code} {agent_response.text}"

                # Multiple file uploads
                multi_files = [create_sample_file()[0] for _ in range(4)]
                agent_files, thread_files = multi_files[:2], multi_files[2:]
                thread_multi_response = agent_client.upload_files_to_thread(
                    thread_id, thread_files
                )
                assert (
                    thread_multi_response.status_code == 200
                ), f"Multiple file upload to thread: bad response: {thread_multi_response.status_code} {thread_multi_response.text}"

                agent_multi_response = agent_client.upload_files_to_agent(
                    agent_id, agent_files
                )

                assert (
                    agent_multi_response.status_code == 200
                ), f"Multiple file upload to agent: bad response: {agent_multi_response.status_code} {agent_multi_response.text}"

                total_files = (
                    1 + 1 + 2 + 2
                )  # 1 thread, 1 agent, 2 multi-thread, 2 multi-agent
                print_success(f"Successfully uploaded {total_files} files")

                return (
                    [agent_file] + agent_files,
                    [thread_file] + thread_files,
                    [
                        (thread_key, thread_value),
                        (agent_key, agent_value),
                    ],
                )

            def make_async_run(thread_id: str) -> None:
                import time

                print_header("TESTING ASYNCHRONOUS RUN")
                async_message = "What's the weather like today?"
                print_info(f"Creating async run with message: {async_message}")
                async_run_response = agent_client.create_async_run(
                    thread_id, async_message
                )
                assert (
                    "run_id" in async_run_response
                ), f"Async run ID not received in response: {async_run_response!r}"

                run_id = async_run_response["run_id"]
                print_success(f"Async run created with ID: {run_id}")

                print_info("Polling for run completion")

                timeout_at = time.time() + 15
                while True:
                    status_response = agent_client.get_run_status(run_id)
                    if status_response is None:
                        raise Exception("async poll failure (status response is None)")

                    if status_response and status_response["status"] == "complete":
                        break
                    if time.time() > timeout_at:
                        raise Exception(
                            f"Run did not complete in time. Status: {status_response!r}"
                        )
                    time.sleep(0.25)

                print_success("Run completed successfully")

                thread_state = agent_client.get_thread_state(thread_id)

                if not thread_state["last_ai_message"]:
                    raise AssertionError(
                        "No AI message found in the thread state after async run. Received thread state: "
                        f"{thread_state!r}"
                    )
                print_success("Received AI message after async run")

            agent_id = agent_client.create_agent_and_return_agent_id(openai_api_key)

            thread_id = agent_client.create_thread_and_return_thread_id(agent_id)
            agent_client.send_message_to_agent_thread(thread_id)
            make_async_run(thread_id)
            uploaded_agent_files, uploaded_thread_files, key_value_pairs = (
                make_file_uploads(thread_id, agent_id)
            )

            # ---------------------- check file retrieval ----------------------
            print_header("TESTING FILE RETRIEVAL")
            if not uploaded_thread_files:
                raise Exception("No files available to test file retrieval")

            file_ref = os.path.basename(uploaded_thread_files[0])
            file_info = agent_client.get_file_info_by_ref(thread_id, file_ref)
            assert file_info is not None, "File information retrieval"
            assert (
                file_ref in file_info["file_url"]
            ), "Retrieved file_ref matches the requested one"
            print_success(f"Successfully retrieved file information for {file_ref}")

            # ---------------------- check information retrieval ----------------------
            print_header("TESTING INFORMATION RETRIEVAL")
            if not key_value_pairs:
                raise AssertionError(
                    "No key-value pairs available for testing retrieval"
                )

            random_key, expected_value = random.choice(key_value_pairs)
            question = f"What is the value associated with the key '{random_key}'?"
            print_info(f"Asking question: {question}")
            response = agent_client.send_message_to_agent_thread(thread_id, question)
            assert (
                expected_value in response
            ), f"Expected value '{expected_value}' found in the response: {response}"
            print_success(f"Successfully retrieved value for key '{random_key}'")
    finally:
        # Clean up files
        for file_path in uploaded_agent_files + uploaded_thread_files:
            try:
                os.unlink(file_path)
            except Exception:
                traceback.print_exc()


if __name__ == "__main__":
    import pytest

    # Can be set to start the agent server in the test
    # os.environ["INTEGRATION_TEST_START_SERVER"] = "true"
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    sys.exit(pytest.main([]))
