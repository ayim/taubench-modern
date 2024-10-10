from base64 import b64encode
from datetime import datetime, timedelta, timezone
from typing import Optional
from unittest.mock import MagicMock, patch

import jwt

from sema4ai_agent_server.auth.handlers import AuthedUser, get_auth_handler
from sema4ai_agent_server.auth.settings import (
    AuthType,
    JWTSettingsLocal,
    JWTSettingsOIDC,
)
from sema4ai_agent_server.auth.settings import (
    settings as auth_settings,
)
from sema4ai_agent_server.responses import PydanticResponse
from sema4ai_agent_server.server import app
from tests.unit_tests.sema4ai_agent_server.helpers import get_client


@app.get("/me", response_model=AuthedUser, response_class=PydanticResponse)
async def me(user: AuthedUser):
    return user


def _create_jwt(
    key: str, alg: str, payload: dict, headers: Optional[dict] = None
) -> str:
    return jwt.encode(payload, key, algorithm=alg, headers=headers)


async def test_noop():
    get_auth_handler.cache_clear()
    auth_settings.auth_type = AuthType.NOOP
    sub = "user_noop"

    async with get_client() as client:
        response = await client.get("/me", cookies={"agent_server_user_id": sub})
        assert response.status_code == 200
        assert response.json()["sub"] == sub


async def test_jwt_local():
    get_auth_handler.cache_clear()
    auth_settings.auth_type = AuthType.JWT_LOCAL
    key = "key"
    auth_settings.jwt_local = JWTSettingsLocal(
        alg="HS256",
        iss="issuer",
        aud="audience",
        decode_key_b64=b64encode(key.encode("utf-8")),
    )
    sub = "user_jwt_local"

    token = _create_jwt(
        key=key,
        alg=auth_settings.jwt_local.alg,
        payload={
            "sub": sub,
            "iss": auth_settings.jwt_local.iss,
            "aud": auth_settings.jwt_local.aud,
            "exp": datetime.now(timezone.utc) + timedelta(days=1),
        },
    )

    async with get_client() as client:
        response = await client.get("/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        assert response.json()["sub"] == sub

    # Test invalid token
    async with get_client() as client:
        response = await client.get("/me", headers={"Authorization": "Bearer xyz"})
        assert response.status_code == 401


async def test_jwt_oidc():
    get_auth_handler.cache_clear()
    auth_settings.auth_type = AuthType.JWT_OIDC
    auth_settings.jwt_oidc = JWTSettingsOIDC(iss="issuer", aud="audience")
    sub = "user_jwt_oidc"
    key = "key"
    alg = "HS256"

    token = _create_jwt(
        key=key,
        alg=alg,
        payload={
            "sub": sub,
            "iss": auth_settings.jwt_oidc.iss,
            "aud": auth_settings.jwt_oidc.aud,
            "exp": datetime.now(timezone.utc) + timedelta(days=1),
        },
        headers={"kid": "kid", "alg": alg},
    )

    mock_jwk_client = MagicMock()
    mock_jwk_client.get_signing_key.return_value = MagicMock(key=key)

    with patch(
        "sema4ai_agent_server.auth.handlers.JWTAuthOIDC._get_jwk_client",
        return_value=mock_jwk_client,
    ):
        async with get_client() as client:
            response = await client.get(
                "/me", headers={"Authorization": f"Bearer {token}"}
            )
            assert response.status_code == 200
            assert response.json()["sub"] == sub
