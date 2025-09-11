import os
from unittest.mock import MagicMock

import pytest

from agent_platform.core.delta import combine_generic_deltas
from agent_platform.core.kernel import Kernel
from agent_platform.core.platforms.bedrock.client import BedrockClient
from agent_platform.core.platforms.bedrock.configs import BedrockModelMap
from agent_platform.core.platforms.bedrock.parameters import BedrockPlatformParameters
from agent_platform.core.responses.content import ResponseTextContent
from agent_platform.core.responses.response import ResponseMessage
from core.tests.platforms.conftest import compare_responses
from core.tests.vcrx import patched_vcr


def normalize_response(response: ResponseMessage) -> ResponseMessage:
    """
    Normalize a response message for Bedrock-specific formatting.

    Bedrock (Claude 4-series)responses often
    add newlines between tags in the response

    This function normalizes these differences to match expected responses.

    Args:
        response: The response message to normalize

    Returns:
        The normalized response message
    """

    for i, content_item in enumerate(response.content):
        if isinstance(content_item, ResponseTextContent):
            text = content_item.text
            text = text.replace("\n", "")
            normalized_content = ResponseTextContent(text=text)
            response.content[i] = normalized_content

    return response


# -------------------------------------------------------------------------
# MODEL LISTS
# -------------------------------------------------------------------------
MODELS_WITH_TEXT_INPUT = BedrockModelMap.distinct_llm_model_ids()
MODELS_WITH_TOOL_INPUT = BedrockModelMap.distinct_llm_model_ids_with_tool_input()
ALL_MODELS = sorted(BedrockModelMap.distinct_llm_model_ids())

# -------------------------------------------------------------------------
# TEST CASES
# -------------------------------------------------------------------------
TEST_CASES = [
    {
        "case_name": "basic_prompt",
        "prompt_fixture": "basic_prompt_no_tools",
        "response_fixture": "response_to_basic_prompt_no_tools",
        "models": MODELS_WITH_TEXT_INPUT,
        "cassette_suffix": "basic_prompt",
    },
    {
        "case_name": "system_message",
        "prompt_fixture": "basic_prompt_with_system_message",
        "response_fixture": "response_to_basic_prompt_with_system_message",
        "models": MODELS_WITH_TEXT_INPUT,
        "cassette_suffix": "basic_prompt_with_system_message",
    },
    {
        "case_name": "three_messages",
        "prompt_fixture": "basic_prompt_with_three_messages",
        "response_fixture": "response_to_basic_prompt_with_three_messages",
        "models": MODELS_WITH_TEXT_INPUT,
        "cassette_suffix": "basic_prompt_with_three_messages",
    },
    {
        "case_name": "one_tool",
        "prompt_fixture": "basic_prompt_with_one_tool",
        "response_fixture": "response_to_basic_prompt_with_one_tool",
        "models": MODELS_WITH_TOOL_INPUT,
        "cassette_suffix": "basic_prompt_with_one_tool",
    },
    {
        "case_name": "tool_no_args",
        "prompt_fixture": "basic_prompt_tool_no_args",
        "response_fixture": "response_to_basic_prompt_tool_no_args",
        "models": MODELS_WITH_TOOL_INPUT,
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
async def bedrock_client(kernel: Kernel):
    """Fixture for Bedrock client with proper cleanup."""
    access_key_id = os.environ.get("AWS_ACCESS_KEY_ID", "UNUSED")
    secret_access_key = os.environ.get("AWS_SECRET_ACCESS_KEY", "UNUSED")
    default_region = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
    client = BedrockClient(
        parameters=BedrockPlatformParameters(
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name=default_region,
        ),
    )
    client.attach_kernel(kernel)
    try:
        yield client
    finally:
        try:
            await client.aclose()
        except Exception:
            pass


# -------------------------------------------------------------------------
# TESTS
# -------------------------------------------------------------------------


def _fixup_haiku_response(response: ResponseMessage) -> ResponseMessage:
    """Haiku is bad at following even the basic
    instruction in our test prompt..."""
    new_content = []
    for content in response.content:
        if not isinstance(content, ResponseTextContent):
            new_content.append(content)
        elif isinstance(content, ResponseTextContent):
            as_text = content.text
            if "<response>" in as_text:
                as_text = as_text.split("<response>")[1]
                as_text = as_text.split("</response>")[0]
                as_text = as_text.strip()
                new_content.append(
                    ResponseTextContent(
                        text=f"<response>{as_text}</response>",
                    ),
                )
            else:
                new_content.append(content)

    return response.model_copy(
        content=[
            # Dump as we're going to re-parse w/ model_validate in copy
            c.model_dump()
            for c in new_content
        ],
    )


@pytest.mark.parametrize("case", TEST_CASES, ids=[c["case_name"] for c in TEST_CASES])
@pytest.mark.parametrize("model_id", ALL_MODELS)
async def test_bedrock_generate_responses(request, bedrock_client, case, model_id):
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
        f"platforms/bedrock/test_e2e/test_response_{case['cassette_suffix']}__{model_id}.yaml"
    )

    with patched_vcr(cassette_path):
        bedrock_prompt = await bedrock_client.converters.convert_prompt(
            prompt,
            model_id=model_id,
        )
        response = await bedrock_client.generate_response(
            bedrock_prompt,
            model=model_id,
        )

    final_response = _fixup_haiku_response(response) if "haiku" in model_id else response
    final_response = normalize_response(final_response)
    compare_responses(final_response, expected_response)


@pytest.mark.parametrize("case", TEST_CASES, ids=[c["case_name"] for c in TEST_CASES])
@pytest.mark.parametrize("model_id", ALL_MODELS)
async def test_bedrock_stream_responses(request, bedrock_client, case, model_id):
    """
    Test each (case, model_id) for streaming responses.
    """
    if model_id not in case["models"]:
        pytest.skip(f"Model {model_id} not applicable to case '{case['case_name']}'")

    prompt = request.getfixturevalue(case["prompt_fixture"])
    await prompt.finalize_messages()
    expected_response = request.getfixturevalue(case["response_fixture"])

    cassette_path = (
        f"platforms/bedrock/test_e2e/"
        f"test_stream_response_{case['cassette_suffix']}__{model_id}.yaml"
    )

    with patched_vcr(cassette_path):
        bedrock_prompt = await bedrock_client.converters.convert_prompt(
            prompt,
            model_id=model_id,
        )

        deltas = []
        async for delta in bedrock_client.generate_stream_response(
            bedrock_prompt,
            model=model_id,
        ):
            deltas.append(delta)

        # Combine the streamed deltas into a single ResponseMessage
        response = ResponseMessage.model_validate(
            combine_generic_deltas(deltas),
        )

    final_response = _fixup_haiku_response(response) if "haiku" in model_id else response
    final_response = normalize_response(final_response)
    compare_responses(final_response, expected_response)
