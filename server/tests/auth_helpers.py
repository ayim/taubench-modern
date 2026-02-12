import base64
import json

TEST_USER_SUB = "test-user"

_header = base64.urlsafe_b64encode(json.dumps({"alg": "none"}).encode()).rstrip(b"=").decode()
_payload = base64.urlsafe_b64encode(json.dumps({"sub": TEST_USER_SUB}).encode()).rstrip(b"=").decode()
TEST_TOKEN = f"{_header}.{_payload}."

TEST_AUTH_HEADERS = {"Authorization": f"Bearer {TEST_TOKEN}"}
