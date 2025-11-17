"""Tests for the LiteLLM platform client."""

from collections.abc import Callable
from unittest.mock import MagicMock, patch

import httpx
import pytest

from agent_platform.core.errors.base import PlatformError, PlatformHTTPError
from agent_platform.core.errors.streaming import StreamingError
from agent_platform.core.platforms.litellm.client import LiteLLMClient
from agent_platform.core.platforms.litellm.parameters import LiteLLMPlatformParameters
from agent_platform.core.utils import SecretString


def _http_request() -> httpx.Request:
    """Create a fresh HTTPX request for OpenAI error construction."""
    return httpx.Request("POST", "https://litellm.test")


def _http_response(status_code: int) -> httpx.Response:
    """Create a fresh HTTPX response attached to a request."""
    return httpx.Response(status_code, request=_http_request())


def _passthrough_retry_decorator(**_kwargs):
    """Return a decorator that leaves the wrapped coroutine untouched."""

    def _decorator(func: Callable):
        return func

    return _decorator


def _instantiate_openai_error(class_name: str, *args, **kwargs):
    """Instantiate an OpenAI SDK error without importing at module level."""
    import openai

    error_cls = getattr(openai, class_name)
    return error_cls(*args, **kwargs)


@pytest.fixture
def parameters() -> LiteLLMPlatformParameters:
    """Provide LiteLLM parameters with explicit API key and base URL."""
    return LiteLLMPlatformParameters(
        litellm_api_key=SecretString("test-key"),
        litellm_base_url="https://router.litellm.local/v1",
    )


@pytest.fixture
def lite_llm_client(parameters: LiteLLMPlatformParameters) -> LiteLLMClient:
    """Instantiate a LiteLLMClient with the OpenAI SDK patched out."""
    with (
        patch(
            "agent_platform.core.platforms.litellm.client.build_llm_async_http_client",
            return_value=object(),
        ),
        patch("openai.AsyncOpenAI", return_value=MagicMock(name="AsyncOpenAI")),
    ):
        return LiteLLMClient(parameters=parameters)


