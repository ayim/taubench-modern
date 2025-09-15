import os
from unittest.mock import MagicMock

import pytest

from agent_platform.core.delta import combine_generic_deltas
from agent_platform.core.kernel import Kernel
from agent_platform.core.platforms.azure.client import AzureOpenAIClient
from agent_platform.core.platforms.azure.parameters import AzureOpenAIPlatformParameters
from agent_platform.core.responses.response import ResponseMessage
from agent_platform.core.utils import SecretString
from core.tests.platforms.conftest import compare_responses
from core.tests.vcrx import patched_vcr

# For tests, we'll use a limited set of models to avoid excessive test time
ALL_MODELS = ["gpt-5-medium", "gpt-5-minimal"]

# -------------------------------------------------------------------------
# TEST CASES
# -------------------------------------------------------------------------
TEST_CASES = [
    {
        "case_name": "basic_prompt",
        "prompt_fixture": "basic_prompt_no_tools",
        "response_fixture": "response_to_basic_prompt_no_tools",
        "models": ALL_MODELS,
        "cassette_suffix": "basic_prompt",
    },
    {
        "case_name": "system_message",
        "prompt_fixture": "basic_prompt_with_system_message",
        "response_fixture": "response_to_basic_prompt_with_system_message",
        "models": ALL_MODELS,
        "cassette_suffix": "basic_prompt_with_system_message",
    },
    {
        "case_name": "three_messages",
        "prompt_fixture": "basic_prompt_with_three_messages",
        "response_fixture": "response_to_basic_prompt_with_three_messages",
        "models": ALL_MODELS,
        "cassette_suffix": "basic_prompt_with_three_messages",
    },
    {
        "case_name": "one_tool",
        "prompt_fixture": "basic_prompt_with_one_tool",
        "response_fixture": "response_to_basic_prompt_with_one_tool",
        "models": ALL_MODELS,
        "cassette_suffix": "basic_prompt_with_one_tool",
    },
    {
        "case_name": "tool_no_args",
        "prompt_fixture": "basic_prompt_tool_no_args",
        "response_fixture": "response_to_basic_prompt_tool_no_args",
        "models": ALL_MODELS,
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
def azure_client(kernel: Kernel):
    """Fixture for Azure OpenAI client with proper cleanup."""
    api_key = os.environ.get("AZURE_API_KEY", "UNUSED")
    endpoint_url = os.environ.get(
        "AZURE_ENDPOINT_URL",
        "https://example.openai.azure.com",
    )
    deployment_name = os.environ.get("AZURE_DEPLOYMENT_NAME", "test-deployment")
    deployment_name_embeddings = os.environ.get(
        "AZURE_DEPLOYMENT_NAME_EMBEDDINGS",
        "test-embeddings",
    )
    # Don't load this from env... (anytime one switches up they azure env to be a _non_ GPT-5
    # deployment, this'll get unhappy, even though we're replaying gpt-5 cassettes)
    model_backing_deployment_name = "gpt-5"

    client = AzureOpenAIClient(
        parameters=AzureOpenAIPlatformParameters(
            azure_api_key=SecretString(api_key),
            azure_endpoint_url=endpoint_url,
            azure_deployment_name=deployment_name,
            azure_deployment_name_embeddings=deployment_name_embeddings,
            azure_model_backing_deployment_name=model_backing_deployment_name,
        ),
    )
    client.attach_kernel(kernel)
    return client


# -------------------------------------------------------------------------
# TESTS
# -------------------------------------------------------------------------


@pytest.mark.parametrize("case", TEST_CASES, ids=[c["case_name"] for c in TEST_CASES])
@pytest.mark.parametrize("model_id", ALL_MODELS)
async def test_azure_generate_responses(request, azure_client, case, model_id):
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
        f"platforms/azure/test_e2e/test_response_{case['cassette_suffix']}__{model_id}.yaml"
    )

    with patched_vcr(cassette_path):
        azure_prompt = await azure_client.converters.convert_prompt(
            prompt,
            model_id=model_id,
        )
        response = await azure_client.generate_response(
            azure_prompt,
            model=model_id,
        )

    compare_responses(response, expected_response)


@pytest.mark.parametrize("case", TEST_CASES, ids=[c["case_name"] for c in TEST_CASES])
@pytest.mark.parametrize("model_id", ALL_MODELS)
async def test_azure_stream_responses(request, azure_client, case, model_id):
    """
    Test each (case, model_id) for streaming responses.
    """
    if model_id not in case["models"]:
        pytest.skip(f"Model {model_id} not applicable to case '{case['case_name']}'")

    prompt = request.getfixturevalue(case["prompt_fixture"])
    await prompt.finalize_messages()
    expected_response = request.getfixturevalue(case["response_fixture"])

    cassette_path = (
        f"platforms/azure/test_e2e/test_stream_response_{case['cassette_suffix']}__{model_id}.yaml"
    )

    with patched_vcr(cassette_path):
        azure_prompt = await azure_client.converters.convert_prompt(
            prompt,
            model_id=model_id,
        )

        deltas = []
        async for delta in azure_client.generate_stream_response(
            azure_prompt,
            model=model_id,
        ):
            deltas.append(delta)

        # Combine the streamed deltas into a single ResponseMessage
        response = ResponseMessage.model_validate(
            combine_generic_deltas(deltas),
        )

    compare_responses(response, expected_response)
