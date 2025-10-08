import os
from unittest.mock import MagicMock

import pytest
from snowflake.snowpark import Session

from agent_platform.core.delta import combine_generic_deltas
from agent_platform.core.kernel import Kernel
from agent_platform.core.platforms.configs import PlatformModelConfigs
from agent_platform.core.platforms.cortex.client import CortexClient
from agent_platform.core.platforms.cortex.parameters import CortexPlatformParameters
from agent_platform.core.responses.content import ResponseTextContent, ResponseToolUseContent
from agent_platform.core.responses.response import ResponseMessage
from agent_platform.core.utils import SecretString
from core.tests.platforms.conftest import compare_responses
from core.tests.vcrx import patched_vcr

# -------------------------------------------------------------------------
# MODEL LISTS
# -------------------------------------------------------------------------
MODELS_TO_TEST = [
    model
    for model in PlatformModelConfigs.models_capable_of_driving_agents
    if model.startswith("cortex/")
]

# -------------------------------------------------------------------------
# TEST CASES
# -------------------------------------------------------------------------
TEST_CASES = [
    {
        "case_name": "basic_prompt",
        "prompt_fixture": "basic_prompt_no_tools",
        "response_fixture": "response_to_basic_prompt_no_tools",
        "models": MODELS_TO_TEST,
        "cassette_suffix": "basic_prompt",
    },
    {
        "case_name": "system_message",
        "prompt_fixture": "basic_prompt_with_system_message",
        "response_fixture": "response_to_basic_prompt_with_system_message",
        "models": MODELS_TO_TEST,
        "cassette_suffix": "basic_prompt_with_system_message",
    },
    {
        "case_name": "three_messages",
        "prompt_fixture": "basic_prompt_with_three_messages",
        "response_fixture": "response_to_basic_prompt_with_three_messages",
        "models": MODELS_TO_TEST,
        "cassette_suffix": "basic_prompt_with_three_messages",
    },
    {
        "case_name": "one_tool",
        "prompt_fixture": "basic_prompt_with_one_tool",
        "response_fixture": "response_to_basic_prompt_with_one_tool",
        "models": MODELS_TO_TEST,
        "cassette_suffix": "basic_prompt_with_one_tool",
    },
    {
        "case_name": "tool_no_args",
        "prompt_fixture": "basic_prompt_tool_no_args",
        "response_fixture": "response_to_basic_prompt_tool_no_args",
        "models": MODELS_TO_TEST,
        "cassette_suffix": "basic_prompt_tool_no_args",
    },
    {
        "case_name": "parallel_tool_calls",
        "prompt_fixture": "prompt_to_elicit_parallel_tool_calls",
        "response_fixture": "response_to_prompt_to_elicit_parallel_tool_calls",
        "models": MODELS_TO_TEST,
        "cassette_suffix": "parallel_tool_calls",
    },
]


# -------------------------------------------------------------------------
# FIXTURES
# -------------------------------------------------------------------------
@pytest.fixture
def kernel() -> Kernel:
    """Fixture for the Kernel mock."""
    return MagicMock(spec=Kernel)


@pytest.fixture
def cortex_client(kernel: Kernel, monkeypatch):
    """Fixture for Cortex client with proper cleanup."""
    from pathlib import Path

    from vcr.record_mode import RecordMode

    from core.tests.vcrx import get_vcr_record_mode

    # If we don't have a linking file, we can still run tests, but
    # actually put a non-None value in here so the parameters are
    # "set" (we don't actually make network requests so this is fine)
    unused_or_none: str | None = "UNUSED"
    linking_file_path = Path.home() / ".sema4ai" / "sf-auth.json"
    if linking_file_path.exists():
        unused_or_none = None

    snowflake_username = os.environ.get("SNOWFLAKE_USERNAME", unused_or_none)
    snowflake_password = os.environ.get("SNOWFLAKE_PASSWORD", unused_or_none)
    snowflake_account = os.environ.get("SNOWFLAKE_ACCOUNT", unused_or_none)
    snowflake_role = os.environ.get("SNOWFLAKE_ROLE", unused_or_none)

    mock_session = MagicMock(spec=Session)
    # You can customize additional attributes of the session if needed
    mock_session.connection = MagicMock()
    mock_session.connection.host = "zvzwmyo-hp00956.snowflakecomputing.com"
    mock_session.connection.rest = MagicMock()
    mock_session.connection.rest.token = "DUMMY_TOKEN_VALUE"

    if get_vcr_record_mode() == RecordMode.NONE:
        # When we are doing replays, mock to make sure we don't
        # try and connect to Snowflake
        monkeypatch.setattr(
            "agent_platform.core.platforms.cortex.client.CortexClient._init_session",
            lambda self, parameters: mock_session,
        )

    client = CortexClient(
        parameters=CortexPlatformParameters(
            snowflake_username=snowflake_username,
            snowflake_password=(
                SecretString(snowflake_password) if snowflake_password is not None else None
            ),
            snowflake_account=snowflake_account,
            snowflake_role=snowflake_role,
        ),
    )

    client.attach_kernel(kernel)
    return client


