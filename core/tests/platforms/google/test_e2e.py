import os
from unittest.mock import MagicMock

import pytest

from agent_platform.core.delta import combine_generic_deltas
from agent_platform.core.kernel import Kernel
from agent_platform.core.platforms.google.client import GoogleClient
from agent_platform.core.platforms.google.configs import GoogleModelMap
from agent_platform.core.platforms.google.parameters import GooglePlatformParameters
from agent_platform.core.responses.content.text import ResponseTextContent
from agent_platform.core.responses.response import ResponseMessage
from agent_platform.core.utils import SecretString
from core.tests.platforms.conftest import compare_responses
from core.tests.vcr_setup import patched_vcr

# -------------------------------------------------------------------------
# MODEL LISTS
# -------------------------------------------------------------------------
MODELS_WITH_TEXT_INPUT = [m for m in GoogleModelMap.distinct_llm_model_ids()]
MODELS_WITH_TOOL_INPUT = [
    m
    for m in GoogleModelMap.distinct_llm_model_ids_with_tool_input()
    if m not in GoogleModelMap.distinct_llm_model_ids_with_audio_input()
]
ALL_MODELS = sorted(set(GoogleModelMap.distinct_llm_model_ids()))
TEST_MODELS = [
    "gemini-2.5-flash-preview-04-17-high",
    "gemini-2.5-flash-preview-04-17-low",
]

# -------------------------------------------------------------------------
# TEST CASES
# -------------------------------------------------------------------------
TEST_CASES = [
    {
        "case_name": "basic_prompt",
        "prompt_fixture": "basic_prompt_no_tools",
        "response_fixture": "response_to_basic_prompt_no_tools",
        "models": TEST_MODELS,
        "cassette_suffix": "basic_prompt",
    },
    {
        "case_name": "system_message",
        "prompt_fixture": "basic_prompt_with_system_message",
        "response_fixture": "response_to_basic_prompt_with_system_message",
        "models": TEST_MODELS,
        "cassette_suffix": "basic_prompt_with_system_message",
    },
    {
        "case_name": "three_messages",
        "prompt_fixture": "basic_prompt_with_three_messages",
        "response_fixture": "response_to_basic_prompt_with_three_messages",
        "models": MODELS_WITH_TEXT_INPUT,
        "cassette_suffix": "basic_prompt_with_three_messages",
    },
    # Enable tool-related tests - Google Gemini now supports tools
    # {
    #     "case_name": "one_tool",
    #     "prompt_fixture": "basic_prompt_with_one_tool",
    #     "response_fixture": "response_to_basic_prompt_with_one_tool",
    #     "models": MODELS_WITH_TOOL_INPUT,
    #     "cassette_suffix": "basic_prompt_with_one_tool",
    # },
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
def google_client(kernel: Kernel):
    """Fixture for Google client with proper cleanup."""
    api_key = os.environ.get("GOOGLE_API_KEY", "UNUSED")
    client = GoogleClient(
        parameters=GooglePlatformParameters(
            google_api_key=SecretString(api_key),
        ),
    )
    client.attach_kernel(kernel)
    return client


# -------------------------------------------------------------------------
# HELPER FUNCTIONS
# -------------------------------------------------------------------------
def normalize_response(response: ResponseMessage) -> ResponseMessage:
    """
    Normalize a response message for Google-specific formatting.

    Google Gemini responses often:
    1. Include trailing newlines
    2. Insert newlines in XML-like elements
    3. Have different whitespace around content

    This function normalizes these differences to match expected responses.

    Args:
        response: The response message to normalize

    Returns:
        The normalized response message
    """

    for i, content_item in enumerate(response.content):
        if isinstance(content_item, ResponseTextContent):
            text = content_item.text

            # 1. First, strip trailing whitespace
            # (Gemini likes adding newlines at the end of responses)
            text = text.rstrip()

            # 3. Create a new content item with normalized text
            normalized_content = ResponseTextContent(text=text)
            response.content[i] = normalized_content

    return response


# -------------------------------------------------------------------------
# TESTS
# -------------------------------------------------------------------------
@pytest.mark.parametrize("case", TEST_CASES, ids=[c["case_name"] for c in TEST_CASES])
@pytest.mark.parametrize("model_id", ALL_MODELS)
async def test_google_generate_responses(request, google_client, case, model_id):
    """
    Test each (case, model_id) for generating responses (non-stream).
    """
    # Get the prompt + expected response from fixtures
    prompt = request.getfixturevalue(case["prompt_fixture"])
    await prompt.finalize_messages()
    expected_response = request.getfixturevalue(case["response_fixture"])

    # Unique cassette per test
    cassette_path = (
        f"platforms/google/test_e2e/"
        f"test_response_{case['cassette_suffix']}__{model_id}.yaml"
    )

    # Use VCR without patching
    with patched_vcr(cassette_path):
        # Convert the prompt
        google_prompt = await google_client.converters.convert_prompt(
            prompt,
            model_id=model_id,
        )

        # Generate the response
        response = await google_client.generate_response(
            google_prompt,
            model=model_id,
        )

    # Normalize the response before comparison
    normalized_response = normalize_response(response)
    compare_responses(normalized_response, expected_response)


@pytest.mark.parametrize("case", TEST_CASES, ids=[c["case_name"] for c in TEST_CASES])
@pytest.mark.parametrize("model_id", ALL_MODELS)
async def test_google_stream_responses(request, google_client, case, model_id):
    """
    Test each (case, model_id) for streaming responses.
    """
    prompt = request.getfixturevalue(case["prompt_fixture"])
    await prompt.finalize_messages()
    expected_response = request.getfixturevalue(case["response_fixture"])

    cassette_path = (
        f"platforms/google/test_e2e/"
        f"test_stream_response_{case['cassette_suffix']}__{model_id}.yaml"
    )

    # Use VCR without patching
    with patched_vcr(cassette_path):
        # Convert the prompt
        google_prompt = await google_client.converters.convert_prompt(
            prompt,
            model_id=model_id,
        )

        # Collect deltas from streaming
        deltas = []
        async for delta in google_client.generate_stream_response(
            google_prompt,
            model=model_id,
        ):
            deltas.append(delta)

        # Combine the streamed deltas into a single ResponseMessage
        response = ResponseMessage.model_validate(
            combine_generic_deltas(deltas),
        )
        if "_tool_input" in response.content:
            print("yes")

        print(response)
        # Normalize the response before comparison
        normalized_response = normalize_response(response)
        compare_responses(normalized_response, expected_response)
