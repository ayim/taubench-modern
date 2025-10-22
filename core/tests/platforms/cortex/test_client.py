import json
from collections.abc import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import HTTPStatusError, Request, Response, Timeout
from snowflake.snowpark import Session

from agent_platform.core.delta import GenericDelta
from agent_platform.core.errors import ErrorCode, PlatformHTTPError
from agent_platform.core.kernel import Kernel
from agent_platform.core.platforms.configs import (
    resolve_generic_model_id_to_platform_specific_model_id,
)
from agent_platform.core.platforms.cortex.client import CortexClient
from agent_platform.core.platforms.cortex.connect import SnowflakeAuthenticationError
from agent_platform.core.platforms.cortex.converters import CortexConverters
from agent_platform.core.platforms.cortex.parameters import CortexPlatformParameters
from agent_platform.core.platforms.cortex.parsers import CortexParsers
from agent_platform.core.platforms.cortex.prompts import CortexPrompt
from agent_platform.core.prompts import Prompt, PromptTextContent, PromptUserMessage
from agent_platform.core.responses.content.text import ResponseTextContent
from agent_platform.core.responses.response import ResponseMessage
from agent_platform.core.utils import SecretString


@pytest.fixture
def kernel() -> Kernel:
    """Fixture for the Kernel mock."""
    return MagicMock(spec=Kernel)


@pytest.fixture
def parameters() -> CortexPlatformParameters:
    """Fixture for CortexPlatformParameters with minimal required fields."""
    # Provide realistic defaults if needed
    return CortexPlatformParameters(
        snowflake_role="TEST_ROLE",
        snowflake_warehouse="TEST_WAREHOUSE",
        snowflake_database="TEST_DB",
        snowflake_schema="TEST_SCHEMA",
        snowflake_username="TEST_USER",
        snowflake_password=SecretString("TEST_PASSWORD"),
        snowflake_account="test_account.snowflakecomputing.com",
    )


@pytest.fixture
def mock_snowpark_session() -> MagicMock:
    """Fixture for mocking Snowpark Session."""
    mock_session = MagicMock(spec=Session)
    # You can customize additional attributes of the session if needed
    mock_session.connection = MagicMock()
    mock_session.connection.rest = MagicMock()
    mock_session.connection.rest.token = "DUMMY_TOKEN_VALUE"
    return mock_session


@pytest.fixture
def _mock_snowpark_init_session(
    mock_snowpark_session: MagicMock,
) -> Generator[None, None, None]:
    """
    Patch the internal `_init_session` method so that it always returns
    our mock_snowpark_session fixture.
    """
    with patch(
        "agent_platform.core.platforms.cortex.client.CortexClient._init_session",
        return_value=mock_snowpark_session,
    ):
        yield


@pytest.fixture
def cortex_client(
    kernel: Kernel,
    parameters: CortexPlatformParameters,
    mock_snowpark_session: MagicMock,
    _mock_snowpark_init_session: None,
) -> CortexClient:
    """
    Fixture for CortexClient, ensuring the Snowflake session is mocked.
    The client will be returned in an attached-kernel state,
    ready for testing methods.
    """
    client = CortexClient(parameters=parameters)
    client.attach_kernel(kernel)

    # Make sure we use the same session fixture
    client._cortex_runtime_session = mock_snowpark_session

    available_models = {
        "anthropic": [
            "claude-3-5-sonnet",
        ],
        "snowflake": [
            "snowflake-arctic-embed-m",
            "snowflake-arctic-embed-l",
        ],
        "voyage": [
            "voyage-multilingual",
        ],
    }
    CortexClient._GLOBAL_AVAILABLE_MODELS_CACHE.clear()
    CortexClient._GLOBAL_AVAILABLE_MODELS_CACHE.update(
        {provider: list(models) for provider, models in available_models.items()}
    )
    client._available_models_cache = {
        provider: list(models)
        for provider, models in CortexClient._GLOBAL_AVAILABLE_MODELS_CACHE.items()
    }
    return client


@pytest.fixture
def prompt() -> Prompt:
    """Fixture for a basic Prompt object."""
    return Prompt(
        system_instruction="You are a helpful assistant.",
        messages=[PromptUserMessage([PromptTextContent("Hello, world!")])],
    )


@pytest.fixture
def cortex_prompt() -> CortexPrompt:
    """Fixture for a basic CortexPrompt object."""
    return CortexPrompt()


