import os

import vcr
from vcr.stubs import VCRHTTPResponse, httpx_stubs

# -------------------------------------------------------------------------
# (1) _shared_vcr_send patch to fix an issue with keyword arguments
original_shared_vcr_send = httpx_stubs._shared_vcr_send


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

    httpx_stubs._logger.info("%s not in cassette, sending to real server", vcr_request)
    return vcr_request, None


httpx_stubs._shared_vcr_send = patched_shared_vcr_send


# -------------------------------------------------------------------------
# (2) Patch the record functions to forcibly consume streams
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


original_sync_vcr_send = httpx_stubs._sync_vcr_send


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


httpx_stubs._sync_vcr_send = patched_sync_vcr_send


original_async_vcr_send = httpx_stubs._async_vcr_send


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


# -------------------------------------------------------------------------
# (3) Final VCR setup

# Reads an environment variable to set recording mode
VCR_RECORD_MODE = os.getenv("VCR_RECORD", "none")  # Default to 'none'

# Need to parse it to vcr.record_mode.RecordMode
record_mode = vcr.record_mode.RecordMode.NONE
if VCR_RECORD_MODE == "none":
    record_mode = vcr.record_mode.RecordMode.NONE
elif VCR_RECORD_MODE == "new_episodes":
    record_mode = vcr.record_mode.RecordMode.NEW_EPISODES
elif VCR_RECORD_MODE == "once":
    record_mode = vcr.record_mode.RecordMode.ONCE
elif VCR_RECORD_MODE == "all":
    record_mode = vcr.record_mode.RecordMode.ALL
else:
    raise ValueError(f"Invalid VCR record mode: {VCR_RECORD_MODE}")


# Patch VCRHTTPResponse to include version_string attribute
# This is a patch to make boto3 happy
original_init = VCRHTTPResponse.__init__


def patched_init(self, *args, **kwargs):
    original_init(self, *args, **kwargs)
    # Add version_string attribute if missing
    if not hasattr(self, "version_string"):
        self.version_string = "HTTP/1.1"


VCRHTTPResponse.__init__ = patched_init


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
    record_mode=record_mode,
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
