import contextlib
from collections.abc import AsyncIterator, Callable, Generator
from dataclasses import dataclass
from typing import Any

import vcr.patch
from aiobotocore.awsrequest import AioAWSResponse
from aiobotocore.httpsession import AIOHTTPSession
from botocore.compat import HTTPHeaders
from vcr.record_mode import RecordMode
from vcr.request import Request as VcrRequest

from core.tests.vcrx.env import debug, get_vcr_record_mode
from core.tests.vcrx.util import byteslike, serialize_aiobotocore_headers, should_skip_record


# The record for a streaming response remains the same.
@dataclass
class _BedrockStreamRecord:
    buf: bytearray
    request: Any
    status: int
    headers: dict[str, Any]
    saved: bool = False


class _ReplayStreamReader:
    """A fake stream reader that replays response body bytes from a cassette."""

    def __init__(self, data: bytes):
        self._data = data or b""
        self._was_read = False

    async def read(self) -> bytes:
        if self._was_read:
            return b""
        self._was_read = True
        return self._data

    async def iter_chunks(self) -> AsyncIterator[tuple[bytes, bool]]:
        if not self._was_read:
            self._was_read = True
            yield self._data, True


class _ReplayRawResponse:
    """Mocks the raw response object to satisfy aiobotocore's interface."""

    def __init__(self, data: bytes):
        self.content = _ReplayStreamReader(data)

    async def read(self) -> bytes:
        return await self.content.read()


class _StreamingBodyRecorder:
    """
    Wraps an aiohttp.StreamReader to record all bytes read from it into a buffer
    while proxying calls to the original client.
    """

    def __init__(self, original_stream: Any, buffer: bytearray):
        self._stream = original_stream
        self._buffer = buffer

    async def read(self, *args, **kwargs) -> bytes:
        chunk = await self._stream.read(*args, **kwargs)
        if chunk:
            self._buffer.extend(chunk)
        return chunk

    async def iter_chunks(self) -> AsyncIterator[tuple[bytes, bool]]:
        async for chunk, end_of_http_chunk in self._stream.iter_chunks():
            if chunk:
                self._buffer.extend(chunk)
            yield chunk, end_of_http_chunk

    async def iter_any(self) -> AsyncIterator[bytes]:
        async for chunk in self._stream.iter_any():
            if chunk:
                self._buffer.extend(chunk)
            yield chunk

    def __getattr__(self, name: str) -> Any:
        """Proxy any other attribute access to the original stream."""
        return getattr(self._stream, name)


