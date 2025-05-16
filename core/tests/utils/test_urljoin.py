import pytest

from agent_platform.core.utils.url import safe_urljoin


@pytest.mark.parametrize(
    ("base_url", "segments", "expected"),
    [
        (
            "http://example.com/api/resource",
            ["openapi.json"],
            "http://example.com/api/resource/openapi.json",
        ),
        (
            "http://example.com/api/resource/",
            ["openapi.json"],
            "http://example.com/api/resource/openapi.json",
        ),
        (
            "http://example.com/api/resource//",
            ["openapi.json"],
            "http://example.com/api/resource/openapi.json",
        ),
        (
            "http://example.com/api/resource",
            ["/openapi.json"],
            "http://example.com/api/resource/openapi.json",
        ),
        (
            "http://example.com/api",
            ["v1", "resource", "openapi.json"],
            "http://example.com/api/v1/resource/openapi.json",
        ),
        (
            "http://example.com/api",
            ["//v1/", "/resource/", "///openapi.json"],
            "http://example.com/api/v1/resource/openapi.json",
        ),
        (
            "http://example.com",
            ["v1", "openapi.json"],
            "http://example.com/v1/openapi.json",
        ),
        (
            "http://example.com/api/",
            ["", "openapi.json"],
            "http://example.com/api/openapi.json",
        ),
        (
            "http://example.com/api/resource/openapi.json",
            [],
            "http://example.com/api/resource/openapi.json",
        ),
    ],
)
def test_safe_urljoin(base_url, segments, expected):
    assert safe_urljoin(base_url, *segments) == expected