# -------------------------------------------------------------------------
# TESTS
# -------------------------------------------------------------------------


def _strip_deepseek_r1_think_tags(response: ResponseMessage) -> ResponseMessage:
    from re import DOTALL, sub

    new_content = []
    for content in response.content:
        if not isinstance(content, ResponseTextContent):
            new_content.append(content)
        else:
            clean_text = sub(
                r"<think>.*?</think>",
                "",
                content.text,
                flags=DOTALL,
            )

            # Deepseek also likes to include newlines where we don't
            # want them, so strip those out too
            clean_text = clean_text.replace("\n", "")

            new_content.append(
                ResponseTextContent(
                    text=clean_text.strip(),
                ),
            )

    return response.model_copy(
        content=[
            # Dump as we're going to re-parse w/ model_validate in copy
            c.model_dump()
            for c in new_content
        ],
    )


@pytest.mark.parametrize("case", TEST_CASES, ids=[c["case_name"] for c in TEST_CASES])
@pytest.mark.parametrize("model_id", MODELS_TO_TEST)
async def test_cortex_generate_responses(request, cortex_client, case, model_id):
    """
    Test each (case, model_id) for generating responses (non-stream).
    """
    # If model_id not relevant to this case, skip
    if model_id not in case["models"]:
        pytest.skip(f"Model {model_id} not applicable to case '{case['case_name']}'")
    if "parallel" in case["case_name"]:
        pytest.skip("Parallel tool calls are not supported for generate... ANOTHER Cortex bug")

    # Get the prompt + expected response from fixtures
    prompt = request.getfixturevalue(case["prompt_fixture"])
    await prompt.finalize_messages()
    expected_response = request.getfixturevalue(case["response_fixture"])

    # Unique cassette per test
    cassette_path = (
        f"platforms/cortex/test_e2e/test_response_{case['cassette_suffix']}__{model_id}.yaml"
    )

    with patched_vcr(cassette_path):
        cortex_prompt = await cortex_client.converters.convert_prompt(
            prompt,
            model_id=model_id,
        )
        response = await cortex_client.generate_response(
            cortex_prompt,
            model=model_id,
        )

    # For deepseek-r1, we get <think>...</think> inline; strip this
    # to test comparison
    final_response = (
        _strip_deepseek_r1_think_tags(response) if model_id == "deepseek-r1" else response
    )

    compare_responses(final_response, expected_response)


@pytest.mark.parametrize("case", TEST_CASES, ids=[c["case_name"] for c in TEST_CASES])
@pytest.mark.parametrize("model_id", MODELS_TO_TEST)
async def test_cortex_stream_responses(request, cortex_client, case, model_id):
    """
    Test each (case, model_id) for streaming responses.
    """
    if model_id not in case["models"]:
        pytest.skip(f"Model {model_id} not applicable to case '{case['case_name']}'")

    prompt = request.getfixturevalue(case["prompt_fixture"])
    await prompt.finalize_messages()
    expected_response = request.getfixturevalue(case["response_fixture"])

    cassette_path = (
        f"platforms/cortex/test_e2e/test_stream_response_{case['cassette_suffix']}__{model_id}.yaml"
    )

    with patched_vcr(cassette_path):
        cortex_prompt = await cortex_client.converters.convert_prompt(
            prompt,
            model_id=model_id,
        )

        deltas = []
        async for delta in cortex_client.generate_stream_response(
            cortex_prompt,
            model=model_id,
        ):
            deltas.append(delta)

        # Combine the streamed deltas into a single ResponseMessage
        response = ResponseMessage.model_validate(
            combine_generic_deltas(deltas),
        )

    # For deepseek-r1, we get <think>...</think> inline; strip this
    # to test comparison
    final_response = (
        _strip_deepseek_r1_think_tags(response) if model_id == "deepseek-r1" else response
    )

    # TODO(jjhenkel): Cortex + Claude 3.5 does not respect the optionality of the
    # 'category' field in our test tool schema for the parallel tool-call case.
    # It sometimes omits 'category' even when the prompt provides it explicitly.
    # To keep this test stable, accept missing 'category' for this specific combo.
    if case.get("case_name") == "parallel_tool_calls" and model_id == "claude-3-5-sonnet":
        from copy import deepcopy
        from json import dumps

        adjusted_contents = []
        for content in expected_response.content:
            if isinstance(content, ResponseToolUseContent):
                tool_input = deepcopy(content.tool_input)
                if isinstance(tool_input, dict) and isinstance(tool_input.get("book"), dict):
                    tool_input["book"].pop("category", None)
                adjusted_contents.append(
                    ResponseToolUseContent(
                        tool_call_id=content.tool_call_id,
                        tool_name=content.tool_name,
                        tool_input_raw=dumps(tool_input),
                    )
                )
            else:
                adjusted_contents.append(content)

        expected_response = expected_response.model_copy(
            content=[c.model_dump() for c in adjusted_contents],
        )

    compare_responses(final_response, expected_response)