class TestLiteLLMClient:
    """Focused tests on LiteLLM client behaviour."""

    def test_init_client_configures_openai_sdk(self, parameters: LiteLLMPlatformParameters) -> None:
        """Verify we construct AsyncOpenAI with the expected auth and routing settings."""
        http_client = object()
        openai_stub = MagicMock(name="AsyncOpenAI")
        with (
            patch(
                "agent_platform.core.platforms.litellm.client.build_llm_async_http_client",
                return_value=http_client,
            ),
            patch("openai.AsyncOpenAI", return_value=openai_stub) as mock_openai,
        ):
            client = LiteLLMClient(parameters=parameters)

        assert client._openai_client is openai_stub
        assert mock_openai.call_args.kwargs == {
            "api_key": "test-key",
            "base_url": "https://router.litellm.local/v1",
            "http_client": http_client,
            "default_headers": None,
        }

    @pytest.mark.asyncio
    async def test_call_with_retries_maps_rate_limit_errors(
        self,
        lite_llm_client: LiteLLMClient,
    ) -> None:
        """Ensure _call_with_retries converts OpenAI rate limits into HTTP-friendly errors."""

        async def failing_call():
            raise _instantiate_openai_error(
                "RateLimitError",
                "rate limited",
                response=_http_response(429),
                body=None,
            )

        with patch(
            "agent_platform.core.platforms.retry.build_openai_retry_decorator",
            new=_passthrough_retry_decorator,
        ):
            with pytest.raises(PlatformHTTPError) as excinfo:
                await lite_llm_client._call_with_retries(
                    failing_call, model="cortex/openai/o4-mini-low"
                )

        assert excinfo.value.response.code == "too_many_requests"
        assert excinfo.value.data["model"] == "cortex/openai/o4-mini-low"

    @pytest.mark.asyncio
    async def test_call_with_retries_raises_streaming_error_on_failure(
        self,
        lite_llm_client: LiteLLMClient,
    ) -> None:
        """Confirm stream=True swaps in StreamingError while retaining LiteLLM messaging."""

        async def failing_call():
            raise _instantiate_openai_error(
                "RateLimitError",
                "rate limited",
                response=_http_response(429),
                body=None,
            )

        with patch(
            "agent_platform.core.platforms.retry.build_openai_retry_decorator",
            new=_passthrough_retry_decorator,
        ):
            with pytest.raises(StreamingError) as excinfo:
                await lite_llm_client._call_with_retries(
                    failing_call,
                    model="cortex/openai/o4-mini-low",
                    stream=True,
                )

        assert excinfo.value.response.code == "too_many_requests"
        assert excinfo.value.data["model"] == "cortex/openai/o4-mini-low"

    def test_handle_bad_request_context_length(self, lite_llm_client: LiteLLMClient) -> None:
        """Validate context-length errors include the upstream message and data payload."""
        error = _instantiate_openai_error(
            "BadRequestError",
            "context exceeded",
            response=_http_response(400),
            body=None,
        )
        error.code = "context_length_exceeded"
        error.message = "Prompt was too long"

        result = lite_llm_client._handle_litellm_error(
            error,
            "cortex/openai/o4-mini-low",
            PlatformHTTPError,
        )

        assert isinstance(result, PlatformHTTPError)
        assert result.response.code == "bad_request"
        assert "context length limit" in result.response.message
        assert result.data["error_message"] == "Prompt was too long"

    def test_handle_bad_request_unsupported_value(self, lite_llm_client: LiteLLMClient) -> None:
        """Check the org-verification guidance is surfaced for unsupported_value errors."""
        error = _instantiate_openai_error(
            "BadRequestError",
            "unsupported stream",
            response=_http_response(400),
            body=None,
        )
        error.code = "unsupported_value"

        result = lite_llm_client._handle_litellm_error(
            error,
            "cortex/openai/o4-mini-low",
            PlatformHTTPError,
        )

        assert isinstance(result, PlatformHTTPError)
        assert result.response.code == "bad_request"
        assert "organization must be verified" in result.response.message

    @pytest.mark.parametrize(
        ("error_factory", "expected_code"),
        [
            pytest.param(
                lambda: _instantiate_openai_error(
                    "AuthenticationError",
                    "auth failed",
                    response=_http_response(401),
                    body=None,
                ),
                "unauthorized",
                id="authentication",
            ),
            pytest.param(
                lambda: _instantiate_openai_error(
                    "PermissionDeniedError",
                    "forbidden",
                    response=_http_response(403),
                    body=None,
                ),
                "forbidden",
                id="permission",
            ),
            pytest.param(
                lambda: _instantiate_openai_error(
                    "NotFoundError",
                    "missing model",
                    response=_http_response(404),
                    body=None,
                ),
                "not_found",
                id="not_found",
            ),
            pytest.param(
                lambda: _instantiate_openai_error(
                    "UnprocessableEntityError",
                    "unprocessable",
                    response=_http_response(422),
                    body=None,
                ),
                "unprocessable_entity",
                id="unprocessable",
            ),
            pytest.param(
                lambda: _instantiate_openai_error(
                    "APIConnectionError",
                    message="connection issue",
                    request=_http_request(),
                ),
                "unexpected",
                id="api_connection",
            ),
            pytest.param(
                lambda: _instantiate_openai_error(
                    "APITimeoutError",
                    request=_http_request(),
                ),
                "unexpected",
                id="api_timeout",
            ),
            pytest.param(
                lambda: _instantiate_openai_error(
                    "InternalServerError",
                    "server blew up",
                    response=_http_response(500),
                    body=None,
                ),
                "unexpected",
                id="internal_server",
            ),
            pytest.param(
                lambda: _instantiate_openai_error(
                    "APIError",
                    "api error",
                    request=_http_request(),
                    body=None,
                ),
                "unexpected",
                id="api_error",
            ),
        ],
    )
    def test_handle_common_openai_errors_maps_to_platform_codes(
        self,
        error_factory: Callable[[], Exception],
        expected_code: str,
        lite_llm_client: LiteLLMClient,
    ) -> None:
        """Ensure the bespoke OpenAI errors are translated into PlatformHTTPError instances."""
        error = error_factory()

        result = lite_llm_client._handle_litellm_error(
            error,
            "cortex/openai/o4-mini-low",
            PlatformHTTPError,
        )

        assert isinstance(result, PlatformHTTPError)
        assert result.response.code == expected_code
        assert result.data["model"] == "cortex/openai/o4-mini-low"

    def test_handle_unexpected_error_falls_back_to_platform_error(
        self,
        lite_llm_client: LiteLLMClient,
    ) -> None:
        """Guard that unknown exceptions still become PlatformError instances."""

        class CustomError(Exception):
            pass

        err = CustomError("boom")
        result = lite_llm_client._handle_litellm_error(err, "cortex/openai/o4-mini-low")

        assert isinstance(result, PlatformError)
        assert result.response.code == "unexpected"
        assert result.data["error"] == "boom"
