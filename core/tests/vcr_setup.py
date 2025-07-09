import os
from contextlib import contextmanager


def _install_patches():  # noqa: C901, PLR0915
    from vcr.stubs import httpx_stubs

    undo = []

    # _shared_vcr_send patch to fix an issue with keyword arguments
    def patched_shared_vcr_send(cassette, real_send, *args, **kwargs):
        if len(args) >= 2:
            real_request = args[1]
        elif "request" in kwargs:
            real_request = kwargs["request"]
        else:
            raise ValueError("Could not find request in args or kwargs")

        vcr_request = httpx_stubs._make_vcr_request(real_request, **kwargs)

        if cassette.can_play_response_for(vcr_request):
            return vcr_request, httpx_stubs._play_responses(
                cassette,
                real_request,
                vcr_request,
                args[0] if len(args) >= 1 else kwargs.get("client", None),
                kwargs,
            )

        if cassette.write_protected and cassette.filter_request(vcr_request):
            from vcr.errors import CannotOverwriteExistingCassetteException

            raise CannotOverwriteExistingCassetteException(
                cassette=cassette,
                failed_request=vcr_request,
            )

        httpx_stubs._logger.info(
            "%s not in cassette, sending to real server",
            vcr_request,
        )
        return vcr_request, None

    # Patch the record functions to forcibly consume streams
    # This is important as we have a lot of SSE-based streaming requests
    # and responses that VCR stuggles a bit with
    def _record_responses_sync_patched(cassette, vcr_request, real_response):
        for past_real_response in real_response.history:
            past_vcr_request = httpx_stubs._make_vcr_request(past_real_response.request)
            cassette.append(
                past_vcr_request,
                httpx_stubs._to_serialized_response(past_real_response),
            )

        if real_response.history:
            vcr_request = httpx_stubs._make_vcr_request(real_response.request)

        # Force synchronous read if not already consumed
        if not real_response.is_stream_consumed:
            real_response.read()

        cassette.append(vcr_request, httpx_stubs._to_serialized_response(real_response))
        return real_response

    async def _record_responses_async_patched(cassette, vcr_request, real_response):
        for past_real_response in real_response.history:
            past_vcr_request = httpx_stubs._make_vcr_request(past_real_response.request)
            cassette.append(
                past_vcr_request,
                httpx_stubs._to_serialized_response(past_real_response),
            )

        if real_response.history:
            vcr_request = httpx_stubs._make_vcr_request(real_response.request)

        # Force async read if not already consumed
        if not real_response.is_stream_consumed:
            await real_response.aread()

        cassette.append(vcr_request, httpx_stubs._to_serialized_response(real_response))
        return real_response

    def patched_sync_vcr_send(cassette, real_send, *args, **kwargs):
        vcr_request, response = patched_shared_vcr_send(
            cassette,
            real_send,
            *args,
            **kwargs,
        )
        if response:
            args[0].cookies.extract_cookies(response)
            return response

        real_response = real_send(*args, **kwargs)
        return _record_responses_sync_patched(cassette, vcr_request, real_response)

    async def patched_async_vcr_send(cassette, real_send, *args, **kwargs):
        vcr_request, response = patched_shared_vcr_send(
            cassette,
            real_send,
            *args,
            **kwargs,
        )
        if response:
            args[0].cookies.extract_cookies(response)
            return response

        real_response = await real_send(*args, **kwargs)
        return await _record_responses_async_patched(cassette, vcr_request, real_response)

    httpx_stubs._async_vcr_send = patched_async_vcr_send

    # ------------------------------------------------------------------
    # Patch aiohttp_stubs.build_response for compatibility
    # ------------------------------------------------------------------
    from vcr.stubs import aiohttp_stubs

    original_build_response = aiohttp_stubs.build_response

    def patched_build_response(vcr_request, vcr_response, history):
        """Build an aiohttp MockClientResponse tolerant of older/newer cassette formats.

        We have two cassette layouts floating around in the repo:
        1. The default aiohttp layout (``status`` / ``body`` / optional ``url``).
        2. The httpx layout produced by our custom httpx patch
           (``status_code`` / ``content`` / ``http_version``).

        The stock ``build_response`` assumes #1.  When fed #2 it raises a
        ``TypeError`` because ``url`` is missing (``URL(None)``).

        Strategy:
        • If ``url`` is missing, fall back to the *request* URL.
        • If we have httpx-style keys, convert them to their aiohttp twins.
        """

        # If the cassette is in httpx format, normalise it first.
        if "status_code" in vcr_response:
            # httpx --> aiohttp field mapping
            vcr_response = {
                **vcr_response,
                "status": {
                    "code": vcr_response.pop("status_code"),
                    "message": vcr_response.get("reason", "OK"),
                },
                "body": {"string": vcr_response.pop("content", b"")},
            }

        # Ensure we always have a URL for the response object.
        vcr_response.setdefault("url", vcr_request.url)

        built = original_build_response(vcr_request, vcr_response, history)

        # Ensure raw_headers exists for aiobotocore compatibility
        if getattr(built, "_raw_headers", None) in (None, []):
            header_items = []
            for k, v in built.headers.items():
                if isinstance(v, tuple | list):
                    joined_val = ", ".join(str(item) for item in v)
                    header_items.append((k.encode("utf-8"), joined_val.encode("utf-8")))
                else:
                    header_items.append((k.encode("utf-8"), str(v).encode("utf-8")))
            # aiohttp exposes raw_headers as a cached_property (read-only);
            # the underlying storage is _raw_headers. Set that instead.
            built._raw_headers = tuple(header_items)

        return built

    def _swap(mod, attr, new):
        original = getattr(mod, attr)
        setattr(mod, attr, new)
        undo.append((mod, attr, original))

    _swap(httpx_stubs, "_shared_vcr_send", patched_shared_vcr_send)
    _swap(httpx_stubs, "_sync_vcr_send", patched_sync_vcr_send)
    _swap(httpx_stubs, "_async_vcr_send", patched_async_vcr_send)
    _swap(aiohttp_stubs, "build_response", patched_build_response)

    # Ensure MockStream has readchunk for aiohttp >=3.9 compatibility
    if not hasattr(aiohttp_stubs.MockStream, "readchunk"):

        async def _readchunk(self):
            data = await self.read()
            return data, False  # (chunk, end_of_chunk flag)

        aiohttp_stubs.MockStream.readchunk = _readchunk  # type: ignore[attr-defined]

    return lambda: [setattr(m, a, o) for m, a, o in undo]


