import os
import sys
import traceback

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

from tests.integration_tests.agent_client import ActionPackageDataClass, AgentClient

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

    with AgentClient(base_url_agent_server) as agent_client:
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


def test_api_interaction(base_url_agent_server, openai_api_key):
    uploaded_agent_files = []
    uploaded_thread_files = []
    try:
        with AgentClient(base_url_agent_server) as agent_client:
            agent_id = agent_client.create_agent_and_return_agent_id(openai_api_key)

            thread_id = agent_client.create_thread_and_return_thread_id(agent_id)
            agent_client.send_message_to_agent_thread(thread_id)
            agent_client.make_async_run(thread_id)
            uploaded_agent_files, uploaded_thread_files, key_value_pairs = (
                agent_client.make_file_uploads(thread_id, agent_id)
            )
            agent_client.check_get_file(thread_id, uploaded_thread_files)
            agent_client.check_retrieval(thread_id, key_value_pairs)
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