class _BedrockPatcher:
    """
    Manages the logic for patching aiobotocore, replaying responses,
    and recording streaming/non-streaming interactions.
    """

    def __init__(self, cassette: Any):
        self.cassette = cassette
        self.streaming_records: list[_BedrockStreamRecord] = []
        self.original_send: Callable | None = None

    def _make_vcr_request(self, request: Any) -> VcrRequest:
        try:
            body = getattr(request, "body", b"")
            body_s = (
                body.decode("utf-8", "ignore")
                if isinstance(body, bytes | bytearray)
                else str(body or "")
            )
            headers = dict(getattr(request, "headers", {}) or {})
        except Exception:
            body_s, headers = "", {}
        return VcrRequest(request.method, str(request.url), body_s, headers)

    async def _handle_replay(self, vcr_request: VcrRequest) -> AioAWSResponse:
        vcr_response = self.cassette.play_response(vcr_request)
        status = vcr_response.get("status", {}).get("code") or vcr_response.get("status_code", 200)
        headers = {
            str(k).lower(): str(v[0] if isinstance(v, list) else v)
            for k, v in (vcr_response.get("headers") or {}).items()
        }
        body_data = vcr_response.get("body") or {}
        body_bytes = (
            byteslike(body_data.get("string"))
            if isinstance(body_data, dict)
            else byteslike(vcr_response.get("content", ""))
        )
        raw_response_mock = _ReplayRawResponse(body_bytes)
        http_headers = HTTPHeaders()
        for key, value in headers.items():
            http_headers[key] = value
        return AioAWSResponse(vcr_request.uri, int(status), http_headers, raw_response_mock)

    def _capture_streaming_response(self, vcr_request: VcrRequest, resp: Any):
        raw_response = getattr(resp, "raw", None)
        if not raw_response or not hasattr(raw_response, "content"):
            return
        original_content_stream = raw_response.content
        if not original_content_stream:
            return

        buf = bytearray()
        record = _BedrockStreamRecord(
            buf=buf,
            request=vcr_request,
            status=int(getattr(resp, "status", 200)),
            headers=serialize_aiobotocore_headers(resp),
        )
        self.streaming_records.append(record)
        raw_response.content = _StreamingBodyRecorder(original_content_stream, buf)

    async def _capture_json_response(self, vcr_request: VcrRequest, resp: Any):
        status = int(getattr(resp, "status", 0))
        if should_skip_record(status):
            return
        try:
            if not self.cassette.can_play_response_for(vcr_request):
                response_text = await resp.text
                response_body = {"string": response_text.encode("utf-8", "ignore")}
                self.cassette.append(
                    vcr_request,
                    {
                        "status_code": status,
                        "headers": serialize_aiobotocore_headers(resp),
                        "body": response_body,
                    },
                )
        except Exception as e:
            debug(f"[VCR][bedrock] Error recording JSON response: {e}")

    async def _handle_record(self, session: Any, request: Any) -> AioAWSResponse:
        assert self.original_send is not None, "Original send method not patched correctly."
        resp = await self.original_send(session, request)
        url_str = str(getattr(request, "url", ""))
        vcr_request = self._make_vcr_request(request)
        try:
            if "/converse-stream" in url_str:
                self._capture_streaming_response(vcr_request, resp)
            elif "/converse" in url_str:
                await self._capture_json_response(vcr_request, resp)
            elif any(
                endpoint in url_str for endpoint in ("/inference-profiles", "/foundation-models")
            ):
                await self._capture_json_response(vcr_request, resp)
        except Exception as e:
            debug(f"[VCR][bedrock] Failed to capture response for {url_str}: {e}")
        return resp

    async def _patched_send_logic(self, session: Any, request: Any) -> AioAWSResponse:
        vcr_request = self._make_vcr_request(request)
        if get_vcr_record_mode() == RecordMode.NONE and self.cassette.can_play_response_for(
            vcr_request
        ):
            return await self._handle_replay(vcr_request)
        debug(
            f"[VCR][aiohttp][send] mode={get_vcr_record_mode()} url={getattr(request, 'url', '')}"
        )
        return await self._handle_record(session, request)

    def save_recorded_streams(self):
        for rec in self.streaming_records:
            if rec.saved or not rec.buf or not rec.request or should_skip_record(rec.status):
                continue
            try:
                if not self.cassette.can_play_response_for(rec.request):
                    self.cassette.append(
                        rec.request,
                        {
                            "status_code": rec.status,
                            "headers": rec.headers,
                            "body": {"string": bytes(rec.buf)},
                        },
                    )
                    rec.saved = True
            except Exception as e:
                debug(f"[VCR][bedrock] Failed to save stream record: {e}")


@contextlib.contextmanager
def _suppress_vcr_aiohttp_patchers():
    """Temporarily disables VCR's built-in aiohttp patcher."""
    original_patcher = None
    try:

        def _noop_aiohttp_patcher(self: Any) -> Generator[Any, Any, None]:
            return self._build_patchers_from_mock_triples(())

        original_patcher = getattr(vcr.patch.CassettePatcherBuilder, "_aiohttp", None)
        if original_patcher:
            vcr.patch.CassettePatcherBuilder._aiohttp = _noop_aiohttp_patcher
    except (ImportError, AttributeError):
        pass
    try:
        yield
    finally:
        if original_patcher:
            try:
                vcr.patch.CassettePatcherBuilder._aiohttp = original_patcher
            except (ImportError, AttributeError):
                pass


@contextlib.contextmanager
def patch_bedrock(cassette_path: str, cassette: Any):
    """Context manager to patch aiobotocore for recording/replaying Bedrock interactions."""
    if not str(cassette_path).startswith("platforms/bedrock/"):
        yield
        return

    patcher = _BedrockPatcher(cassette)
    original_send = AIOHTTPSession.send
    if original_send is None:
        yield
        return

    patcher.original_send = original_send

    async def patched_send(self: AIOHTTPSession, request: Any) -> AioAWSResponse:
        """This function becomes the new AIOHTTPSession.send method."""
        return await patcher._patched_send_logic(self, request)

    AIOHTTPSession.send = patched_send
    with _suppress_vcr_aiohttp_patchers():
        try:
            yield
        finally:
            if patcher.original_send:
                AIOHTTPSession.send = patcher.original_send
            patcher.save_recorded_streams()
