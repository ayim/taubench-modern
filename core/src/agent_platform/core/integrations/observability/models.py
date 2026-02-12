from abc import ABC
from dataclasses import dataclass, field
from typing import Any, ClassVar, Literal, cast

import structlog

from agent_platform.core.errors import ErrorCode, PlatformHTTPError
from agent_platform.core.utils import SecretString

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class GenericOtlpObservabilitySettings(ABC):
    """Base class for generic OTLP observability providers with trace URL support.

    Subclasses must define `url` and `trace_ui_type` attributes (typically via dataclass fields).
    This base class provides the common `get_trace_url` implementation.
    """

    url: str
    trace_ui_type: Literal["grafana", "jaeger", "unknown"]

    def get_trace_url(self, trace_id: str) -> str | None:
        """Generate a trace URL for viewing a trace in the configured UI.

        Args:
            trace_id: The OTEL trace ID (32-character hex string).

        Returns:
            The URL to view the trace, or None if trace_ui_type is 'unknown'.
        """
        if self.trace_ui_type == "unknown":
            return None

        import json
        import urllib.parse

        # Extract base URL (scheme + host + port) from the OTLP endpoint URL
        parsed = urllib.parse.urlparse(self.url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"

        if self.trace_ui_type == "jaeger":
            return f"{base_url}/trace/{trace_id}"
        elif self.trace_ui_type == "grafana":
            left = json.dumps({"queries": [{"refId": "A", "query": trace_id}]})
            return f"{base_url}/explore?orgId=1&left={urllib.parse.quote(left)}"

        return None


def _to_plain_str(value: str | SecretString | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, SecretString):
        return value.get_secret_value()
    return value


def _secret_or_redact(value: str | SecretString | None, redact_secret: bool = True) -> str | None:
    """Gets the plain string value from a SecretString/str or redacts it if requested."""
    if value is None:
        return None

    if redact_secret:
        return "**********"

    return _to_plain_str(value)


@dataclass(frozen=True)
class GrafanaObservabilitySettings:
    """Grafana Cloud observability configuration."""

    # Minimum required fields to authenticate with Grafana Cloud
    url: str = field(metadata={"description": "Full OTLP traces endpoint"})
    api_token: str | SecretString = field(
        metadata={"description": "Grafana API token."},
    )
    grafana_instance_id: str = field(
        metadata={"description": "Grafana instance ID."},
    )
    additional_headers: dict[str, str] | None = field(
        default=None,
        metadata={"description": "Optional HTTP headers to send with the request to Grafana Cloud."},
    )
    DISALLOWED_HEADERS: ClassVar[set[str]] = {"authorization", "content-type", "host"}

    @classmethod
    def model_validate(cls, data: Any) -> "GrafanaObservabilitySettings":
        if not isinstance(data, dict):
            raise ValueError("Grafana settings payload must be an object.")
        if "url" not in data:
            raise ValueError("Grafana settings require 'url'.")
        if "api_token" not in data:
            raise ValueError("Grafana settings require 'api_token'.")
        if "grafana_instance_id" not in data:
            raise ValueError("Grafana settings require 'grafana_instance_id'.")
        additional_headers = data.get("additional_headers", None)
        if additional_headers is not None and not isinstance(additional_headers, dict):
            raise ValueError("Grafana settings 'additional_headers' must be an object.")

        # Validate that disallowed headers are not present (case-insensitive)
        if additional_headers:
            for key in additional_headers:
                if key.lower() in cls.DISALLOWED_HEADERS:
                    raise PlatformHTTPError(
                        error_code=ErrorCode.BAD_REQUEST,
                        message=f"{key} may not be specified as an HTTP header",
                    )

        return cls(
            url=str(data["url"]),
            api_token=str(data["api_token"]),
            grafana_instance_id=str(data["grafana_instance_id"]),
            additional_headers=additional_headers,
        )

    def model_dump(self, *, redact_secret: bool = True) -> dict[str, Any]:
        data: dict[str, Any] = {
            "url": self.url,
            "api_token": _secret_or_redact(self.api_token, redact_secret),
            "grafana_instance_id": self.grafana_instance_id,
        }
        if self.additional_headers:
            data["additional_headers"] = {
                key: _secret_or_redact(value, redact_secret) for key, value in self.additional_headers.items()
            }
        return data

    def get_trace_url(self, trace_id: str) -> str | None:
        """Generate a trace URL for viewing a trace. Not supported for Grafana Cloud."""
        return None


@dataclass(frozen=True)
class LangSmithObservabilitySettings:
    """LangSmith observability configuration."""

    url: str = field(metadata={"description": "LangSmith OTLP endpoint"})
    project_name: str = field(metadata={"description": "LangSmith project name."})
    api_key: str | SecretString = field(
        metadata={"description": "LangSmith API key."},
    )

    @classmethod
    def model_validate(cls, data: Any) -> "LangSmithObservabilitySettings":
        if not isinstance(data, dict):
            raise ValueError("LangSmith settings payload must be an object.")
        for required in ("url", "project_name", "api_key"):
            if required not in data:
                raise ValueError(f"LangSmith settings require '{required}'.")
        return cls(str(data["url"]), str(data["project_name"]), str(data["api_key"]))

    def model_dump(self, *, redact_secret: bool = True) -> dict[str, Any]:
        return {
            "url": self.url,
            "project_name": self.project_name,
            "api_key": _secret_or_redact(self.api_key, redact_secret),
        }

    def get_trace_url(self, trace_id: str) -> str | None:
        """Generate a trace URL for viewing a trace. Not supported for LangSmith."""
        return None


@dataclass(frozen=True)
class OtlpBasicAuthObservabilitySettings(GenericOtlpObservabilitySettings):
    """Generic OTLP observability with Basic Authentication."""

    url: str = field(metadata={"description": "OTLP endpoint URL"})
    username: str = field(metadata={"description": "Basic auth username"})
    password: str | SecretString = field(
        metadata={"description": "Basic auth password."},
    )
    trace_ui_type: Literal["grafana", "jaeger", "unknown"] = field(
        default="unknown",
        metadata={"description": "Type of trace UI to use for viewing traces."},
    )

    @classmethod
    def model_validate(cls, data: Any) -> "OtlpBasicAuthObservabilitySettings":
        if not isinstance(data, dict):
            raise ValueError("OTLP Basic Auth settings payload must be an object.")
        for required in ("url", "username", "password"):
            if required not in data:
                raise ValueError(f"OTLP Basic Auth settings require '{required}'.")

        trace_ui_type = data.get("trace_ui_type", "unknown")
        if trace_ui_type not in ("grafana", "jaeger", "unknown"):
            raise ValueError("trace_ui_type must be 'grafana', 'jaeger', or 'unknown'.")

        return cls(
            url=str(data["url"]),
            username=str(data["username"]),
            password=str(data["password"]),
            trace_ui_type=trace_ui_type,
        )

    def model_dump(self, *, redact_secret: bool = True) -> dict[str, Any]:
        return {
            "url": self.url,
            "username": self.username,
            "password": _secret_or_redact(self.password, redact_secret),
            "trace_ui_type": self.trace_ui_type,
        }


@dataclass(frozen=True)
class OtlpCustomHeadersObservabilitySettings(GenericOtlpObservabilitySettings):
    """Generic OTLP observability with custom headers."""

    url: str = field(metadata={"description": "OTLP endpoint URL"})
    headers: dict[str, str] = field(
        metadata={"description": "Custom HTTP headers to send with the request."},
    )
    trace_ui_type: Literal["grafana", "jaeger", "unknown"] = field(
        default="unknown",
        metadata={"description": "Type of trace UI to use for viewing traces."},
    )
    DISALLOWED_HEADERS: ClassVar[set[str]] = {"content-type", "host"}

    @classmethod
    def model_validate(cls, data: Any) -> "OtlpCustomHeadersObservabilitySettings":
        if not isinstance(data, dict):
            raise ValueError("OTLP Custom Headers settings payload must be an object.")
        if "url" not in data:
            raise ValueError("OTLP Custom Headers settings require 'url'.")
        if "headers" not in data:
            raise ValueError("OTLP Custom Headers settings require 'headers'.")

        headers = data.get("headers")
        if not isinstance(headers, dict):
            raise ValueError("OTLP Custom Headers settings 'headers' must be an object.")

        # Validate that disallowed headers are not present (case-insensitive)
        for key in headers:
            if key.lower() in cls.DISALLOWED_HEADERS:
                raise PlatformHTTPError(
                    error_code=ErrorCode.BAD_REQUEST,
                    message=f"{key} may not be specified as an HTTP header",
                )

        trace_ui_type = data.get("trace_ui_type", "unknown")
        if trace_ui_type not in ("grafana", "jaeger", "unknown"):
            raise ValueError("trace_ui_type must be 'grafana', 'jaeger', or 'unknown'.")

        return cls(
            url=str(data["url"]),
            headers=headers,
            trace_ui_type=trace_ui_type,
        )

    def model_dump(self, *, redact_secret: bool = True) -> dict[str, Any]:
        return {
            "url": self.url,
            "headers": {key: _secret_or_redact(value, redact_secret) for key, value in self.headers.items()},
            "trace_ui_type": self.trace_ui_type,
        }


ObservabilityProviderSettings = (
    GrafanaObservabilitySettings
    | LangSmithObservabilitySettings
    | OtlpBasicAuthObservabilitySettings
    | OtlpCustomHeadersObservabilitySettings
)

PROVIDER_SETTINGS: dict[str, type[ObservabilityProviderSettings]] = {
    "grafana": GrafanaObservabilitySettings,
    "langsmith": LangSmithObservabilitySettings,
    "otlp_basic_auth": OtlpBasicAuthObservabilitySettings,
    "otlp_custom_headers": OtlpCustomHeadersObservabilitySettings,
}


@dataclass(frozen=True)
class ObservabilitySettings:
    """Settings payload for observability providers."""

    kind: Literal["grafana", "langsmith", "otlp_basic_auth", "otlp_custom_headers"]
    provider_settings: ObservabilityProviderSettings
    is_enabled: bool = field(default=True)

    def __post_init__(self):
        normalized_kind = str(self.kind).lower()
        if normalized_kind not in PROVIDER_SETTINGS:
            raise ValueError(f"Unsupported observability provider '{self.kind}'.")
        object.__setattr__(self, "kind", normalized_kind)

        settings_value = self.provider_settings
        provider_cls = PROVIDER_SETTINGS[normalized_kind]
        # Request payloads arrive as plain dicts; coerce them into the provider dataclass.
        if isinstance(settings_value, dict):
            settings_value = provider_cls.model_validate(settings_value)
        # When the value is already a dataclass but not the expected one (e.g., Pydantic chose
        # the wrong union member or we reloaded from storage), re-validate to get the right type.
        elif not isinstance(settings_value, provider_cls):
            # Provider mismatch (e.g., union chose the wrong dataclass); re-coerce using the
            # provider-specific validator. Logging helps trace unexpected conversions.
            logger.debug(
                "Coercing observability settings from %s to %s for provider '%s'.",
                type(settings_value).__name__,
                provider_cls.__name__,
                normalized_kind,
            )
            settings_value = provider_cls.model_validate(settings_value.model_dump(redact_secret=False))
        object.__setattr__(self, "provider_settings", settings_value)

    def model_dump(self, *, redact_secret: bool = True) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "is_enabled": self.is_enabled,
            "provider_settings": self.provider_settings.model_dump(redact_secret=redact_secret),
        }

    @classmethod
    def model_validate(cls, data: Any) -> "ObservabilitySettings":
        if not isinstance(data, dict):
            raise ValueError("Observability settings payload must be an object.")
        if "kind" not in data:
            raise ValueError("Observability settings require 'kind'.")

        kind = str(data["kind"]).lower()
        provider_cls = PROVIDER_SETTINGS[kind]
        provider_settings_data = data.get("provider_settings", {})
        provider_settings = provider_cls.model_validate(provider_settings_data)

        literal_kind = cast(Literal["grafana", "langsmith", "otlp_basic_auth", "otlp_custom_headers"], kind)

        return cls(
            kind=literal_kind,
            provider_settings=provider_settings,
            is_enabled=bool(data.get("is_enabled", True)),
        )
