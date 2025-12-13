import functools
import logging
import time
from collections.abc import Callable
from typing import Any

from vcr.errors import CannotOverwriteExistingCassetteException

from core.tests.vcrx.util import (
    is_openai_models,
    is_transient_body,
    serialize_httpx_headers,
    should_skip_record,
)

_HTTPX_SHIM_INSTALLED = False
_LOGGER = logging.getLogger("tests.vcr.httpx_shim")


def _get_request_from_args(*args: Any, **kwargs: Any) -> tuple[Any | None, Any | None]:
    """Extracts the httpx client and request from VCR's patched args."""
    client, req = None, None
    if len(args) >= 2:
        client, req = args[0], args[1]
    elif "request" in kwargs:
        req = kwargs["request"]
    return client, req


def _should_record_response(cassette: Any, vcr_request: Any, response: Any) -> bool:
    """Determines if a given response should be recorded to the cassette."""
    try:
        status_code = int(getattr(response, "status_code", 0))
    except (ValueError, TypeError):
        status_code = 0

    if should_skip_record(status_code):
        return False

    uri = str(getattr(vcr_request, "uri", ""))
    if is_openai_models(uri):
        if status_code >= 500 or is_transient_body(getattr(response, "text", "")):
            return False
        # Record the first successful /v1/models response, but skip subsequent ones.
        if getattr(cassette, "_ap_openai_models_recorded", False):
            return False

    return True


def _perform_cassette_append(cassette: Any, vcr_request: Any, response: Any) -> None:
    """Appends a response to the cassette and handles special flags."""
    cassette.append(
        vcr_request,
        {
            "status_code": response.status_code,
            "http_version": response.http_version,
            "headers": serialize_httpx_headers(response),
            "content": response.text,
        },
    )
    if is_openai_models(str(getattr(vcr_request, "uri", ""))):
        cassette._ap_openai_models_recorded = True


def _create_async_send_shim(cassette: Any, real_async_send: Callable) -> Callable:
    """Creates the async VCR send function with custom recording logic."""
    from vcr.stubs import httpx_stubs

    @functools.wraps(real_async_send)
    async def async_vcr_send_shim(*args: Any, **kwargs: Any) -> Any:
        t0 = time.monotonic()
        client, req = _get_request_from_args(*args, **kwargs)

        if req is None:
            return await real_async_send(*args, **kwargs)

        vcr_request = httpx_stubs._make_vcr_request(req)
        if cassette.can_play_response_for(vcr_request):
            response = httpx_stubs._play_responses(cassette, req, vcr_request, client, kwargs)
            _LOGGER.info(
                "[VCR][playback] %s %s in %.4fs",
                vcr_request.method,
                vcr_request.uri,
                time.monotonic() - t0,
            )
            return response

        if cassette.write_protected and cassette.filter_request(vcr_request):
            raise CannotOverwriteExistingCassetteException(cassette=cassette, failed_request=vcr_request)

        real_response = await real_async_send(*args, **kwargs)
        t1 = time.monotonic()

        try:
            await real_response.aread()  # Ensure body is loaded for recording
        except Exception:
            pass  # Ignore errors if body is already read or stream is closed

        if _should_record_response(cassette, vcr_request, real_response):
            _perform_cassette_append(cassette, vcr_request, real_response)
            _LOGGER.info(
                "[VCR][record] %s %s sent in %.4fs, saved in %.4fs",
                vcr_request.method,
                vcr_request.uri,
                t1 - t0,
                time.monotonic() - t1,
            )
        return real_response

    return async_vcr_send_shim


def _create_sync_send_shim(cassette: Any, real_sync_send: Callable) -> Callable:
    """Creates the sync VCR send function with custom recording logic."""
    from vcr.stubs import httpx_stubs

    @functools.wraps(real_sync_send)
    def sync_vcr_send_shim(*args: Any, **kwargs: Any) -> Any:
        t0 = time.monotonic()
        client, req = _get_request_from_args(*args, **kwargs)

        if req is None:
            return real_sync_send(*args, **kwargs)

        vcr_request = httpx_stubs._make_vcr_request(req)
        if cassette.can_play_response_for(vcr_request):
            response = httpx_stubs._play_responses(cassette, req, vcr_request, client, kwargs)
            _LOGGER.info(
                "[VCR][playback] %s %s in %.4fs",
                vcr_request.method,
                vcr_request.uri,
                time.monotonic() - t0,
            )
            return response

        if cassette.write_protected and cassette.filter_request(vcr_request):
            raise CannotOverwriteExistingCassetteException(cassette=cassette, failed_request=vcr_request)

        real_response = real_sync_send(*args, **kwargs)
        t1 = time.monotonic()

        try:
            real_response.read()
        except Exception:
            pass

        if _should_record_response(cassette, vcr_request, real_response):
            _perform_cassette_append(cassette, vcr_request, real_response)
            _LOGGER.info(
                "[VCR][record] %s %s sent in %.4fs, saved in %.4fs",
                vcr_request.method,
                vcr_request.uri,
                t1 - t0,
                time.monotonic() - t1,
            )
        return real_response

    return sync_vcr_send_shim


def install_httpx_shim() -> None:
    """
    Install a streaming-safe httpx shim into VCR's httpx stubs.
    This is idempotent and safe to call multiple times.
    """
    global _HTTPX_SHIM_INSTALLED  # noqa: PLW0603
    if _HTTPX_SHIM_INSTALLED:
        return

    try:
        from vcr.patch import _HttpxAsyncClient_send, _HttpxSyncClient_send
        from vcr.stubs import httpx_stubs
    except ImportError:
        return  # VCR or httpx not available

    # Replace VCR's default send functions with our custom shims
    httpx_stubs.async_vcr_send = lambda c, r_send: _create_async_send_shim(c, _HttpxAsyncClient_send)
    httpx_stubs.sync_vcr_send = lambda c, r_send: _create_sync_send_shim(c, _HttpxSyncClient_send)

    _HTTPX_SHIM_INSTALLED = True
    _LOGGER.debug("VCR-safe httpx shim installed.")
