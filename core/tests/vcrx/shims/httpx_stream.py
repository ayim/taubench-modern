import contextlib
import functools
import logging
from collections.abc import AsyncIterator, Callable
from typing import Any

import httpx
from vcr.record_mode import RecordMode
from vcr.stubs import httpx_stubs

from core.tests.vcrx.env import get_vcr_record_mode
from core.tests.vcrx.util import serialize_httpx_headers

_LOGGER = logging.getLogger(__name__)


class _ReplayStreamContextManager:
    """An async context manager that returns a replayed httpx.Response."""

    def __init__(self, response: httpx.Response):
        self._response = response

    async def __aenter__(self) -> httpx.Response:
        return self._response

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        # No resources to clean up, so we don't suppress exceptions.
        return False


class _RecordingStreamContextManager:
    """
    Wraps an original httpx stream context manager to record the streaming
    body before it's consumed by the client.
    """

    def __init__(self, cassette: Any, original_cm: contextlib.AbstractAsyncContextManager):
        self._cassette = cassette
        self._original_cm = original_cm
        self._response: httpx.Response | None = None
        self._buffer: list[str] = []

    async def _wrap_aiter_lines(self, original_aiter: Callable[[], AsyncIterator[str]]):
        """Wraps the line iterator to populate the internal buffer."""
        async for line in original_aiter():
            self._buffer.append(line)
            yield line

    async def __aenter__(self) -> httpx.Response:
        self._response = await self._original_cm.__aenter__()
        assert self._response is not None, "Stream context manager failed to return a response."

        # Monkey-patch the response's line iterator with our recording wrapper
        self._response.aiter_lines = functools.partial(self._wrap_aiter_lines, self._response.aiter_lines)
        return self._response

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> Any:
        # First, call the original exit method to perform cleanup.
        # Its result determines if the exception is suppressed.
        exit_result = await self._original_cm.__aexit__(exc_type, exc, tb)

        # Then, perform our recording logic only if no exception occurred.
        # This is wrapped in a try/except to prevent recording failures
        # from interfering with the original exception flow.
        if exc is None and get_vcr_record_mode() != RecordMode.NONE and self._response:
            try:
                vcr_request = httpx_stubs._make_vcr_request(self._response.request)
                if not self._cassette.can_play_response_for(vcr_request):
                    content = "\n".join(self._buffer)
                    self._cassette.append(
                        vcr_request,
                        {
                            "status_code": self._response.status_code,
                            "http_version": self._response.http_version,
                            "headers": serialize_httpx_headers(self._response),
                            "content": content,
                        },
                    )
            except Exception:
                _LOGGER.exception("VCR: Failed to record streaming response.")

        return exit_result


def _create_stream_patcher(cassette: Any, original_stream_method: Callable) -> Callable:
    """Creates the patched implementation of httpx.AsyncClient.stream."""

    @functools.wraps(original_stream_method)
    def _vcr_stream(client: httpx.AsyncClient, method: str, url: Any, **kwargs: Any):
        # Attempt pure playback if in NONE mode.
        if get_vcr_record_mode() == RecordMode.NONE:
            try:
                req = client.build_request(method=method, url=url, **kwargs)
                vcr_request = httpx_stubs._make_vcr_request(req)
                if cassette.can_play_response_for(vcr_request):
                    resp = httpx_stubs._play_responses(cassette, req, vcr_request, client, kwargs)
                    return _ReplayStreamContextManager(resp)
            except Exception:
                # Fall through to the original method if replay fails.
                pass

        # For recording modes, wrap the original stream in our recorder.
        original_cm = original_stream_method(client, method, url, **kwargs)
        return _RecordingStreamContextManager(cassette, original_cm)

    return _vcr_stream


@contextlib.contextmanager
def patch_httpx_stream(cassette: Any):
    """
    Context manager to patch httpx.AsyncClient.stream for recording and replaying.
    """
    original_stream = httpx.AsyncClient.stream
    vcr_stream_method = _create_stream_patcher(cassette, original_stream)

    httpx.AsyncClient.stream = vcr_stream_method
    try:
        yield
    finally:
        httpx.AsyncClient.stream = original_stream
