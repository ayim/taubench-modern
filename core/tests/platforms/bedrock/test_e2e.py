import logging
import os
import time
from unittest.mock import MagicMock

import pytest

from agent_platform.core.delta import combine_generic_deltas
from agent_platform.core.kernel import Kernel
from agent_platform.core.platforms.bedrock.client import BedrockClient
from agent_platform.core.platforms.bedrock.parameters import BedrockPlatformParameters
from agent_platform.core.platforms.configs import PlatformModelConfigs
from agent_platform.core.responses.content import ResponseTextContent
from agent_platform.core.responses.content.reasoning import ResponseReasoningContent
from agent_platform.core.responses.response import ResponseMessage
from core.tests.platforms.conftest import compare_responses
from core.tests.vcrx import patched_vcr

logger = logging.getLogger(__name__)


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

    # Pop any ReasoningContent items
    indices_of_reasoning_content = [
        i for i, content_item in enumerate(response.content) if isinstance(content_item, ResponseReasoningContent)
    ]
    for i in reversed(indices_of_reasoning_content):
        response.content.pop(i)

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
MODELS_TO_TEST = [
    model for model in PlatformModelConfigs.models_capable_of_driving_agents if model.startswith("bedrock/")
]

# TODO: get access to these if we want to e2e test them
NO_ACCESS_MODELS = [
    "bedrock/anthropic/claude-4-1-opus",
    "bedrock/anthropic/claude-4-1-opus-thinking-high",
    "bedrock/anthropic/claude-4-1-opus-thinking-medium",
    "bedrock/anthropic/claude-4-1-opus-thinking-low",
    "bedrock/meta/llama-4-scout",
    "bedrock/meta/llama-4-maverick",
    "bedrock/cohere/command-r-plus",
]

MODELS_TO_TEST = [model for model in MODELS_TO_TEST if model not in NO_ACCESS_MODELS]

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
    return client


# -------------------------------------------------------------------------
# TESTS
# -------------------------------------------------------------------------
@pytest.mark.parametrize("case", TEST_CASES, ids=[c["case_name"] for c in TEST_CASES])
@pytest.mark.parametrize("model_id", MODELS_TO_TEST)
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
    cassette_path = f"platforms/bedrock/test_e2e/test_response_{case['cassette_suffix']}__{model_id}.yaml"

    with patched_vcr(cassette_path):
        bedrock_prompt = await bedrock_client.converters.convert_prompt(
            prompt,
            model_id=model_id,
        )
        response = await bedrock_client.generate_response(
            bedrock_prompt,
            model=model_id,
        )

    final_response = normalize_response(response)
    compare_responses(final_response, expected_response)


@pytest.mark.parametrize("case", TEST_CASES, ids=[c["case_name"] for c in TEST_CASES])
@pytest.mark.parametrize("model_id", MODELS_TO_TEST)
async def test_bedrock_stream_responses(request, bedrock_client, case, model_id):
    """
    Test each (case, model_id) for streaming responses.
    """
    if model_id not in case["models"]:
        pytest.skip(f"Model {model_id} not applicable to case '{case['case_name']}'")

    overall_start = time.perf_counter()
    logger.info(
        "Starting stream test: case=%s model=%s",
        case["case_name"],
        model_id,
    )

    prompt = request.getfixturevalue(case["prompt_fixture"])
    await prompt.finalize_messages()
    expected_response = request.getfixturevalue(case["response_fixture"])

    cassette_path = f"platforms/bedrock/test_e2e/test_stream_response_{case['cassette_suffix']}__{model_id}.yaml"

    with patched_vcr(cassette_path):
        convert_start = time.perf_counter()
        bedrock_prompt = await bedrock_client.converters.convert_prompt(
            prompt,
            model_id=model_id,
        )
        convert_duration = time.perf_counter() - convert_start
        logger.info(
            "convert_prompt completed: case=%s model=%s duration=%.3fs",
            case["case_name"],
            model_id,
            convert_duration,
        )

        deltas = []
        stream_start = time.perf_counter()
        first_delta_time: float | None = None
        last_delta_time: float | None = None
        async for delta in bedrock_client.generate_stream_response(
            bedrock_prompt,
            model=model_id,
        ):
            now = time.perf_counter()
            deltas.append(delta)
            if first_delta_time is None:
                first_delta_time = now
                logger.info(
                    "first delta received: case=%s model=%s latency=%.3fs",
                    case["case_name"],
                    model_id,
                    first_delta_time - stream_start,
                )
            elif last_delta_time is not None:
                logger.debug(
                    "delta received: case=%s model=%s delta_index=%s gap=%.3fs",
                    case["case_name"],
                    model_id,
                    len(deltas),
                    now - last_delta_time,
                )
            last_delta_time = now

        stream_duration = time.perf_counter() - stream_start
        logger.info(
            "stream completed: case=%s model=%s deltas=%d duration=%.3fs",
            case["case_name"],
            model_id,
            len(deltas),
            stream_duration,
        )

        # Combine the streamed deltas into a single ResponseMessage
        combine_start = time.perf_counter()
        response = ResponseMessage.model_validate(
            combine_generic_deltas(deltas),
        )
        combine_duration = time.perf_counter() - combine_start
        logger.info(
            "combine_generic_deltas completed: case=%s model=%s duration=%.3fs",
            case["case_name"],
            model_id,
            combine_duration,
        )

    final_response = normalize_response(response)
    compare_responses(final_response, expected_response)

    overall_duration = time.perf_counter() - overall_start
    logger.info(
        "stream test finished: case=%s model=%s total_duration=%.3fs",
        case["case_name"],
        model_id,
        overall_duration,
    )
