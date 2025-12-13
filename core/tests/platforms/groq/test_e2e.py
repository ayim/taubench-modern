import os
from unittest.mock import MagicMock

import pytest

from agent_platform.core.delta import combine_generic_deltas
from agent_platform.core.kernel import Kernel
from agent_platform.core.platforms.configs import PlatformModelConfigs
from agent_platform.core.platforms.groq.client import GroqClient
from agent_platform.core.platforms.groq.parameters import GroqPlatformParameters
from agent_platform.core.responses.response import ResponseMessage
from agent_platform.core.utils import SecretString
from core.tests.platforms.conftest import compare_responses
from core.tests.vcrx import patched_vcr


def _parse_models_env(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [model.strip() for model in raw.split(",") if model.strip()]


def _build_models_allowlist(models: list[str]) -> dict[str, list[str]]:
    allowlist: dict[str, set[str]] = {}
    for model in models:
        try:
            _, provider, slug = model.split("/", 2)
        except ValueError:
            continue
        allowlist.setdefault(provider, set()).add(slug)
    return {provider: sorted(slugs) for provider, slugs in allowlist.items()}


_ENV_MODELS = _parse_models_env(os.getenv("GROQ_E2E_MODELS"))
_CONFIGURED_MODELS = [
    model for model in PlatformModelConfigs.models_capable_of_driving_agents if model.startswith("groq/")
]
_DEFAULT_MODELS = list(dict.fromkeys(["groq/openai/gpt-oss-20b", *_CONFIGURED_MODELS]))
MODELS_TO_TEST = _ENV_MODELS or _DEFAULT_MODELS

EXCLUDED_MODELS = [
    "groq/moonshotai/kimi-k2",  # just doesn't give consistent tool use outputs at this time
]
MODELS_TO_TEST = [model for model in MODELS_TO_TEST if model not in EXCLUDED_MODELS]

MODELS_ALLOWLIST = _build_models_allowlist(MODELS_TO_TEST)


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


@pytest.fixture
def kernel() -> Kernel:
    return MagicMock(spec=Kernel)


@pytest.fixture
def groq_client(kernel: Kernel) -> GroqClient:
    api_key = os.environ.get("GROQ_API_KEY", "UNUSED")
    parameters = GroqPlatformParameters(
        groq_api_key=SecretString(api_key),
        models=MODELS_ALLOWLIST or None,
    )
    client = GroqClient(parameters=parameters)
    client.attach_kernel(kernel)
    return client


@pytest.mark.parametrize("case", TEST_CASES, ids=[c["case_name"] for c in TEST_CASES])
@pytest.mark.parametrize("model_id", MODELS_TO_TEST)
async def test_groq_generate_responses(request, groq_client: GroqClient, case, model_id) -> None:
    """Test each (case, model_id) for generating responses (non-stream)."""
    if model_id not in case["models"]:
        pytest.skip(f"Model {model_id} not applicable to case '{case['case_name']}'")

    prompt = request.getfixturevalue(case["prompt_fixture"])
    await prompt.finalize_messages()
    expected_response = request.getfixturevalue(case["response_fixture"])

    cassette_path = f"platforms/groq/test_e2e/test_response_{case['cassette_suffix']}__{model_id}.yaml"

    with patched_vcr(cassette_path):
        groq_prompt = await groq_client.converters.convert_prompt(
            prompt,
            model_id=model_id,
        )
        response = await groq_client.generate_response(
            groq_prompt,
            model=model_id,
        )

    compare_responses(response, expected_response)


@pytest.mark.parametrize("case", TEST_CASES, ids=[c["case_name"] for c in TEST_CASES])
@pytest.mark.parametrize("model_id", MODELS_TO_TEST)
async def test_groq_stream_responses(request, groq_client: GroqClient, case, model_id) -> None:
    """Test each (case, model_id) for streaming responses."""
    if model_id not in case["models"]:
        pytest.skip(f"Model {model_id} not applicable to case '{case['case_name']}'")

    prompt = request.getfixturevalue(case["prompt_fixture"])
    await prompt.finalize_messages()
    expected_response = request.getfixturevalue(case["response_fixture"])

    cassette_path = f"platforms/groq/test_e2e/test_stream_response_{case['cassette_suffix']}__{model_id}.yaml"

    with patched_vcr(cassette_path):
        groq_prompt = await groq_client.converters.convert_prompt(
            prompt,
            model_id=model_id,
        )

        deltas = []
        async for delta in groq_client.generate_stream_response(
            groq_prompt,
            model=model_id,
        ):
            deltas.append(delta)

        response = ResponseMessage.model_validate(
            combine_generic_deltas(deltas),
        )

    compare_responses(response, expected_response)
