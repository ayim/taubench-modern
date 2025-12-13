"""Utilities for constructing httpx clients that honor enterprise network settings."""

from typing import Any

from httpx import AsyncClient, Proxy, Timeout
from structlog.stdlib import get_logger

logger = get_logger(__name__)


def build_httpx_client_options() -> dict[str, Any]:
    """Return base keyword arguments for httpx clients with sema4 network settings.

    The helper inspects the optional sema4 network profile and, when available,
    configures certificate verification and proxies so enterprise TLS interception
    and proxy requirements are respected.
    """

    options: dict[str, Any] = {}

    try:
        from sema4ai_http import get_network_profile
    except Exception as exc:
        logger.debug(f"sema4ai_http helper not available: {exc!r}", exc_info=True)
        return options

    try:
        network_profile = get_network_profile()
    except Exception as exc:
        logger.debug(f"Failed to load sema4 network profile: {exc!r}", exc_info=True)
        return options

    if network_profile.ssl_context is not None:
        options["verify"] = network_profile.ssl_context

    proxies: dict[str, Proxy] = {}

    exclude_hosts = tuple(network_profile.proxy_config.no_proxy)
    if not exclude_hosts:
        exclude_hosts = None

    def _build_proxy(urls: list[str]) -> Proxy | None:
        if not urls:
            return None
        proxy_kwargs: dict[str, Any] = {}
        if exclude_hosts:
            proxy_kwargs["exclude_hosts"] = exclude_hosts
        return Proxy(urls[0], **proxy_kwargs)

    http_proxy = _build_proxy(network_profile.proxy_config.http)
    if http_proxy is not None:
        proxies["http://"] = http_proxy

    https_proxy = _build_proxy(network_profile.proxy_config.https)
    if https_proxy is not None:
        proxies["https://"] = https_proxy

    if proxies:
        options["proxies"] = proxies
        options.setdefault("trust_env", False)

    logger.debug(
        f"Initialized httpx client base options: has_ssl_context={bool(options.get('verify'))}"
        f",proxies={list(proxies.keys())}",
    )

    return options


def init_httpx_client(
    *,
    timeout: Timeout | float | int | None = None,
    **client_kwargs: Any,
) -> AsyncClient:
    """Instantiate an AsyncClient pre-configured with enterprise network settings."""

    options = build_httpx_client_options()
    if timeout is not None:
        options["timeout"] = timeout
    options.update(client_kwargs)
    return AsyncClient(**options)


__all__ = ["build_httpx_client_options", "init_httpx_client"]
