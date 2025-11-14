"""Network utilities for enterprise SSL/proxy support."""

import logging

import requests
from requests.adapters import HTTPAdapter
from sema4ai_http import get_network_profile

logger = logging.getLogger(__name__)


def build_network_session() -> requests.Session | None:
    """Build a requests.Session that:
    - trusts enterprise MITM certs via truststore
    - uses enterprise proxy settings
    using sema4ai-http-helper, for all OTEL exporters.

    Returns:
        Configured requests.Session with enterprise settings, or None if unavailable
    """
    try:
        net = get_network_profile()  # SSL context + proxy config (http, https, no_proxy)
    except Exception as e:
        logger.warning(f"Failed to get network profile: {e}")
        return None

    # Build an adapter that injects the SSL context into urllib3 pool managers.
    class _SSLContextAdapter(HTTPAdapter):
        def __init__(self, ssl_context, *args, **kwargs):
            self._ssl_context = ssl_context
            super().__init__(*args, **kwargs)

        def init_poolmanager(self, *args, **kwargs):
            # Force our ssl_context into the PoolManager constructor
            kwargs["ssl_context"] = self._ssl_context
            return super().init_poolmanager(*args, **kwargs)

        def proxy_manager_for(self, proxy, **kwargs):
            kwargs["ssl_context"] = self._ssl_context
            return super().proxy_manager_for(proxy, **kwargs)

    s = requests.Session()
    if net.ssl_context:
        adapter = _SSLContextAdapter(net.ssl_context)
        s.mount("https://", adapter)
        s.mount("http://", adapter)

    # Apply proxies if present in the profile (pick the first defined because
    # requests doesn't support providing multiple and choosing one).
    if net.proxy_config.http:
        prev = s.proxies.get("http")
        new = net.proxy_config.http[0]
        s.proxies["http"] = new
        logger.debug(f"Overriding OTEL exporter http proxy from {prev} to {new}")

    if net.proxy_config.https:
        prev = s.proxies.get("https")
        new = net.proxy_config.https[0]
        s.proxies["https"] = new
        logger.debug(f"Overriding OTEL exporter https proxy from {prev} to {new}")

    return s
