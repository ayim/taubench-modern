from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

from sema4ai_docint.models.constants import DATA_SOURCE_NAME

from agent_platform.core.data_server.data_connection import DataConnection
from agent_platform.core.data_server.data_server import (
    DataServerDetails,
    DataServerEndpoint,
    DataServerEndpointKind,
)
from agent_platform.core.data_server.data_sources import DataSources
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
class DataServerConfig:
    credentials: _Credentials
    api: _ApiConfig


@dataclass(frozen=True)
class IntegrationInput:
    type: str | IntegrationKind
    endpoint: str
    api_key: str | SecretString
    external_id: str | None = None


@dataclass(frozen=True)
class DocumentIntelligenceConfigPayload:
    """Payload for upserting Document Intelligence configuration.

    This payload groups the Data Server connection details and one or more
    integrations. It is treated with PUT semantics by the API layer: callers
    are expected to provide the full set of fields.
    """

    data_server: DataServerConfig = field()
    integrations: list[IntegrationInput] = field(default_factory=list)
    data_connections: list[DataConnection] = field(default_factory=list)

    @classmethod
    def model_validate(cls, data: Any) -> DocumentIntelligenceConfigPayload:
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

        data_server = DataServerConfig(credentials=credentials, api=api_cfg)

        # Normalize integrations
        integrations_raw = obj.get("integrations", []) or []
        integrations: list[IntegrationInput] = []
        for item in integrations_raw:
            integrations.append(
                IntegrationInput(
                    external_id=item.get("external_id", item.get("id", str(uuid4()))),
                    type=item["type"],
                    endpoint=item["endpoint"],
                    api_key=item["api_key"],
                )
            )

        data_connections_raw = obj.get("data_connections", []) or []
        data_connections: list[DataConnection] = []
        for item in data_connections_raw:
            external_id = item.get("external_id", item.get("id", str(uuid4())))
            data_connections.append(
                DataConnection(
                    external_id=external_id,
                    name=item["name"],
                    engine=item["engine"],
                    configuration=item["configuration"],
                )
            )

        return cls(
            integrations=integrations,
            data_server=data_server,
            data_connections=data_connections,
        )

    # Convenience helpers used by the API layer
    def to_data_sources(self) -> DataSources:
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

        http_conn = DataServerEndpoint(
            host=http_host,
            port=self.data_server.api.http.port,
            kind=DataServerEndpointKind.HTTP,
        )
        mysql_conn = DataServerEndpoint(
            host=self.data_server.api.mysql.host,
            port=self.data_server.api.mysql.port,
            kind=DataServerEndpointKind.MYSQL,
        )

        password_value = (
            self.data_server.credentials.password
            if isinstance(self.data_server.credentials.password, SecretString)
            else SecretString(self.data_server.credentials.password)
        )

        data_server = DataServerDetails(
            username=self.data_server.credentials.username,
            password=password_value,
            data_server_endpoints=[http_conn, mysql_conn],
        )
        data_sources = {DATA_SOURCE_NAME: self.data_connections[0]} if self.data_connections else {}

        return DataSources(
            data_server=data_server,
            data_sources=data_sources,
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
                    external_id=item.external_id or str(uuid4()),
                    kind=kind,
                    endpoint=item.endpoint,
                    api_key=api_key_value,
                )
            )
        return results

    @classmethod
    def from_storage(
        cls,
        data_server_details: DataServerDetails,
        integrations: list[DocumentIntelligenceIntegration],
        data_connections: list[DataConnection],
    ) -> DocumentIntelligenceConfigPayload:
        """Create DocumentIntelligenceConfigPayload from stored data.

        Args:
            data_server_details: The stored data server details
            integrations: The stored integrations
            data_connections: The stored data connections

        Returns:
            A DocumentIntelligenceConfigPayload instance
        """
        # Extract HTTP and MySQL endpoints
        http_endpoint = None
        mysql_endpoint = None

        for endpoint in data_server_details.data_server_endpoints:
            if endpoint.kind == DataServerEndpointKind.HTTP:
                http_endpoint = endpoint
            elif endpoint.kind == DataServerEndpointKind.MYSQL:
                mysql_endpoint = endpoint

        if http_endpoint is None or mysql_endpoint is None:
            raise ValueError("HTTP and MySQL endpoints not found")

        # Use the host directly from the endpoint
        http_host = http_endpoint.host

        # Validate required credentials
        if data_server_details.username is None:
            raise ValueError("Data server username is required")
        if data_server_details.password is None:
            raise ValueError("Data server password is required")

        # Create data server config
        data_server = DataServerConfig(
            credentials=_Credentials(
                username=data_server_details.username,
                password=data_server_details.password,
            ),
            api=_ApiConfig(
                http=_HttpConfig(url=http_host, port=http_endpoint.port),
                mysql=_MysqlConfig(host=mysql_endpoint.host, port=mysql_endpoint.port),
            ),
        )

        # Convert integrations to IntegrationInput
        integration_inputs = []
        for integration in integrations:
            integration_inputs.append(
                IntegrationInput(
                    external_id=integration.external_id,
                    type=integration.kind,
                    endpoint=integration.endpoint,
                    api_key=integration.api_key,
                )
            )

        return cls(
            data_server=data_server,
            integrations=integration_inputs,
            data_connections=data_connections,
        )
