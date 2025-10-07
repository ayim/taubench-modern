"""Data server integration settings."""

from dataclasses import dataclass
from typing import Any

from agent_platform.core.integrations.settings.base import IntegrationSettings
from agent_platform.core.utils import SecretString


@dataclass(frozen=True)
class DataServerEndpoint:
    """Data server endpoint configuration."""

    host: str
    port: int
    kind: str  # "http" or "mysql"


@dataclass(frozen=True)
class DataServerSettings(IntegrationSettings):
    """Settings for data server integration."""

    username: str
    password: str | SecretString
    endpoints: list[DataServerEndpoint]

    def model_dump(self) -> dict[str, Any]:
        """Convert settings to dictionary."""
        return {
            "username": self.username,
            "password": self.password,
            "endpoints": [
                {
                    "host": endpoint.host,
                    "port": endpoint.port,
                    "kind": endpoint.kind,
                }
                for endpoint in self.endpoints
            ],
        }

    @classmethod
    def model_validate(cls, data: dict[str, Any]) -> "DataServerSettings":
        """Create settings from dictionary."""
        endpoints = [
            DataServerEndpoint(
                host=ep["host"],
                port=ep["port"],
                kind=ep["kind"],
            )
            for ep in data.get("endpoints", [])
        ]

        return cls(
            username=data["username"],
            password=data["password"],
            endpoints=endpoints,
        )
