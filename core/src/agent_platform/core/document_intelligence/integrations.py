from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Literal
from urllib.parse import urlparse

from agent_platform.core.utils import SecretString


class IntegrationKind(StrEnum):
    """Supported integration kinds for Document Intelligence Data Server"""

    REDUCTO = "reducto"


@dataclass(frozen=True)
class DocumentIntelligenceIntegration:
    """DocumentIntelligenceIntegration represents an integration configuration for the
    Document Intelligence API."""

    kind: IntegrationKind = field(
        metadata={
            "description": "The kind of integration (currently only 'reducto' is supported)",
        },
    )
    """The kind of integration (currently only 'reducto' is supported)"""

    endpoint: str = field(
        metadata={
            "description": "The endpoint URL for the integration service",
        },
    )
    """The endpoint URL for the integration service"""

    api_key: SecretString = field(
        metadata={
            "description": "The API key for authenticating with the integration service",
        },
    )
    """The API key for authenticating with the integration service"""

    updated_at: datetime = field(
        default_factory=lambda: datetime.now(),
        metadata={
            "description": "Timestamp when the integration was last updated",
        },
    )
    """Timestamp when the integration was last updated"""

    def __post_init__(self):
        # Validate endpoint URL
        try:
            parsed = urlparse(self.endpoint)
            if not all([parsed.scheme, parsed.netloc]):
                raise ValueError(
                    f"Invalid endpoint URL: '{self.endpoint}'. "
                    "URL must include both scheme (http/https) and network location (domain)."
                )
            if parsed.scheme not in ("http", "https"):
                raise ValueError(
                    f"Invalid endpoint URL scheme: '{parsed.scheme}'. "
                    "Only 'http' and 'https' schemes are supported."
                )
            # Ensure there's actually a hostname (not just port)
            if not parsed.hostname:
                raise ValueError(
                    f"Invalid endpoint URL: '{self.endpoint}'. "
                    "URL must include a valid hostname/domain."
                )
        except Exception as e:
            if isinstance(e, ValueError):
                raise
            raise ValueError(f"Invalid endpoint URL format: '{self.endpoint}'") from e

        # Convert string api_key to SecretString
        if isinstance(self.api_key, str):
            object.__setattr__(self, "api_key", SecretString(self.api_key))

    def model_dump(self, *, mode: Literal["python", "json"] = "python") -> dict:
        """Convert the DocumentIntelligenceIntegration to a dictionary

        Args:
            mode: Either 'python' for Python objects or 'json' for JSON-serializable values
        """
        return {
            "kind": self.kind.value if mode == "json" else self.kind,
            "endpoint": self.endpoint,
            "api_key": self.api_key if mode == "python" else self.api_key.get_secret_value(),
            "updated_at": self.updated_at if mode == "python" else self.updated_at.isoformat(),
        }

    @classmethod
    def model_validate(cls, data: dict) -> "DocumentIntelligenceIntegration":
        """Create a DocumentIntelligenceIntegration instance from a dictionary.

        Args:
            data: Dictionary containing kind, endpoint, api_key, and updated_at fields

        Returns:
            A DocumentIntelligenceIntegration instance
        """
        data = dict(data)  # Create a copy to avoid modifying the original

        # Handle SecretString conversion (api_key can be a string or already a SecretString)
        if "api_key" in data and isinstance(data["api_key"], str):
            data["api_key"] = SecretString(data["api_key"])

        return cls(**data)