# -----------------------------------------------------------------------------
# Basic Initialization Tests
# -----------------------------------------------------------------------------
def test_cortex_client_init(parameters: CortexPlatformParameters) -> None:
    """
    Test that the client initializes properly and has correct default attributes.
    """
    with patch("snowflake.snowpark.Session"):
        client = CortexClient(parameters=parameters)
        assert client.name == "cortex"
        assert isinstance(client.converters, CortexConverters)
        assert isinstance(client.parsers, CortexParsers)
        assert isinstance(client.parameters, CortexPlatformParameters)


def test_init_session_missing_auth_file(parameters: CortexPlatformParameters) -> None:
    """Missing sf-auth.json bubbles up a helpful unauthorized error."""

    client = CortexClient(parameters=parameters)
    error_message = "Failed to read authentication config: [Errno 2]"

    with patch(
        "agent_platform.core.platforms.cortex.connect.get_connection_details",
        side_effect=SnowflakeAuthenticationError(error_message),
    ):
        with pytest.raises(PlatformHTTPError) as excinfo:
            client._init_session(client.parameters)

    err = excinfo.value
    assert err.response.error_code == ErrorCode.UNAUTHORIZED
    assert "no linking details" in str(err)


# -----------------------------------------------------------------------------
# Internal Method Tests
# -----------------------------------------------------------------------------
@pytest.mark.usefixtures("_mock_snowpark_init_session")
@pytest.mark.asyncio
async def test_get_or_refresh_token(
    cortex_client: CortexClient,
    mock_snowpark_session: MagicMock,
) -> None:
    """
    Test that _get_or_refresh_token returns the existing token from the session.
    """
    mock_snowpark_session.connection.rest.token = "DUMMY_TOKEN"
    session, token = await cortex_client._get_or_refresh_token()
    assert token == "DUMMY_TOKEN"
    assert session is mock_snowpark_session

    # Test if no REST connection, it raises an error
    mock_snowpark_session.connection.rest = None
    with pytest.raises(ValueError, match="No REST connection found"):
        await cortex_client._get_or_refresh_token()


@pytest.mark.usefixtures("_mock_snowpark_init_session")
@pytest.mark.asyncio
async def test_build_url(
    cortex_client: CortexClient,
    mock_snowpark_session: MagicMock,
) -> None:
    """
    Test that _build_url constructs the correct Cortex completion URL.
    """
    host = "test-account.snowflakecomputing.com"
    mock_snowpark_session.connection.host = host

    url = await cortex_client._build_url()
    assert url == f"https://{host}/api/v2/cortex/inference:complete"


@pytest.mark.usefixtures("_mock_snowpark_init_session")
@pytest.mark.asyncio
async def test_build_headers(
    cortex_client: CortexClient,
    mock_snowpark_session: MagicMock,
) -> None:
    """
    Test that _build_headers returns the expected dictionary, including token.
    """

    # The fixture sets up the token as "DUMMY_TOKEN_VALUE"
    class AuthByKeyPair:  # mimic connector auth class name
        pass

    mock_snowpark_session.connection.auth_class = AuthByKeyPair
    headers = await cortex_client._build_headers(streaming=False)
    assert "Authorization" in headers
    assert headers["Authorization"] == 'Snowflake Token="DUMMY_TOKEN_VALUE"'
    assert headers["Accept"] == "application/json, text/event-stream"
    assert headers["Content-Type"] == "application/json"


@pytest.mark.usefixtures("_mock_snowpark_init_session")
@pytest.mark.asyncio
async def test_build_headers_oauth(
    cortex_client: CortexClient,
    mock_snowpark_session: MagicMock,
) -> None:
    """Ensure OAuth/key-pair auth uses Snowflake Token prefix."""
    mock_snowpark_session.connection.rest.token = "DUMMY_TOKEN_VALUE"

    class AuthByOAuth:  # mimic connector OAuth auth class name
        pass

    mock_snowpark_session.connection.auth_class = AuthByOAuth

    headers = await cortex_client._build_headers(streaming=False)
    assert headers["Authorization"] == 'Snowflake Token="DUMMY_TOKEN_VALUE"'


