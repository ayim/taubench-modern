import vcr
from vcr.matchers import query as vcr_query
from vcr.request import Request

from core.tests.vcrx.config import CASSETTE_ROOT_DIR
from core.tests.vcrx.env import debug, get_vcr_record_mode
from core.tests.vcrx.persisters.zip_archive import ZipArchivePersister

# --- Custom Matchers ---


def _method_ci(r1: Request, r2: Request) -> None:
    """Case-insensitive method matcher."""
    if r1.method.upper() != r2.method.upper():
        raise AssertionError(f"Methods do not match: {r1.method} != {r2.method}")


def _normalize_host(host: str | None, path: str | None) -> str:
    """Normalize hosts for services that vary by subdomain.

    Azure OpenAI endpoints commonly use per-resource subdomains like
    "<anything>.openai.azure.com". For replay stability across environments,
    collapse any such subdomain to a stable token when the path targets
    Azure OpenAI routes (both classic deployment routes and the v1 routes).
    """
    h = (host or "").lower()
    p = path or ""

    # Normalize any host ending with ".openai.azure.com" when using Azure
    # OpenAI-style paths (e.g. "/openai/v1/..." or "/openai/deployments/...").
    if h.endswith(".openai.azure.com") and p.startswith("/openai/"):
        return "openai.azure.com"

    return h


def _host_norm(r1: Request, r2: Request) -> None:
    """Normalized host matcher for debugging (Azure-friendly)."""
    h1 = _normalize_host(r1.host, r1.path)
    h2 = _normalize_host(r2.host, r2.path)
    debug(f"[VCR] match host: {h1} ?= {h2}")
    if h1 != h2:
        raise AssertionError(f"Hosts do not match: {r1.host} != {r2.host}")


def _normalize_path(path: str | None) -> str:
    """Normalize variable path segments across environments.

    - Azure OpenAI embeds the deployment name in the path:
      "/openai/deployments/<deployment>/...". Replace the deployment segment
      with a stable token to allow cassettes to replay regardless of the
      specific deployment name used when recording vs. replaying.
    """
    p = (path or "").rstrip("/")
    if p.startswith("/openai/deployments/"):
        parts = p.split("/")
        # ['', 'openai', 'deployments', '<deployment>', ...]
        if len(parts) >= 4 and parts[1] == "openai" and parts[2] == "deployments":
            parts[3] = "<deployment>"
            p = "/".join(parts)
    return p


def _path_norm(r1: Request, r2: Request) -> None:
    """Normalized path matcher for debugging (Azure-friendly)."""
    p1 = _normalize_path(r1.path)
    p2 = _normalize_path(r2.path)
    debug(f"[VCR] match path: {p1} ?= {p2}")
    if p1 != p2:
        raise AssertionError(f"Paths do not match: {r1.path} != {r2.path}")


def _query_dbg(r1: Request, r2: Request) -> None:
    """Query matcher with added debug logging."""
    debug(f"[VCR] match query: {r1.query} ?= {r2.query}")
    vcr_query(r1, r2)


def build_vcr() -> vcr.VCR:
    """
    Builds and configures a VCR instance with custom matchers, filters,
    and a zip-based persister.
    """
    our_vcr = vcr.VCR(
        cassette_library_dir=CASSETTE_ROOT_DIR,
        record_mode=get_vcr_record_mode(),
        ignore_localhost=True,
        decode_compressed_response=False,
        filter_headers=[
            "authorization",
            "api-key",  # Azure OpenAI
            "x-goog-api-key",  # Google Gemini
            "x-api-key",  # Anthropic
        ],
        filter_query_parameters=[
            "api_key",
            "key",
            "X-Goog-Api-Key",
        ],
    )

    # Register all custom matchers.
    our_vcr.register_matcher("method_ci", _method_ci)
    our_vcr.register_matcher("host_norm", _host_norm)
    our_vcr.register_matcher("path_norm", _path_norm)
    our_vcr.register_matcher("query_dbg", _query_dbg)

    # Replace default matchers with our custom, debug-friendly versions.
    default_matchers = list(our_vcr.match_on)
    customized_matchers = []
    matcher_map = {
        "method": "method_ci",
        "host": "host_norm",
        "path": "path_norm",
        "query": "query_dbg",
    }
    for m in default_matchers:
        customized_matchers.append(matcher_map.get(m, m))

    our_vcr.match_on = tuple(customized_matchers)

    our_vcr.register_persister(ZipArchivePersister)
    return our_vcr
