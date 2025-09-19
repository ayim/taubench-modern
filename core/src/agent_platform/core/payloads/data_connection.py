from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Literal


class Sslmode(Enum):
    require = "require"
    disable = "disable"
    allow = "allow"
    prefer = "prefer"


@dataclass
class PostgresDataConnectionConfiguration:
    host: str
    port: float
    database: str
    user: str
    password: str
    schema: str = "public"
    sslmode: Sslmode | None = None


@dataclass
class RedshiftDataConnectionConfiguration:
    host: str
    port: float
    database: str
    user: str
    password: str
    schema: str | None = None
    sslmode: Sslmode | None = None


@dataclass
class SnowflakeLinkedConfiguration:
    warehouse: str
    database: str
    schema: str
    credential_type: str = "linked"


@dataclass
class SnowflakeCustomKeyPairConfiguration:
    account: str
    user: str
    private_key_path: str
    warehouse: str
    database: str
    schema: str
    credential_type: str = "custom-key-pair"
    role: str | None = None
    private_key_passphrase: str | None = None


@dataclass
class SnowflakeDataConnectionConfiguration:
    credential_type: str
    account: str
    user: str
    password: str
    warehouse: str
    database: str
    schema: str
    role: str | None = None


@dataclass
class ConfluenceDataConnectionConfiguration:
    api_base: str
    username: str
    password: str


@dataclass
class MySQLDataConnectionConfiguration:
    host: str
    port: float
    database: str
    user: str
    password: str
    ssl: bool | None = None
    ssl_ca: str | None = None
    ssl_cert: str | None = None
    ssl_key: str | None = None


@dataclass
class MSSQLDataConnectionConfiguration:
    host: str
    database: str
    user: str
    password: str
    port: float | None = None
    server: str | None = None


@dataclass
class OracleDataConnectionConfiguration:
    host: str
    user: str
    password: str
    service_name: str
    port: float | None = None
    dsn: str | None = None
    sid: str | None = None
    disable_oob: bool | None = None
    auth_mode: str | None = None


@dataclass
class SlackDataConnectionConfiguration:
    token: str
    app_token: str


@dataclass
class SalesforceDataConnectionConfiguration:
    username: str
    password: str
    client_id: str
    client_secret: str


@dataclass
class TimescaledbDataConnectionConfiguration:
    host: str
    port: float
    database: str
    user: str
    password: str


OpenAIProvider = Literal["openai"]


@dataclass
class OpenAIEmbeddingModel:
    model_name: str
    api_key: str
    provider: OpenAIProvider = "openai"


AzureOpenAIProvider = Literal["azure_openai"]


@dataclass
class AzureOpenAIEmbeddingModel:
    model_name: str
    api_key: str
    base_url: str
    api_version: str
    provider: AzureOpenAIProvider = "azure_openai"


@dataclass
class OpenAIRerankingModel:
    model_name: str
    api_key: str
    provider: OpenAIProvider = "openai"


@dataclass
class AzureOpenAIRerankingModel:
    model_name: str
    api_key: str
    base_url: str
    api_version: str
    provider: AzureOpenAIProvider = "azure_openai"


@dataclass
class SemaknowledgebaseDataConnectionConfiguration:
    embedding_model: OpenAIEmbeddingModel | AzureOpenAIEmbeddingModel
    storage: str
    reranking_model: OpenAIRerankingModel | AzureOpenAIRerankingModel | None = None
    metadata_columns: list[str] | None = None
    content_columns: list[str] | None = None
    id_column: str | None = None


@dataclass
class PgvectorDataConnectionConfiguration:
    host: str
    port: float
    database: str
    user: str
    password: str
    schema: str = "public"
    sslmode: Sslmode | None = None


@dataclass
class BigqueryDataConnectionConfiguration:
    project_id: str
    dataset: str
    service_account_keys: str | None = None
    service_account_json: str | None = None


@dataclass
class SQLiteDataConnectionConfiguration:
    db_file: str


DataConnectionEngine = Literal[
    "postgres",
    "redshift",
    "snowflake",
    "confluence",
    "mysql",
    "mssql",
    "oracle",
    "slack",
    "salesforce",
    "timescaledb",
    "pgvector",
    "bigquery",
    "sema4_knowledge_base",
    "sqlite",
]

