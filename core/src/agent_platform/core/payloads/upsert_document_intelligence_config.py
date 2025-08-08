from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from agent_platform.core.document_intelligence.dataserver import (
    DIDSApiConnectionDetails,
    DIDSConnectionDetails,
    DIDSConnectionKind,
)
from agent_platform.core.document_intelligence.integrations import (
    DocumentIntelligenceIntegration,
    IntegrationKind,
)
from agent_platform.core.utils import SecretString


@dataclass(frozen=True)
class _HttpConfig:
    url: str
    port: int


@dataclass(frozen=True)
class _MysqlConfig:
    host: str
    port: int


@dataclass(frozen=True)
class _ApiConfig:
    http: _HttpConfig
    mysql: _MysqlConfig


@dataclass(frozen=True)
class _Credentials:
    username: str
    password: str | SecretString


@dataclass(frozen=True)
class _DataServerConfig:
    credentials: _Credentials
    api: _ApiConfig


@dataclass(frozen=True)
class _IntegrationInput:
    type: str | IntegrationKind
    endpoint: str
    api_key: str | SecretString


@dataclass(frozen=True)
class UpsertDocumentIntelligenceConfigPayload:
    """Payload for upserting Document Intelligence configuration.

    This payload groups the Data Server connection details and one or more
    integrations. It is treated with PUT semantics by the API layer: callers
    are expected to provide the full set of fields.
    """

    data_server: _DataServerConfig = field()
    integrations: list[_IntegrationInput] = field(default_factory=list)

    @classmethod
    def model_validate(cls, data: Any) -> UpsertDocumentIntelligenceConfigPayload:
        # Defensive copy
        if isinstance(data, dict):
            obj = dict(data)
        else:
            obj = dict(getattr(data, "__dict__", {}))

        # Normalize credentials
        creds_in = obj["data_server"]["credentials"]
        credentials = _Credentials(
            username=creds_in["username"],
            password=creds_in["password"],
        )

        # Normalize API configs
        http_in = obj["data_server"]["api"]["http"]
        mysql_in = obj["data_server"]["api"]["mysql"]
        api_cfg = _ApiConfig(
            http=_HttpConfig(url=http_in["url"], port=int(http_in["port"])),
            mysql=_MysqlConfig(host=mysql_in["host"], port=int(mysql_in["port"])),
        )

        data_server = _DataServerConfig(credentials=credentials, api=api_cfg)

        # Normalize integrations
        integrations_raw = obj.get("integrations", []) or []
        integrations: list[_IntegrationInput] = []
        for item in integrations_raw:
            integrations.append(
                _IntegrationInput(
                    type=item["type"],
                    endpoint=item["endpoint"],
                    api_key=item["api_key"],
                )
            )

        return cls(integrations=integrations, data_server=data_server)

    # Convenience helpers used by the API layer
    def to_dids_connection_details(self) -> DIDSConnectionDetails:
        # HTTP connection: accept hostname in url; scheme (if provided) is ignored
        http_host = self.data_server.api.http.url
        # If the client sends something like http://host or https://host/path, extract hostname
        try:
            parsed = urlparse(http_host)
            if parsed.scheme and parsed.hostname:
                http_host = parsed.hostname
            elif "://" not in http_host and "/" in http_host:
                # looks like host/path without scheme
                http_host = http_host.split("/", 1)[0]
        except Exception:
            pass

        http_conn = DIDSApiConnectionDetails(
            host=http_host,
            port=self.data_server.api.http.port,
            kind=DIDSConnectionKind.HTTP,
        )
        mysql_conn = DIDSApiConnectionDetails(
            host=self.data_server.api.mysql.host,
            port=self.data_server.api.mysql.port,
            kind=DIDSConnectionKind.MYSQL,
        )

        password_value = (
            self.data_server.credentials.password
            if isinstance(self.data_server.credentials.password, SecretString)
            else SecretString(self.data_server.credentials.password)
        )

        return DIDSConnectionDetails(
            username=self.data_server.credentials.username,
            password=password_value,
            connections=[http_conn, mysql_conn],
        )

    def to_integrations(self) -> list[DocumentIntelligenceIntegration]:
        results: list[DocumentIntelligenceIntegration] = []
        for item in self.integrations:
            kind = (
                item.type if isinstance(item.type, IntegrationKind) else IntegrationKind(item.type)
            )
            api_key_value = (
                item.api_key
                if isinstance(item.api_key, SecretString)
                else SecretString(item.api_key)
            )
            results.append(
                DocumentIntelligenceIntegration(
                    kind=kind,
                    endpoint=item.endpoint,
                    api_key=api_key_value,
                )
            )
        return results