# -------------------------------------------------------------------------
# Final VCR setup
def get_vcr_record_mode():
    from vcr.record_mode import RecordMode

    vcr_record_mode_raw = os.getenv("VCR_RECORD", "none")  # Default to 'none'

    # Need to parse it to vcr.record_mode.RecordMode
    record_mode = RecordMode.NONE
    if vcr_record_mode_raw == "none":
        record_mode = RecordMode.NONE
    elif vcr_record_mode_raw == "new_episodes":
        record_mode = RecordMode.NEW_EPISODES
    elif vcr_record_mode_raw == "once":
        record_mode = RecordMode.ONCE
    elif vcr_record_mode_raw == "all":
        record_mode = RecordMode.ALL
    else:
        raise ValueError(f"Invalid VCR record mode: {vcr_record_mode_raw}")

    return record_mode


@contextmanager
def patched_vcr(cassette_path: str, **use_kwargs):
    import vcr

    def _remove_headers_we_dont_care_about(response):
        # Remove 'Set-Cookie' header from the response
        response["headers"].pop("Set-Cookie", None)
        # Remove 'CF-RAY' header from the response (from cloudflare)
        response["headers"].pop("CF-RAY", None)

        return response

    def _mask_sensitive_url_parts(request):
        """Mask sensitive parts of URLs like endpoint domains and deployment names."""
        # Replace Azure OpenAI endpoint with a generic placeholder
        if "azure.com" in request.uri:
            # Replace with an example endpoint that isn't sensitive
            request.uri = request.uri.replace(
                request.host,
                "azure-openai-endpoint.example.com",
            )

            import re

            # Pattern to match: /openai/deployments/NAME/chat/completions
            deployment_pattern = r"/openai/deployments/([^/]+)/"
            request.uri = re.sub(
                deployment_pattern,
                "/openai/deployments/example-deployment-name/",
                request.uri,
            )
        return request

    our_vcr = vcr.VCR(
        cassette_library_dir="core/tests/fixtures/vcr_cassettes",
        record_mode=get_vcr_record_mode(),
        # TODO: locally, on OSX, some interaction between this
        # and file-related integration tests? Easiest fix is to
        # ignore localhost. Should investigate more.
        ignore_localhost=True,
        filter_headers=[
            "authorization",
            "api-key",  # For Azure OpenAI
            "x-goog-api-key",  # For Google
        ],
        filter_query_parameters=[
            "api_key",
        ],
        before_record_request=[
            _mask_sensitive_url_parts,
        ],
        before_record_response=[
            _remove_headers_we_dont_care_about,
        ],
    )

    undo_patches = _install_patches()
    try:
        with our_vcr.use_cassette(cassette_path, **use_kwargs):
            yield
    finally:
        undo_patches()
