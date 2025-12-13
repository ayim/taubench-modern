from logging import Logger
from pathlib import Path
from typing import Any

from agent_platform.core.platforms.base import PlatformClient


def log_token_usage(
    logger: Logger,
    usage: dict[str, Any],
) -> None:
    """Log token usage in a single concise line."""
    if not usage:
        logger.info("Token usage: unknown")
        return

    input_tokens = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)
    total_tokens = usage.get("total_tokens", 0)

    # Handle potentially nested cached/reasoning tokens
    cached_tokens = usage.get("cached_tokens", 0)
    if not cached_tokens and "input_tokens_details" in usage:
        cached_tokens = usage["input_tokens_details"].get("cached_tokens", 0)

    reasoning_tokens = usage.get("reasoning_tokens", 0)
    if not reasoning_tokens and "output_tokens_details" in usage:
        reasoning_tokens = usage["output_tokens_details"].get("reasoning_tokens", 0)

    parts = [
        f"total={total_tokens}",
        f"input={input_tokens}",
        f"output={output_tokens}",
    ]

    if cached_tokens > 0:
        cache_pct = (cached_tokens / input_tokens * 100) if input_tokens > 0 else 0
        parts.append(f"cached={cached_tokens}({cache_pct:.0f}%)")

    if reasoning_tokens > 0:
        parts.append(f"reasoning={reasoning_tokens}")

    logger.info(f"Token usage: {' '.join(parts)}")


def write_debug_prompt_yaml(
    platform_client: PlatformClient,
    logger: Logger,
    request: dict[str, Any],
) -> None:
    """Write the prompt request to a structured logs path as pretty YAML.

    - Path: logs/prompts/agent{id}/thread{id}/run{id}-{counter}.yaml
    - Multiline strings are rendered in literal block style for readability.
    """
    try:
        from ruamel.yaml import YAML
        from ruamel.yaml.scalarstring import LiteralScalarString
    except Exception as import_error:  # pragma: no cover - best-effort debug helper
        logger.exception("Failed to import ruamel.yaml for prompt debug dump: %s", import_error)
        return

    kernel = getattr(platform_client, "_internal_kernel", None)
    if kernel is None or getattr(kernel, "run", None) is None:
        logger.warning("Kernel or run context unavailable; skipping prompt debug dump")
        return

    run_ctx = kernel.run
    base_dir = Path("logs") / "prompts" / f"agent{run_ctx.agent_id}" / f"thread{run_ctx.thread_id}"
    base_dir.mkdir(parents=True, exist_ok=True)

    # Determine next index based on existing files for this run id
    existing_indices: list[int] = []
    for _p in base_dir.glob(f"run{run_ctx.run_id}-*.yaml"):
        try:
            stem = _p.stem  # e.g., run123-4
            index_part = stem.split("-")[-1]
            existing_indices.append(int(index_part))
        except Exception:
            continue
    next_index = (max(existing_indices) + 1) if existing_indices else 1
    file_path = base_dir / f"run{run_ctx.run_id}-{next_index}.yaml"

    def convert_multiline_strings(obj: Any) -> Any:
        if isinstance(obj, str):
            return LiteralScalarString(obj) if "\n" in obj else obj
        if isinstance(obj, list):
            return [convert_multiline_strings(item) for item in obj]
        if isinstance(obj, dict):
            return {key: convert_multiline_strings(value) for key, value in obj.items()}
        return obj

    yaml_request = convert_multiline_strings(request)

    yaml = YAML()
    yaml.default_flow_style = False
    yaml.width = 100
    yaml.indent(mapping=2, sequence=4, offset=2)

    try:
        with file_path.open("w", encoding="utf-8") as f:
            yaml.dump(yaml_request, f)
        logger.info("Wrote prompt debug YAML to %s", file_path)
    except Exception as write_error:  # pragma: no cover - best-effort debug helper
        logger.exception("Failed writing prompt debug YAML to %s: %s", file_path, write_error)


def build_llm_async_http_client(
    *,
    # Match OpenAI SDK defaults, with bumps to connect,
    # read, and keepalive_expiry. (And defaults to http2.)
    http2: bool = True,
    follow_redirects: bool = True,
    connect_timeout: float = 15.0,
    read_timeout: float = 1200.0,
    write_timeout: float = 600.0,
    pool_timeout: float = 600.0,
    max_connections: int = 1000,
    max_keepalive_connections: int = 100,
    keepalive_expiry: float = 90.0,
):
    """Return a configured httpx.AsyncClient for LLM traffic.

    Mirrors most OpenAI SDK defaults (follow_redirects, timeouts, limits) and only
    tunes a few knobs to better support long SSE and high-latency calls.
    """
    from httpx import AsyncClient, Limits, Timeout

    timeout = Timeout(
        connect=connect_timeout,
        read=read_timeout,
        write=write_timeout,
        pool=pool_timeout,
    )
    limits = Limits(
        max_connections=max_connections,
        max_keepalive_connections=max_keepalive_connections,
        keepalive_expiry=keepalive_expiry,
    )
    return AsyncClient(
        http2=http2,
        follow_redirects=follow_redirects,
        timeout=timeout,
        limits=limits,
    )