@pytest.mark.usefixtures("_mock_snowpark_init_session")
@pytest.mark.asyncio
async def test_build_headers_auth_instance(
    cortex_client: CortexClient,
    mock_snowpark_session: MagicMock,
) -> None:
    """Ensure OAuth/key-pair auth uses Snowflake Token prefix."""

    class AuthByOAuth:
        pass

    mock_snowpark_session.connection.rest.token = "DUMMY_TOKEN_VALUE"
    mock_snowpark_session.connection.auth_class = AuthByOAuth()

    headers = await cortex_client._build_headers(streaming=False)
    assert headers["Authorization"] == 'Snowflake Token="DUMMY_TOKEN_VALUE"'


# -----------------------------------------------------------------------------
# generate_response Tests
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_generate_response_success(
    cortex_client: CortexClient,
    cortex_prompt: CortexPrompt,
) -> None:
    """
    Test generate_response on success, ensuring parse_response is called
    and a ResponseMessage is returned.
    """
    from httpx import Response

    # Suppose we have a test model name
    test_model = "claude-3-5-sonnet"
    # We pretend that the mapping is direct for the test
    mock_raw_response_data = Response(
        status_code=200,
        content=json.dumps(
            {
                "choices": [
                    {"message": {"content": "mock api response"}},
                ],
            },
        ),
    )

    # Patch httpx.AsyncClient.post to return the mock data
    with patch("httpx.AsyncClient.post", return_value=mock_raw_response_data):
        response = await cortex_client.generate_response(cortex_prompt, test_model)

        # Check final result is a ResponseMessage
        assert isinstance(response, ResponseMessage)
        assert len(response.content) == 1
        assert isinstance(response.content[0], ResponseTextContent)
        assert response.content[0].text == "mock api response"


@pytest.mark.asyncio
async def test_generate_response_http_failure(
    cortex_client: CortexClient,
    cortex_prompt: CortexPrompt,
) -> None:
    """
    Test generate_response scenario where the HTTP status is not 200 (e.g. 400).
    We expect an HTTPError or some exception from httpx.
    """
    test_model = "claude-3-5-sonnet"  # Use a model that already exists in the model map

    # We create a mock that raises an httpx.HTTPStatusError
    async def mock_generate_response_failure(*args, **kwargs):
        from httpx import HTTPStatusError

        request = Request("POST", "http://test-url")
        response = Response(status_code=500, request=request)
        raise HTTPStatusError("Internal Server Error", request=request, response=response)

    # Only patch the _generate_response method
    with patch.object(
        cortex_client,
        "_generate_response",
        side_effect=mock_generate_response_failure,
    ):
        with pytest.raises(Exception, match="Internal Server Error"):
            await cortex_client.generate_response(cortex_prompt, test_model)


@pytest.mark.asyncio
async def test_generate_response_bad_request(
    cortex_client: CortexClient,
    cortex_prompt: CortexPrompt,
) -> None:
    """
    Test generate_response scenario where the HTTP status is not 200 (e.g. 400).
    We expect an HTTPError or some exception from httpx.
    """
    test_model = "claude-3-5-sonnet"  # Use a model that already exists in the model map

    # We create a mock that raises a PlatformHTTPError
    async def mock_generate_response_failure(*args, **kwargs):
        request = Request("POST", "http://test-url")
        response = Response(status_code=400, request=request)
        raise PlatformHTTPError(
            error_code=ErrorCode.BAD_REQUEST,
            message="Bad Request",
            data={"status_code": response.status_code},
        )

    # Only patch the _generate_response method
    with patch.object(
        cortex_client,
        "_generate_response",
        side_effect=mock_generate_response_failure,
    ):
        with pytest.raises(PlatformHTTPError, match="Bad Request"):
            await cortex_client.generate_response(cortex_prompt, test_model)


@pytest.mark.asyncio
async def test_generate_response_refreshes_session_on_unauthorized(
    cortex_client: CortexClient,
) -> None:
    """Ensure unauthorized responses trigger a session refresh and retry."""

    unauthorized_response = Response(
        status_code=401,
        content=b'{"message": "token expired"}',
        request=Request("POST", "https://cortex.test"),
    )
    success_payload = {"result": "ok"}
    success_response = Response(
        status_code=200,
        content=json.dumps(success_payload).encode(),
        request=Request("POST", "https://cortex.test"),
    )

    responses = [unauthorized_response, success_response]
    post_call_count = 0

    class AsyncClientMock:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def post(self, *args, **kwargs) -> Response:
            nonlocal post_call_count
            post_call_count += 1
            return responses.pop(0)

    refresh_mock = AsyncMock(return_value=cortex_client._cortex_runtime_session)

    client_instance = AsyncClientMock()

    class ClientContextManager:
        async def __aenter__(self) -> AsyncClientMock:
            return client_instance

        async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
            return None

    def client_factory(*args, **kwargs) -> ClientContextManager:
        return ClientContextManager()

    with (
        patch(
            "agent_platform.core.platforms.cortex.client.init_httpx_client",
            side_effect=client_factory,
        ),
        patch.object(cortex_client, "_refresh_session", refresh_mock),
    ):
        result = await cortex_client._generate_response({"prompt": "ping"})

    assert result == success_payload
    assert post_call_count == 2
    refresh_mock.assert_awaited_once()
    assert not responses


