from urllib.parse import urljoin

from sema4ai_docint.agent_server_client.transport.base import TransportBase


def test_build_agent_server_url():
    assert "https://router.ten-1234/proxy/api/v2/" == TransportBase._build_agent_server_v2_url(
        "https://router.ten-1234/proxy"
    )
    assert "http://localhost:8000/api/v2/" == TransportBase._build_agent_server_v2_url(
        "http://localhost:8000"
    )
    assert "http://localhost:8000/api/v2/" == TransportBase._build_agent_server_v2_url(
        "http://localhost:8000/"
    )
    assert "/api/v2/" == TransportBase._build_agent_server_v2_url("")


def test_clean_path():
    assert "ok" == TransportBase._clean_path("/ok")
    assert "ok" == TransportBase._clean_path("ok")
    assert "ok/" == TransportBase._clean_path("ok/")

    # Additionally check the basic logic of how urljoin will work with the clean path
    api_url = TransportBase._build_agent_server_v2_url("http://localhost:8000")
    path = TransportBase._clean_path("/ok")
    url = urljoin(api_url, path)
    assert "http://localhost:8000/api/v2/ok" == TransportBase._clean_path(url)
