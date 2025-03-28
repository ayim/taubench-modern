import os
from base64 import b64decode
from dataclasses import dataclass
from enum import Enum

from agent_platform.server.env_vars import AUTH_TYPE


class AuthType(Enum):
    NOOP = "noop"
    JWT_LOCAL = "jwt_local"
    JWT_OIDC = "jwt_oidc"


@dataclass
class JWTSettingsBase:
    iss: str
    aud: str | list[str]

    def __post_init__(self):
        # Handle comma-separated audience strings
        if isinstance(self.aud, str) and "," in self.aud:
            self.aud = self.aud.split(",")

    @classmethod
    def from_env(cls, prefix="JWT_"):
        """Load settings from environment variables with given prefix"""
        env_vars = {k: v for k, v in os.environ.items() if k.startswith(prefix)}
        kwargs = {}

        for field_name in cls.__annotations__.keys():
            env_name = f"{prefix}{field_name.upper()}"
            if env_name in env_vars:
                kwargs[field_name] = env_vars[env_name]

        return cls(**kwargs)


@dataclass
class JWTSettingsLocal(JWTSettingsBase):
    decode_key_b64: str
    alg: str
    decode_key: str | None = None

    def __post_init__(self):
        super().__post_init__()
        """
        Key may be a multiline string (e.g. in the case of a public key), so to
        be able to set it from env, we set it as a base64 encoded string and
        decode it here.
        """
        if self.decode_key is None:
            self.decode_key = b64decode(self.decode_key_b64).decode("utf-8")


@dataclass
class JWTSettingsOIDC(JWTSettingsBase):
    pass


@dataclass
class Settings:
    auth_type: AuthType
    jwt_local: JWTSettingsLocal | None = None
    jwt_oidc: JWTSettingsOIDC | None = None

    def __post_init__(self):
        if self.auth_type == AuthType.JWT_LOCAL and self.jwt_local is None:
            raise ValueError(
                "jwt local settings must be set when auth type is jwt_local.",
            )
        if self.auth_type == AuthType.JWT_OIDC and self.jwt_oidc is None:
            raise ValueError(
                "jwt oidc settings must be set when auth type is jwt_oidc.",
            )


def get_env_var(name, default=None):
    """Helper to get environment variables with defaults"""
    return os.environ.get(name, default)


# Create settings based on auth type
auth_type = AuthType((AUTH_TYPE or AuthType.NOOP.value).lower())
kwargs = {"auth_type": auth_type}

if auth_type == AuthType.JWT_LOCAL:
    kwargs["jwt_local"] = JWTSettingsLocal.from_env()
elif auth_type == AuthType.JWT_OIDC:
    kwargs["jwt_oidc"] = JWTSettingsOIDC.from_env()

settings = Settings(**kwargs)
