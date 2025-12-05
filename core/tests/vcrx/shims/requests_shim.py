from __future__ import annotations

from typing import Any

_REQUESTS_SHIM_INSTALLED = False


def install_requests_shim() -> None:
    """
    Patch VCR's requests stub so urllib3-based clients work during cassette playback.

    Google Vertex recordings include OAuth token refreshes performed via
    google-auth -> requests -> urllib3. When those calls are replayed, VCR's stub
    (`VCRHTTPResponse`) lacks the `version_string` attribute that urllib3 expects on
    the raw HTTP response, which causes AttributeError the first time we touch the
    cached cassette. Adding the property once keeps urllib3 behaving as if it were
    still talking to a real socket, so the Vertex credential flow can succeed.
    """
    global _REQUESTS_SHIM_INSTALLED  # noqa: PLW0603
    if _REQUESTS_SHIM_INSTALLED:
        return

    try:
        from vcr import stubs as vcr_stubs
    except ImportError:  # pragma: no cover - vcr not installed
        return

    response_cls: Any = getattr(vcr_stubs, "VCRHTTPResponse", None)
    if response_cls is None:
        return

    if not hasattr(response_cls, "version_string"):

        def _version_string(self: Any) -> str:  # pragma: no cover - trivial
            version = getattr(self, "version", None)
            if version in ("HTTP/1.0", 10):
                return "HTTP/1.0"
            return "HTTP/1.1"

        response_cls.version_string = property(_version_string)  # type: ignore[attr-defined]

    _REQUESTS_SHIM_INSTALLED = True
