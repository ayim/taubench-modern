import os
from unittest.mock import MagicMock

import pytest

from agent_platform.core.delta import combine_generic_deltas
from agent_platform.core.kernel import Kernel
from agent_platform.core.platforms.configs import PlatformModelConfigs
from agent_platform.core.platforms.openai.client import OpenAIClient
from agent_platform.core.platforms.openai.parameters import OpenAIPlatformParameters
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
    if model.startswith("openai/openai/")
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
]


# -------------------------------------------------------------------------
# FIXTURES
# -------------------------------------------------------------------------
@pytest.fixture
def kernel() -> Kernel:
    """Fixture for the Kernel mock."""
    return MagicMock(spec=Kernel)


@pytest.fixture
def openai_client(kernel: Kernel):
    """Fixture for OpenAI client with proper cleanup."""
    api_key = os.environ.get("OPENAI_API_KEY", "UNUSED")
    client = OpenAIClient(
        parameters=OpenAIPlatformParameters(
            openai_api_key=SecretString(api_key),
        ),
    )
    client.attach_kernel(kernel)
    return client


# -------------------------------------------------------------------------
# TESTS
# -------------------------------------------------------------------------


@pytest.mark.parametrize("case", TEST_CASES, ids=[c["case_name"] for c in TEST_CASES])
@pytest.mark.parametrize("model_id", MODELS_TO_TEST)
async def test_openai_generate_responses(request, openai_client, case, model_id):
    """
    Test each (case, model_id) for generating responses (non-stream).
    """
    # If model_id not relevant to this case, skip
    if model_id not in case["models"]:
        pytest.skip(f"Model {model_id} not applicable to case '{case['case_name']}'")

    # Get the prompt + expected response from fixtures
    prompt = request.getfixturevalue(case["prompt_fixture"])
    await prompt.finalize_messages()
    expected_response = request.getfixturevalue(case["response_fixture"])

    # Unique cassette per test
    cassette_path = (
        f"platforms/openai/test_e2e/test_response_{case['cassette_suffix']}__{model_id}.yaml"
    )

    with patched_vcr(cassette_path):
        openai_prompt = await openai_client.converters.convert_prompt(
            prompt,
            model_id=model_id,
        )
        response = await openai_client.generate_response(
            openai_prompt,
            model=model_id,
        )

    compare_responses(response, expected_response)


@pytest.mark.parametrize("case", TEST_CASES, ids=[c["case_name"] for c in TEST_CASES])
@pytest.mark.parametrize("model_id", MODELS_TO_TEST)
async def test_openai_stream_responses(request, openai_client, case, model_id):
    """
    Test each (case, model_id) for streaming responses.
    """
    if model_id not in case["models"]:
        pytest.skip(f"Model {model_id} not applicable to case '{case['case_name']}'")

    prompt = request.getfixturevalue(case["prompt_fixture"])
    await prompt.finalize_messages()
    expected_response = request.getfixturevalue(case["response_fixture"])

    cassette_path = (
        f"platforms/openai/test_e2e/test_stream_response_{case['cassette_suffix']}__{model_id}.yaml"
    )

    with patched_vcr(cassette_path):
        openai_prompt = await openai_client.converters.convert_prompt(
            prompt,
            model_id=model_id,
        )

        deltas = []
        async for delta in openai_client.generate_stream_response(
            openai_prompt,
            model=model_id,
        ):
            deltas.append(delta)

        # Combine the streamed deltas into a single ResponseMessage
        response = ResponseMessage.model_validate(
            combine_generic_deltas(deltas),
        )

    compare_responses(response, expected_response)
