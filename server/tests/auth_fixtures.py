from unittest.mock import patch

import pytest
import requests


@pytest.fixture(autouse=True, scope="session")
def _inject_test_auth_headers_into_requests():
    from server.tests.auth_helpers import TEST_AUTH_HEADERS

    original_request = requests.Session.request

    def patched_request(self, method, url, **kwargs):
        if "Authorization" not in self.headers:
            headers = kwargs.get("headers") or {}
            if "Authorization" not in headers:
                merged = {**TEST_AUTH_HEADERS, **headers}
                kwargs["headers"] = merged
        return original_request(self, method, url, **kwargs)

    with patch.object(requests.Session, "request", patched_request):
        yield
