from dataclasses import dataclass, field
from typing import Any, Literal, cast

import structlog
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

from agent_platform.core.utils import SecretString

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def _to_plain_str(value: str | SecretString | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, SecretString):
        return value.get_secret_value()
    return value


@dataclass(frozen=True)
class GrafanaObservabilitySettings:
    """Grafana observability configuration."""

    url: str = field(metadata={"description": "Full OTLP traces endpoint"})
    api_key: str | SecretString | None = field(
        default=None,
        metadata={"description": "Grafana API key or token."},
    )
    custom_attributes: dict[str, str] = field(
        default_factory=dict,
        metadata={"description": "Optional custom attributes appended to telemetry payloads."},
    )

    @classmethod
    def model_validate(cls, data: Any) -> "GrafanaObservabilitySettings":
        if not isinstance(data, dict):
            raise ValueError("Grafana settings payload must be an object.")
        if "url" not in data:
            raise ValueError("Grafana settings require 'url'.")

        custom_attrs = data.get("custom_attributes", {})
        api_key = data.get("api_key")
        return cls(str(data["url"]), api_key, custom_attrs)

    def model_dump(self, *, redact_secret: bool = True) -> dict[str, Any]:
        data: dict[str, Any] = {"url": self.url}
        if self.api_key:
            data["api_key"] = "**********" if redact_secret else _to_plain_str(self.api_key)
        if self.custom_attributes:
            data["custom_attributes"] = self.custom_attributes
        return data

    def make_exporter(self, network_session) -> OTLPSpanExporter:
        """Create an OTLPSpanExporter for Grafana.

        Args:
            network_session: Requests session with enterprise SSL/proxy config

        Returns:
            Configured OTLPSpanExporter ready for use
        """
        # TODO: Implement Grafana exporter creation
        raise NotImplementedError("Grafana support not yet implemented")


@dataclass(frozen=True)
class LangSmithObservabilitySettings:
    """LangSmith observability configuration."""

    url: str = field(metadata={"description": "LangSmith OTLP endpoint"})
    project_name: str = field(metadata={"description": "LangSmith project name."})
    api_key: str | SecretString | None = field(
        default=None,
        metadata={"description": "LangSmith API key."},
    )

    @classmethod
    def model_validate(cls, data: Any) -> "LangSmithObservabilitySettings":
        if not isinstance(data, dict):
            raise ValueError("LangSmith settings payload must be an object.")
        for required in ("url", "project_name"):
            if required not in data:
                raise ValueError(f"LangSmith settings require '{required}'.")
        api_key = data.get("api_key")
        return cls(str(data["url"]), str(data["project_name"]), api_key)

    def model_dump(self, *, redact_secret: bool = True) -> dict[str, Any]:
        data: dict[str, Any] = {
            "url": self.url,
            "project_name": self.project_name,
        }
        if self.api_key:
            data["api_key"] = "**********" if redact_secret else _to_plain_str(self.api_key)
        return data

    def make_exporter(self, network_session) -> OTLPSpanExporter:
        """Create an OTLPSpanExporter for LangSmith.

        Args:
            network_session: Requests session with enterprise SSL/proxy config

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

        return OTLPSpanExporter(
            endpoint=endpoint,
            headers=headers,
            session=network_session,
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