DataConnectionConfiguration = (
    PostgresDataConnectionConfiguration
    | RedshiftDataConnectionConfiguration
    | SnowflakeLinkedConfiguration
    | SnowflakeCustomKeyPairConfiguration
    | SnowflakeDataConnectionConfiguration
    | ConfluenceDataConnectionConfiguration
    | MySQLDataConnectionConfiguration
    | MSSQLDataConnectionConfiguration
    | OracleDataConnectionConfiguration
    | SlackDataConnectionConfiguration
    | SalesforceDataConnectionConfiguration
    | TimescaledbDataConnectionConfiguration
    | PgvectorDataConnectionConfiguration
    | BigqueryDataConnectionConfiguration
    | SemaknowledgebaseDataConnectionConfiguration
    | SQLiteDataConnectionConfiguration
)


@dataclass(frozen=True)
class BaseDataConnection:
    """Base class for all data connections."""

    name: str
    description: str
    configuration: DataConnectionConfiguration
    created_at: datetime
    updated_at: datetime
    id: str | None = None
    external_id: str | None = None


@dataclass(frozen=True)
class PostgresDataConnection(BaseDataConnection):
    engine: Literal["postgres"] = "postgres"
    configuration: PostgresDataConnectionConfiguration


@dataclass(frozen=True)
class RedshiftDataConnection(BaseDataConnection):
    engine: Literal["redshift"] = "redshift"
    configuration: RedshiftDataConnectionConfiguration


@dataclass(frozen=True)
class SnowflakeDataConnection(BaseDataConnection):
    engine: Literal["snowflake"] = "snowflake"
    configuration: (
        SnowflakeLinkedConfiguration
        | SnowflakeCustomKeyPairConfiguration
        | SnowflakeDataConnectionConfiguration
    )


@dataclass(frozen=True)
class ConfluenceDataConnection(BaseDataConnection):
    engine: Literal["confluence"] = "confluence"
    configuration: ConfluenceDataConnectionConfiguration


@dataclass(frozen=True)
class MySQLDataConnection(BaseDataConnection):
    engine: Literal["mysql"] = "mysql"
    configuration: MySQLDataConnectionConfiguration


@dataclass(frozen=True)
class MSSQLDataConnection(BaseDataConnection):
    engine: Literal["mssql"] = "mssql"
    configuration: MSSQLDataConnectionConfiguration


@dataclass(frozen=True)
class OracleDataConnection(BaseDataConnection):
    engine: Literal["oracle"] = "oracle"
    configuration: OracleDataConnectionConfiguration


@dataclass(frozen=True)
class SlackDataConnection(BaseDataConnection):
    engine: Literal["slack"] = "slack"
    configuration: SlackDataConnectionConfiguration


@dataclass(frozen=True)
class SalesforceDataConnection(BaseDataConnection):
    engine: Literal["salesforce"] = "salesforce"
    configuration: SalesforceDataConnectionConfiguration


@dataclass(frozen=True)
class TimescaleDBDataConnection(BaseDataConnection):
    engine: Literal["timescaledb"] = "timescaledb"
    configuration: TimescaledbDataConnectionConfiguration


@dataclass(frozen=True)
class PgvectorDataConnection(BaseDataConnection):
    engine: Literal["pgvector"] = "pgvector"
    configuration: PgvectorDataConnectionConfiguration


@dataclass(frozen=True)
class BigqueryDataConnection(BaseDataConnection):
    engine: Literal["bigquery"] = "bigquery"
    configuration: BigqueryDataConnectionConfiguration


@dataclass(frozen=True)
class SemaknowledgebaseDataConnection(BaseDataConnection):
    engine: Literal["sema4_knowledge_base"] = "sema4_knowledge_base"
    configuration: SemaknowledgebaseDataConnectionConfiguration


@dataclass(frozen=True)
class SQLiteDataConnection(BaseDataConnection):
    engine: Literal["sqlite"] = "sqlite"
    configuration: SQLiteDataConnectionConfiguration


# Union type for all data connection types
DataConnection = (
    PostgresDataConnection
    | RedshiftDataConnection
    | SnowflakeDataConnection
    | ConfluenceDataConnection
    | MySQLDataConnection
    | MSSQLDataConnection
    | OracleDataConnection
    | SlackDataConnection
    | SalesforceDataConnection
    | TimescaleDBDataConnection
    | PgvectorDataConnection
    | BigqueryDataConnection
    | SemaknowledgebaseDataConnection
    | SQLiteDataConnection
)
