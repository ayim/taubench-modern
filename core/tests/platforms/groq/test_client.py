from collections.abc import AsyncIterable, AsyncIterator, Iterable, Iterator
from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest

from agent_platform.core.delta import GenericDelta
from agent_platform.core.kernel import Kernel
from agent_platform.core.platforms.groq.client import GroqClient
from agent_platform.core.platforms.groq.parameters import GroqPlatformParameters
from agent_platform.core.platforms.groq.prompts import GroqPrompt
from agent_platform.core.prompts import Prompt, PromptTextContent, PromptUserMessage
from agent_platform.core.responses.content.text import ResponseTextContent
from agent_platform.core.responses.response import ResponseMessage
from agent_platform.core.utils import SecretString


class MockStreamResponse(AsyncIterable, Iterable):
    """Mock streaming response iterable."""

    def __init__(self, events: list[Any]):
        self._events = list(events)
        self._async_events = list(events)

    def __iter__(self) -> Iterator[Any]:
        yield from self._events

    def __aiter__(self) -> AsyncIterator[Any]:
        return self

    async def __anext__(self) -> Any:
        if not self._async_events:
            raise StopAsyncIteration
        return self._async_events.pop(0)


class MockResponses:
    def __init__(self) -> None:
        self.create = MagicMock()


class MockModels:
    def __init__(self, model_ids: list[str] | None = None) -> None:
        self._model_ids = model_ids or ["openai/gpt-oss-20b"]

    async def list(self) -> Any:
        from types import SimpleNamespace

        return SimpleNamespace(
            data=[SimpleNamespace(id=model_id) for model_id in self._model_ids],
        )


class MockOpenAIClient:
    def __init__(self, model_ids: list[str] | None = None) -> None:
        self.responses = MockResponses()
        self.models = MockModels(model_ids=model_ids)


@pytest.fixture
def groq_parameters() -> GroqPlatformParameters:
    return GroqPlatformParameters(groq_api_key=SecretString("test-key"))


@pytest.fixture
def groq_client(groq_parameters: GroqPlatformParameters) -> GroqClient:
    client = GroqClient(parameters=groq_parameters)
    mock_sdk = MockOpenAIClient()
    client._groq_client = cast("Any", mock_sdk)
    client._test_mock_client = mock_sdk
    return client


@pytest.mark.asyncio
async def test_generate_response(groq_client: GroqClient) -> None:
    prompt = Prompt(
        messages=[PromptUserMessage([PromptTextContent(text="Hello")])],
    )
    kernel = MagicMock(spec=Kernel)
    finalized = await prompt.finalize_messages(kernel)
    groq_prompt = await groq_client.converters.convert_prompt(
        finalized,
        model_id="openai/gpt-oss-20b",
    )

    mock_client = cast("Any", groq_client._test_mock_client)

    async def create_response(**kwargs: Any) -> Any:
        from types import SimpleNamespace

        from openai.types.responses import ResponseOutputMessage, ResponseOutputText

        output_message = ResponseOutputMessage(
            id="msg_1",
            type="message",
            role="assistant",
            status="completed",
            content=[
                ResponseOutputText(
                    type="output_text",
                    text="Hi there!",
                    annotations=[],
                    logprobs=None,
                )
            ],
        )
        return SimpleNamespace(
            id="resp_1",
            model=kwargs.get("model"),
            output=[output_message],
            usage=SimpleNamespace(  # type: ignore[arg-type]
                input_tokens=5,
                output_tokens=10,
                total_tokens=15,
                input_tokens_details=SimpleNamespace(cached_tokens=0),
                output_tokens_details=SimpleNamespace(reasoning_tokens=0),
            ),
        )

    mock_client.responses.create.side_effect = create_response

    response = await groq_client.generate_response(
        groq_prompt,
        model="groq/openai/gpt-oss-20b",
    )
    assert isinstance(response, ResponseMessage)
    assert isinstance(response.content[0], ResponseTextContent)
    assert response.content[0].text == "Hi there!"


@pytest.mark.asyncio
async def test_generate_stream_response(groq_client: GroqClient) -> None:
    groq_prompt = GroqPrompt(input=[], instructions=None)

    mock_client = cast("Any", groq_client._test_mock_client)

    async def create_stream(**kwargs: Any) -> MockStreamResponse:
        from openai.types.responses import ResponseTextDeltaEvent

        events = [
            ResponseTextDeltaEvent(
                type="response.output_text.delta",
                delta="Hello",
                content_index=0,
                item_id="msg_1",
                logprobs=[],
                output_index=0,
                sequence_number=1,
            ),
            ResponseTextDeltaEvent(
                type="response.output_text.delta",
                delta=" Groq",
                content_index=0,
                item_id="msg_1",
                logprobs=[],
                output_index=0,
                sequence_number=2,
            ),
        ]
        return MockStreamResponse(events)

    mock_client.responses.create.side_effect = create_stream

    deltas: list[GenericDelta] = []
    async for delta in groq_client.generate_stream_response(
        groq_prompt,
        model="groq/openai/gpt-oss-20b",
    ):
        deltas.append(delta)

    assert deltas
    assert any("Hello" in str(delta.value) for delta in deltas if delta.value is not None)


class MockOpenAIError(Exception):
    code: str | None = None


@pytest.mark.parametrize(
    "exception_cls,expected_code",  # noqa PT006
    [
        ("RateLimitError", "too_many_requests"),
        ("AuthenticationError", "unauthorized"),
        ("PermissionDeniedError", "forbidden"),
    ],
)
def test_handle_openai_error(
    exception_cls: str, expected_code: str, groq_client: GroqClient
) -> None:
    with patch(f"openai.{exception_cls}", MockOpenAIError):
        error = MockOpenAIError("boom")
        error.__class__.__name__ = exception_cls
        platform_error = groq_client._handle_openai_error(error, "groq/openai/gpt-oss-20b")
        assert platform_error.response.code == expected_code
