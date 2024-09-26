import os
from base64 import b64decode
from enum import Enum
from typing import Optional, Self, Union

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AuthType(Enum):
    NOOP = "noop"
    JWT_LOCAL = "jwt_local"
    JWT_OIDC = "jwt_oidc"


class JWTSettingsBase(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="jwt_")

    iss: str
    aud: Union[str, list[str]]

    @field_validator("aud", mode="before")
    @classmethod
    def set_aud(cls, v: Union[str, list[str]]) -> Union[str, list[str]]:
        return v.split(",") if "," in v else v


class JWTSettingsLocal(JWTSettingsBase):
    decode_key_b64: str
    alg: str
    decode_key: str | None = None

    @model_validator(mode="after")
    def set_decode_key(self) -> Self:
        """
        Key may be a multiline string (e.g. in the case of a public key), so to
        be able to set it from env, we set it as a base64 encoded string and
        decode it here.
        """
        if self.decode_key is None:
            self.decode_key = b64decode(self.decode_key_b64).decode("utf-8")
        return self


class JWTSettingsOIDC(JWTSettingsBase): ...


class Settings(BaseSettings):
    auth_type: AuthType
    jwt_local: Optional[JWTSettingsLocal] = None
    jwt_oidc: Optional[JWTSettingsOIDC] = None

    @model_validator(mode="after")
    def check_jwt_settings(self) -> Self:
        if self.auth_type == AuthType.JWT_LOCAL and self.jwt_local is None:
            raise ValueError(
                "jwt local settings must be set when auth type is jwt_local."
            )
        if self.auth_type == AuthType.JWT_OIDC and self.jwt_oidc is None:
            raise ValueError(
                "jwt oidc settings must be set when auth type is jwt_oidc."
            )
        return self


auth_type = AuthType(os.getenv("AUTH_TYPE", AuthType.NOOP.value).lower())
kwargs = {"auth_type": auth_type}
if auth_type == AuthType.JWT_LOCAL:
    kwargs["jwt_local"] = JWTSettingsLocal()
elif auth_type == AuthType.JWT_OIDC:
    kwargs["jwt_oidc"] = JWTSettingsOIDC()
settings = Settings(**kwargs)
