import json
import unittest.mock
import uuid
from pathlib import Path

import pytest
from agent_platform.orchestrator.agent_server_client import AgentServerClient

from agent_platform.core.work_items import WorkItemStatus
from agent_platform.core.work_items.work_item import WorkItem

# Import cloud server fixture for file upload tests
from server.tests.files.test_api_endpoints_cloud import cloud_server  # noqa: F401


def _get_work_item_judge_test_files():
    """Get all JSON files from the work-item-threads-to-judge directory for parameterization."""

    # Get the directory path relative to this test file
    current_dir = Path(__file__).parent
    work_item_threads_dir = current_dir / "resources" / "work-item-threads-to-judge"

    if not work_item_threads_dir.exists():
        return []

    # Get all JSON files and create pytest parameters
    json_files = []
    for file_path in work_item_threads_dir.glob("*.json"):
        # Use the filename without extension as the test ID
        test_id = file_path.stem.replace("-", "_")
        json_files.append(pytest.param(file_path.name, id=test_id))

    return sorted(json_files, key=lambda x: x.values[0])  # Sort by filename


def _create_mock_storage_for_judge(work_item: WorkItem, openai_api_key: str):
    """Create mock storage service with required dependencies for judge testing."""
    from agent_platform.core.agent.agent import Agent
    from agent_platform.core.agent.agent_architecture import AgentArchitecture
    from agent_platform.core.platforms.openai.parameters import OpenAIPlatformParameters
    from agent_platform.core.runbook.runbook import Runbook
    from agent_platform.core.user import User
    from agent_platform.core.utils import SecretString

    mock_user = User(user_id=work_item.user_id, sub="test_user")
    mock_platform_config = OpenAIPlatformParameters(
        openai_api_key=SecretString(openai_api_key),
        models={"openai": ["gpt-5-low"]},
        platform_id=str(uuid.uuid4()),
    )
    mock_agent = Agent(
        name="Test Agent",
        description="Test agent for validation",
        user_id=work_item.user_id,
        runbook_structured=Runbook(raw_text="You are a helpful assistant", content=[]),
        version="1.0.0",
        platform_configs=[mock_platform_config],
        agent_architecture=AgentArchitecture(name="test_arch", version="1.0.0"),
    )

    mock_storage = unittest.mock.AsyncMock()
    mock_storage.get_user_by_id.return_value = mock_user
    mock_storage.get_agent.return_value = mock_agent
    return mock_storage


def _create_capture_function():
    """Create function to capture judge response and conversation for debugging."""
    judge_response = None
    formatted_conversation = None

    async def capture_prompt_generate(*args, **kwargs):
        nonlocal judge_response, formatted_conversation
        from agent_platform.server.api.private_v2.prompt import prompt_generate

        result = await prompt_generate(*args, **kwargs)
        judge_response = result

        if args and hasattr(args[0], "messages") and args[0].messages:
            user_message = args[0].messages[0]
            if hasattr(user_message, "content") and user_message.content:
                prompt_text = user_message.content[0].text
                start_marker = "<conversation_start>"
                end_marker = "</conversation_start>"
                if start_marker in prompt_text and end_marker in prompt_text:
                    start_idx = prompt_text.find(start_marker) + len(start_marker)
                    end_idx = prompt_text.find(end_marker)
                    formatted_conversation = prompt_text[start_idx:end_idx].strip()
        return result

    return capture_prompt_generate, lambda: (judge_response, formatted_conversation)


def _create_detailed_error_message(
    expected_status, result_status, resource_file, judge_response, formatted_conversation
):
    """Create detailed error message for judge test failures."""
    from agent_platform.core.responses.response import ResponseMessage

    error_msg = [
        f"Expected {expected_status} but got {result_status} for {resource_file}",
        "",
        "=== JUDGE'S FULL RESPONSE ===",
    ]

    if judge_response and isinstance(judge_response, ResponseMessage):
        judge_texts = []
        try:
            content_list = getattr(judge_response, "content", [])
            if content_list:
                for content_item in content_list:
                    if hasattr(content_item, "text"):
                        judge_texts.append(content_item.text)
        except (TypeError, AttributeError):
            pass

        if judge_texts:
            error_msg.append("Judge's response text(s):")
            for i, text in enumerate(judge_texts):
                error_msg.append(f"  [{i + 1}] {text!r}")
        else:
            error_msg.append("Judge's response contained no text content")

        error_msg.append(f"Full response object: {judge_response}")
    else:
        error_msg.append("No judge response captured")

    if formatted_conversation:
        error_msg.extend(["", "=== CONVERSATION SENT TO JUDGE ===", formatted_conversation])

    error_msg.append("=" * 50)
    return "\n".join(error_msg)


@pytest.mark.integration
@pytest.mark.usefixtures("copy_tmpdir_on_failure")
@pytest.mark.asyncio
@pytest.mark.parametrize("resource_file", _get_work_item_judge_test_files())
async def test_work_item_judge_with_recorded_threads(
    base_url_agent_server_with_work_items: str,
    openai_api_key: str,
    resource_file: str,
    resources_dir: Path,
):
    """Test the work item judge using pre-recorded conversation threads.
    These are sanity checks for the work-items judge to verify that it is capable of
    handling basic cases. A thorough test-suite for work-items is available in the Quality
    test harness.
    """

    from agent_platform.server.storage import StorageService
    from agent_platform.server.work_items.judge import _validate_success

    # Load test data
    work_item_resources_dir = resources_dir / "work-item-threads-to-judge"
    with open(work_item_resources_dir / resource_file, encoding="utf-8") as fh:
        work_item_data = json.load(fh)

    expected_status = WorkItemStatus(work_item_data.pop("expected_status"))
    work_item = WorkItem.model_validate(work_item_data)

    # Setup agent and mocks
    with AgentServerClient(base_url_agent_server_with_work_items) as agent_client:
        agent_id = agent_client.create_agent_and_return_agent_id(
            platform_configs=[
                {
                    "kind": "openai",
                    "openai_api_key": openai_api_key,
                    # Use the allowlist feature to force a specific model
                    "models": {"openai": ["gpt-5-low"]},
                }
            ],
        )
        work_item.agent_id = agent_id

        mock_storage = _create_mock_storage_for_judge(work_item, openai_api_key)
        capture_function, get_captured_data = _create_capture_function()

        # Test judge with mocked dependencies
        with (
            unittest.mock.patch.object(StorageService, "get_instance", return_value=mock_storage),
            unittest.mock.patch(
                "agent_platform.server.work_items.judge.prompt_generate",
                side_effect=capture_function,
            ),
        ):
            result_status = await _validate_success(work_item)

        # Assert result with detailed error message if needed
        if result_status != expected_status:
            judge_response, formatted_conversation = get_captured_data()
            error_msg = _create_detailed_error_message(
                expected_status,
                result_status,
                resource_file,
                judge_response,
                formatted_conversation,
            )
            raise AssertionError(error_msg)

        assert result_status == expected_status