@pytest.mark.asyncio
async def test_generate_response_retries_on_retryable_status(
    cortex_client: CortexClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Transient HTTP failures should trigger Tenacity retries before succeeding."""

    request_payload = {"prompt": "ping"}
    success_payload = {"result": "ok"}

    failure_response = Response(
        status_code=500,
        content=b'{"message": "fail"}',
        request=Request("POST", "https://cortex.test/generate"),
    )
    success_response = Response(
        status_code=200,
        content=json.dumps(success_payload).encode(),
        request=Request("POST", "https://cortex.test/generate"),
    )

    responses = [failure_response, success_response]
    post_call_count = 0

    class AsyncClientMock:
        async def post(self, *args, **kwargs) -> Response:
            nonlocal post_call_count
            post_call_count += 1
            return responses.pop(0)

    client_instance = AsyncClientMock()

    class ClientContextManager:
        async def __aenter__(self) -> AsyncClientMock:
            return client_instance

        async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
            return None

    def client_factory(*args, **kwargs) -> ClientContextManager:
        return ClientContextManager()

    monkeypatch.setattr(CortexClient, "_BACKOFF_BASE_S", 0.0)
    monkeypatch.setattr(CortexClient, "_BACKOFF_MAX_S", 0.0)
    monkeypatch.setattr(CortexClient, "_MAX_RETRY_ATTEMPTS", 2)

    monkeypatch.setattr(
        cortex_client,
        "_build_url",
        AsyncMock(return_value="https://cortex.test/generate"),
    )
    monkeypatch.setattr(
        cortex_client,
        "_build_headers",
        AsyncMock(return_value={"Authorization": "token"}),
    )
    monkeypatch.setattr(
        "agent_platform.core.platforms.cortex.client.init_httpx_client",
        client_factory,
    )

    result = await cortex_client._generate_response(request_payload)

    assert result == success_payload
    assert post_call_count == 2
    assert not responses


# -----------------------------------------------------------------------------
# generate_stream_response Tests
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_generate_stream_response_success(
    cortex_client: CortexClient,
    cortex_prompt: CortexPrompt,
) -> None:
    """
    Test generate_stream_response on success, verifying that parse_stream_event
    is called on each chunk and yields GenericDeltas.
    """
    test_model = "claude-3-5-sonnet"

    # We'll simulate 2 lines of data plus one final stop line
    async def mock_stream_responder(*args, **kwargs) -> AsyncGenerator[str, None]:
        yield (
            'data: {"id":"01","model":"claude-3-5-sonnet","choices":[{"delta":{"'
            'content_list":[{"type":"text", "text":"This is a"}]}}],"usage":{}}'
        )
        yield (
            'data: {"id":"01","model":"claude-3-5-sonnet","choices":[{"delta":{"'
            'content_list":[{"type":"text", "text":" test"}]}}],"usage":{}}'
        )
        yield (
            'data: {"id":"01","model":"claude-3-5-sonnet","choices":[{"delta":{}}]'
            ',"usage":{"prompt_tokens":1,"completion_tokens":3,"total_tokens":4}}'
        )

    with (
        patch.object(
            cortex_client,
            "_generate_stream_response",
            side_effect=mock_stream_responder,
        ) as mock_internal_stream,
        patch.object(
            cortex_client,
            "_generate_platform_metadata",
            return_value={"final": "meta"},
        ),
    ):
        deltas: list[GenericDelta] = []
        async for delta in cortex_client.generate_stream_response(
            cortex_prompt,
            test_model,
        ):
            deltas.append(delta)

        # We should have called our internal streaming method once
        expected_request = cortex_prompt.as_platform_request(
            test_model,
            stream=True,
        )
        mock_internal_stream.assert_called_once_with(expected_request)

        # So we expect at least as many deltas as lines plus a few extra
        # for metadata and usage
        assert len(deltas) >= 5
        # They all are GenericDeltas
        assert all(isinstance(d, GenericDelta) for d in deltas)
        # We should have a delta with a path of /role and a value of "agent"
        assert any(d.path == "/role" and d.value == "agent" for d in deltas)
        # We should have a delta with a path of /content and a
        # value of [{"kind": "text", "text": "This is a"}]
        assert any(
            d.path == "/content" and d.value == [{"kind": "text", "text": "This is a"}]
            for d in deltas
        )
        # We should have a delta with a path of /content/0/text and a value " test"
        assert any(d.path == "/content/0/text" and d.value == " test" for d in deltas)
        # We should have a delta with a path of /usage/input_tokens and a value 1
        assert any(d.path == "/usage/input_tokens" and d.value == 1 for d in deltas)
        # We should have a delta with a path of /usage/output_tokens and a value 3
        assert any(d.path == "/usage/output_tokens" and d.value == 3 for d in deltas)
        # We should have a delta with a path of /usage/total_tokens and a value 4
        assert any(d.path == "/usage/total_tokens" and d.value == 4 for d in deltas)
        # We should have a delta with a path of /metadata and a value {"final": "meta"}
        assert any(d.path == "/metadata" and d.value == {"final": "meta"} for d in deltas)


@pytest.mark.asyncio
async def test_iter_stream_with_backoff_retries_on_transient_failure(
    cortex_client: CortexClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ensure streaming retries after transient HTTP failures and yields lines."""

    request_payload = {"prompt": "ping"}
    timeout = Timeout(5.0)
    call_count = 0

    async def mock_iter_stream_response_once(
        *,
        request: dict[str, object],
        timeout: Timeout,
    ) -> AsyncGenerator[str, None]:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            req = Request("POST", "https://cortex.test/stream")
            resp = Response(status_code=500, request=req)
            raise HTTPStatusError("Server error", request=req, response=resp)
        yield "line-one"
        yield "line-two"

    monkeypatch.setattr(
        cortex_client,
        "_iter_stream_response_once",
        mock_iter_stream_response_once,
    )

    monkeypatch.setattr(CortexClient, "_BACKOFF_BASE_S", 0.0)
    monkeypatch.setattr(CortexClient, "_BACKOFF_MAX_S", 0.0)
    monkeypatch.setattr(CortexClient, "_MAX_RETRY_ATTEMPTS", 2)

    lines: list[str] = []
    async for line in cortex_client._iter_stream_with_backoff(
        request=request_payload,
        timeout=timeout,
    ):
        lines.append(line)

    assert lines == ["line-one", "line-two"]
    assert call_count == 2


@pytest.mark.asyncio
async def test_iter_stream_with_backoff_retries_on_retryable_status(  # noqa: C901
    cortex_client: CortexClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A retryable HTTP status from the stream should trigger a retry."""

    request_payload = {"prompt": "ping"}
    timeout = Timeout(5.0)
    success_lines = ["line-one", "line-two"]

    class FakeStreamResponse:
        def __init__(
            self,
            *,
            status_code: int,
            body: bytes = b"",
            lines: list[str] | None = None,
        ) -> None:
            self._response = Response(
                status_code=status_code,
                content=body,
                request=Request("POST", "https://cortex.test/stream"),
            )
            self.status_code = status_code
            self.headers = self._response.headers
            self._lines = lines or []

        async def aread(self) -> bytes:
            return self._response.content or b""

        async def aiter_lines(self):
            for line in self._lines:
                yield line

        def raise_for_status(self) -> None:
            self._response.raise_for_status()

    responses_queue: list[FakeStreamResponse] = [
        FakeStreamResponse(status_code=500, body=b'{"message": "fail"}'),
        FakeStreamResponse(status_code=200, lines=success_lines),
    ]

    class FakeStreamContextManager:
        def __init__(self, response: FakeStreamResponse) -> None:
            self._response = response

        async def __aenter__(self) -> FakeStreamResponse:
            return self._response

        async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
            return None

    class FakeAsyncClient:
        def __init__(self) -> None:
            self.stream_call_count = 0

        def stream(self, *args, **kwargs) -> FakeStreamContextManager:
            self.stream_call_count += 1
            response = responses_queue.pop(0)
            return FakeStreamContextManager(response)

    client_instance = FakeAsyncClient()

    class ClientContextManager:
        async def __aenter__(self) -> FakeAsyncClient:
            return client_instance

        async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
            return None

    def client_factory(*args, **kwargs) -> ClientContextManager:
        return ClientContextManager()

    monkeypatch.setattr(
        cortex_client,
        "_build_url",
        AsyncMock(return_value="https://cortex.test/stream"),
    )
    monkeypatch.setattr(
        cortex_client,
        "_build_headers",
        AsyncMock(return_value={"Authorization": "token"}),
    )
    monkeypatch.setattr(
        "agent_platform.core.platforms.cortex.client.init_httpx_client",
        client_factory,
    )
    monkeypatch.setattr(CortexClient, "_BACKOFF_BASE_S", 0.0)
    monkeypatch.setattr(CortexClient, "_BACKOFF_MAX_S", 0.0)
    monkeypatch.setattr(CortexClient, "_MAX_RETRY_ATTEMPTS", 2)

    lines: list[str] = []
    async for line in cortex_client._iter_stream_with_backoff(
        request=request_payload,
        timeout=timeout,
    ):
        lines.append(line)

    assert lines == success_lines
    assert client_instance.stream_call_count == 2
    assert not responses_queue


@pytest.mark.asyncio
async def test_generate_stream_response_http_failure(
    cortex_client: CortexClient,
    cortex_prompt: CortexPrompt,
) -> None:
    """
    Test generate_stream_response scenario where we get a non-200 from streaming API.
    Should raise an HTTPError from httpx.
    """
    test_model = "claude-3-5-sonnet"

    async def mock_stream_failure(*args, **kwargs) -> AsyncGenerator[str, None]:
        from httpx import HTTPStatusError

        request = Request("POST", "http://test-url")
        response = Response(status_code=500, request=request)
        # Simulate the internal code raising after reading the status code
        raise HTTPStatusError(
            "Internal Server Error",
            request=request,
            response=response,
        )
        yield  # Unreachable, but needed for function signature

    async def _async_iter(
        generator: AsyncGenerator[GenericDelta, None],
    ) -> None:
        async for _ in generator:
            pass

    with patch.object(
        cortex_client,
        "_generate_stream_response",
        side_effect=mock_stream_failure,
    ):
        with pytest.raises(Exception, match="Internal Server Error"):
            await _async_iter(
                cortex_client.generate_stream_response(cortex_prompt, test_model),
            )


@pytest.mark.asyncio
async def test_generate_stream_response_bad_request(
    cortex_client: CortexClient,
    cortex_prompt: CortexPrompt,
) -> None:
    """
    Test generate_stream_response scenario where we get a non-200 from streaming API.
    Should raise an HTTPError from httpx.
    """
    test_model = "claude-3-5-sonnet"

    async def mock_stream_failure(*args, **kwargs) -> AsyncGenerator[str, None]:
        request = Request("POST", "http://test-url")
        response = Response(status_code=400, request=request)
        # Simulate the internal code raising after reading the status code
        raise PlatformHTTPError(
            error_code=ErrorCode.BAD_REQUEST,
            message="Bad Request",
            data={"status_code": response.status_code},
        )
        yield  # Unreachable, but needed for function signature

    async def _async_iter(
        generator: AsyncGenerator[GenericDelta, None],
    ) -> None:
        async for _ in generator:
            pass

    with patch.object(
        cortex_client,
        "_generate_stream_response",
        side_effect=mock_stream_failure,
    ):
        with pytest.raises(PlatformHTTPError, match="Bad Request"):
            await _async_iter(
                cortex_client.generate_stream_response(cortex_prompt, test_model),
            )


@pytest.mark.asyncio
async def test_generate_stream_response_refreshes_session_on_unauthorized(
    cortex_client: CortexClient,
) -> None:
    """Ensure streaming retries once after refreshing the session."""

    unauthorized_stream = Response(
        status_code=401,
        content=b'{"message": "token expired"}',
        request=Request("POST", "https://cortex.test"),
    )

    success_lines = (
        b'data: {"delta": {"content": [{"type": "text", "text": "chunk"}]}}\n\ndata: [DONE]\n\n'
    )
    success_stream = Response(
        status_code=200,
        content=success_lines,
        headers={"content-type": "text/event-stream"},
        request=Request("POST", "https://cortex.test"),
    )

    stream_responses = [unauthorized_stream, success_stream]
    stream_call_count = 0

    class StreamContextManager:
        def __init__(self, response: Response) -> None:
            self._response = response

        async def __aenter__(self) -> Response:
            return self._response

        async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
            return None

    class AsyncClientMock:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def stream(self, *args, **kwargs) -> StreamContextManager:
            nonlocal stream_call_count
            stream_call_count += 1
            return StreamContextManager(stream_responses.pop(0))

    refresh_mock = AsyncMock(return_value=cortex_client._cortex_runtime_session)

    client_instance = AsyncClientMock()

    class ClientContextManager:
        async def __aenter__(self) -> AsyncClientMock:
            return client_instance

        async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
            return None

    def client_factory(*args, **kwargs) -> ClientContextManager:
        return ClientContextManager()

    with (
        patch(
            "agent_platform.core.platforms.cortex.client.init_httpx_client",
            side_effect=client_factory,
        ),
        patch.object(cortex_client, "_refresh_session", refresh_mock),
    ):
        collected: list[str] = []
        async for chunk in cortex_client._generate_stream_response({"prompt": "ping"}):
            collected.append(chunk)

    assert collected == [
        'data: {"delta": {"content": [{"type": "text", "text": "chunk"}]}}',
        "data: [DONE]",
    ]
    assert stream_call_count == 2
    refresh_mock.assert_awaited_once()
    assert not stream_responses


# -----------------------------------------------------------------------------
# create_embeddings Tests
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("text_embedding_model", "expected_func_name"),
    [
        ("snowflake-arctic-embed-m", "EMBED_TEXT_768"),
        ("snowflake-arctic-embed-l", "EMBED_TEXT_1024"),
        ("voyage-multilingual", "EMBED_TEXT_1024"),
    ],
)
async def test_create_embeddings(
    cortex_client: CortexClient,
    mock_snowpark_session: MagicMock,
    text_embedding_model: str,
    expected_func_name: str,
) -> None:
    """
    Test the create_embeddings method for single-batch embeddings with different
    model IDs. Also confirm that total_tokens is calculated properly.
    """
    # Mock out ensure_warehouse_selected
    cortex_client._ensure_warehouse_selected = AsyncMock()

    # Mock the Snowflake row results
    mock_collect_result = [
        {"EMBEDDING": [0.1, 0.2, 0.3]},
    ]
    (
        mock_snowpark_session.create_dataframe.return_value.select.return_value.collect.return_value
    ) = mock_collect_result

    texts = ["This is a test"]

    result = await cortex_client.create_embeddings(texts, text_embedding_model)

    # Check we called ensure_warehouse_selected
    cortex_client._ensure_warehouse_selected.assert_awaited_once()

    # We expect the embeddings result to be correct
    assert "embeddings" in result
    assert result["embeddings"][0] == [0.1, 0.2, 0.3]
    assert result["model"] == text_embedding_model

    # Check usage tokens is length of text // 4
    expected_tokens = sum(len(t) // 4 for t in texts)
    assert result["usage"]["total_tokens"] == expected_tokens


@pytest.mark.asyncio
async def test_create_embeddings_empty_input(cortex_client: CortexClient) -> None:
    """
    Test that create_embeddings returns empty embeddings if no texts are provided.
    """
    text_embedding_model = "voyage-multilingual"

    result = await cortex_client.create_embeddings([], text_embedding_model)
    assert result["embeddings"] == []
    assert result["model"] == text_embedding_model
    assert result["usage"]["total_tokens"] == 0


@pytest.mark.asyncio
async def test_create_embeddings_model_selector(
    cortex_client: CortexClient,
    mock_snowpark_session: MagicMock,
) -> None:
    """
    Example test showing how you might incorporate a ModelSelector
    to pick a friendly model name, then pass it to create_embeddings.
    """
    mock_collect_result = [{"EMBEDDING": [0.1, 0.2, 0.3]}]
    (
        mock_snowpark_session.create_dataframe.return_value.select.return_value.collect.return_value
    ) = mock_collect_result

    selected_model_friendly_name = "snowflake-arctic-embed-m"

    texts = ["This is a test"]

    # Now call create_embeddings with the chosen model
    result = await cortex_client.create_embeddings(texts, selected_model_friendly_name)

    assert isinstance(result, dict)
    assert result["embeddings"] == [[0.1, 0.2, 0.3]]
    assert result["model"] == selected_model_friendly_name
    expected_tokens = sum(len(t) // 4 for t in texts)
    assert result["usage"]["total_tokens"] == expected_tokens


# -----------------------------------------------------------------------------
# _ensure_warehouse_selected Tests
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_ensure_warehouse_selected_already_set(
    cortex_client: CortexClient,
    mock_snowpark_session: MagicMock,
) -> None:
    """
    Test _ensure_warehouse_selected when the warehouse
    is already provided in parameters.
    """
    # We have the fixture set with snowflake_warehouse='TEST_WAREHOUSE'
    await cortex_client._ensure_warehouse_selected()
    # Should run a single sql call to USE WAREHOUSE
    mock_snowpark_session.sql.assert_called_once_with(
        "USE WAREHOUSE TEST_WAREHOUSE",
    )


@pytest.mark.asyncio
async def test_ensure_warehouse_selected_auto_selection(
    cortex_client: CortexClient,
    mock_snowpark_session: MagicMock,
    parameters: CortexPlatformParameters,
) -> None:
    """
    Test _ensure_warehouse_selected when no warehouse is set, so we must auto-detect.
    """
    from unittest.mock import call

    # Clear the warehouse on the parameters
    cortex_client._parameters = CortexPlatformParameters(
        snowflake_role=parameters.snowflake_role,
        snowflake_database=parameters.snowflake_database,
        snowflake_schema=parameters.snowflake_schema,
        snowflake_username=parameters.snowflake_username,
        snowflake_account=parameters.snowflake_account,
        # no warehouse
    )

    assert cortex_client._parameters.snowflake_warehouse is None

    # Configure the mock directly on the session object used by the client
    # The first call (SHOW WAREHOUSES) should return the mock warehouse list
    # The second call (USE WAREHOUSE) can return anything (or None)
    mock_sql_method = mock_snowpark_session.sql
    mock_sql_method.return_value.collect.side_effect = [
        [{"name": "AUTO_SELECTED_WH"}],  # Result for SHOW WAREHOUSES
        [],  # Result for USE WAREHOUSE (doesn't matter)
    ]

    await cortex_client._ensure_warehouse_selected()

    # Assert calls on the mock_sql method itself
    assert mock_sql_method.call_count == 2
    mock_sql_method.assert_has_calls(
        [
            call("SHOW WAREHOUSES"),
            call().collect(),
            call("USE WAREHOUSE AUTO_SELECTED_WH"),
            call().collect(),
        ],
    )

    # Assert calls on the collect() method of the return value of sql()
    assert mock_sql_method.return_value.collect.call_count == 2

    # Now the client should have updated its parameters with the newly chosen warehouse
    assert cortex_client._parameters.snowflake_warehouse == "AUTO_SELECTED_WH"


@pytest.mark.usefixtures("_mock_snowpark_init_session")
@pytest.mark.asyncio
async def test_get_available_models_reraises_show_models_error(
    cortex_client: CortexClient,
) -> None:
    CortexClient._GLOBAL_AVAILABLE_MODELS_CACHE.clear()
    cortex_client._available_models_cache.clear()

    error = PlatformHTTPError(
        error_code=ErrorCode.UNAUTHORIZED,
        message="SHOW MODELS permission denied",
    )

    with patch.object(
        CortexClient,
        "_list_models_via_show_models",
        side_effect=error,
    ):
        with pytest.raises(PlatformHTTPError) as excinfo:
            await cortex_client.get_available_models()

    assert excinfo.value.response.error_code == ErrorCode.UNAUTHORIZED
    assert "SHOW MODELS" in str(excinfo.value)


@pytest.mark.asyncio
async def test_resolve_generic_model_id_missing_provider_raises_platform_error(
    cortex_client: CortexClient,
) -> None:
    CortexClient._GLOBAL_AVAILABLE_MODELS_CACHE.clear()
    cortex_client._available_models_cache = {
        "anthropic": ["claude-3-5-sonnet"],
    }

    with pytest.raises(PlatformHTTPError) as excinfo:
        await resolve_generic_model_id_to_platform_specific_model_id(
            cortex_client,
            "cortex/openai/gpt-4-1",
        )

    assert excinfo.value.response.error_code == ErrorCode.BAD_REQUEST
    assert "provider" in str(excinfo.value).lower()
