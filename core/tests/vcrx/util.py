from typing import Any
from urllib.parse import urlparse


def byteslike(data: Any) -> bytes:
    if isinstance(data, bytes | bytearray):
        return bytes(data)
    if isinstance(data, str):
        return data.encode("utf-8", "ignore")
    return bytes(data or b"")


def serialize_httpx_headers(resp: Any) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    try:
        raw = resp.headers.raw  # type: ignore[attr-defined]
    except Exception:
        raw = []
    for k, v in raw:
        try:
            key = k.decode("utf-8")
            val = v.decode("utf-8")
        except Exception:
            key = str(k)
            val = str(v)
        out.setdefault(key, []).append(val)
    return out


def serialize_aiobotocore_headers(resp: Any) -> dict[str, list[str]]:
    """
    Convert aiobotocore/botocore response headers into plain dict-of-lists.

    Botocore exposes headers as a HeadersDict with custom key types that are
    not safe to round-trip through YAML. Normalize to simple strings.
    """
    out: dict[str, list[str]] = {}
    try:
        items = getattr(resp, "headers", {}) or {}
        items = items.items() if hasattr(items, "items") else []
    except Exception:
        items = []
    for k, v in items:
        try:
            key = str(k)
            if isinstance(v, list | tuple):
                vals = [
                    str(x, "utf-8", "ignore") if isinstance(x, bytes | bytearray) else str(x)
                    for x in v
                ]
            else:
                vals = [str(v, "utf-8", "ignore") if isinstance(v, bytes | bytearray) else str(v)]
        except Exception:
            key, vals = str(k), [str(v)]
        out.setdefault(key, []).extend(vals)
    return out


def is_openai_models(url: str) -> bool:
    try:
        u = urlparse(url or "")
        return u.netloc == "api.openai.com" and u.path == "/v1/models"
    except Exception:
        return False


def is_transient_body(text: str) -> bool:
    t = (text or "").lower()
    return (
        "upstream connect error" in t
        or "reset before headers" in t
        or "connection termination" in t
    )


def should_skip_record(status_code: int) -> bool:
    return status_code == 429 or 500 <= status_code < 600
