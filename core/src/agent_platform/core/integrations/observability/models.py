import base64
from dataclasses import dataclass, field
from typing import Any, ClassVar, Literal, cast

import structlog
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

from agent_platform.core.errors import ErrorCode, PlatformHTTPError
from agent_platform.core.network.utils import build_network_session
from agent_platform.core.utils import SecretString

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


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
        metadata={
            "description": "Optional HTTP headers to send with the request to Grafana Cloud."
        },
    )
    DISALLOWED_HEADERS: ClassVar[set[str]] = {"Authorization", "Content-Type", "Host"}

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

        # Validate that disallowed headers are not present
        if additional_headers:
            for key in additional_headers:
                if key in cls.DISALLOWED_HEADERS:
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
        data: dict[str, Any] = {"url": self.url}
        data["api_token"] = _secret_or_redact(self.api_token, redact_secret)
        data["grafana_instance_id"] = self.grafana_instance_id
        if self.additional_headers:
            # Error out if any disallowed headers are present.
            data["additional_headers"] = {}
            for key, value in self.additional_headers.items():
                if key in self.DISALLOWED_HEADERS:
                    raise PlatformHTTPError(
                        error_code=ErrorCode.BAD_REQUEST,
                        message=f"{key} may not be specified as an HTTP header",
                    )
                data["additional_headers"][key] = _secret_or_redact(value, redact_secret)
        return data

    def make_exporter(self):
        """Create an OTLPSpanExporter for Grafana.

        Returns:
            Configured OTLPSpanExporter ready for use
        """
        # Normalize endpoint (ensure /v1/traces suffix)
        endpoint = self.url.rstrip("/")
        if not endpoint.endswith("/v1/traces"):
            endpoint = f"{endpoint}/v1/traces"

        # Authorization value should be "base64<grafana_instance_id:api_token>"
        api_key = (
            self.api_token.get_secret_value()
            if isinstance(self.api_token, SecretString)
            else self.api_token
        )
        basic_auth_value = base64.b64encode(
            f"{self.grafana_instance_id}:{api_key}".encode()
        ).decode()

        # Sent as HTTP Basic Auth
        headers = {"Authorization": f"Basic {basic_auth_value}"}

        if self.additional_headers:
            # We don't filter out disallowed headers here as if
            # they were present, model_dump would have raised an error.
            headers.update(self.additional_headers)

        # Build fresh session for this exporter
        # (each exporter needs its own to avoid header conflicts)
        session = build_network_session()

        exporter = OTLPSpanExporter(
            endpoint=endpoint,
            headers=headers,
            session=session,
        )
        return exporter


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

    def make_exporter(self):
        """Create an OTLPSpanExporter for LangSmith.

        Returns:
            Configured OTLPSpanExporter ready for use
        """

        # Normalize endpoint (ensure /otel/v1/traces suffix)
        endpoint = self.url.rstrip("/")
        if not endpoint.endswith("/otel/v1/traces"):
            endpoint = f"{endpoint}/otel/v1/traces"

        # Build LangSmith-specific headers
        headers = {
            "x-api-key": _to_plain_str(self.api_key),
            "Langsmith-Project": self.project_name,
        }

        # Build fresh session for this exporter
        # (each exporter needs its own to avoid header conflicts)
        session = build_network_session()

        return OTLPSpanExporter(
            endpoint=endpoint,
            headers=headers,
            session=session,
        )


ObservabilityProviderSettings = GrafanaObservabilitySettings | LangSmithObservabilitySettings

PROVIDER_SETTINGS: dict[str, type[ObservabilityProviderSettings]] = {
    "grafana": GrafanaObservabilitySettings,
    "langsmith": LangSmithObservabilitySettings,
}


@dataclass(frozen=True)
class ObservabilitySettings:
    """Settings payload for observability providers."""

    kind: Literal["grafana", "langsmith"]
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
            settings_value = provider_cls.model_validate(
                settings_value.model_dump(redact_secret=False)
            )
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

        literal_kind = cast(Literal["grafana", "langsmith"], kind)

        return cls(
            kind=literal_kind,
            provider_settings=provider_settings,
            is_enabled=bool(data.get("is_enabled", True)),
        )
