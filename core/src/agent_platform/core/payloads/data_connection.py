from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Annotated, Any, Literal


class Sslmode(Enum):
    require = "require"
    disable = "disable"
    allow = "allow"
    prefer = "prefer"


class DataConnectionTag(str, Enum):
    """Tags that can be applied to data connections."""

    DOCUMENT_INTELLIGENCE = "data_intelligence"


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


@dataclass
class BaseDataConnection:
    """Base class for all data connections."""

    name: str
    description: str
    configuration: DataConnectionConfiguration
    created_at: datetime | None = None
    updated_at: datetime | None = None
    id: str | None = None
    external_id: str | None = None
    tags: list[str] = field(default_factory=list)


@dataclass
class PostgresDataConnection(BaseDataConnection):
    engine: Literal["postgres"] = "postgres"
    configuration: PostgresDataConnectionConfiguration


@dataclass
class RedshiftDataConnection(BaseDataConnection):
    engine: Literal["redshift"] = "redshift"
    configuration: RedshiftDataConnectionConfiguration


@dataclass
class SnowflakeDataConnection(BaseDataConnection):
    engine: Literal["snowflake"] = "snowflake"
    configuration: (
        SnowflakeLinkedConfiguration
        | SnowflakeCustomKeyPairConfiguration
        | SnowflakeDataConnectionConfiguration
    )


@dataclass
class ConfluenceDataConnection(BaseDataConnection):
    engine: Literal["confluence"] = "confluence"
    configuration: ConfluenceDataConnectionConfiguration


@dataclass
class MySQLDataConnection(BaseDataConnection):
    engine: Literal["mysql"] = "mysql"
    configuration: MySQLDataConnectionConfiguration


@dataclass
class MSSQLDataConnection(BaseDataConnection):
    engine: Literal["mssql"] = "mssql"
    configuration: MSSQLDataConnectionConfiguration


@dataclass
class OracleDataConnection(BaseDataConnection):
    engine: Literal["oracle"] = "oracle"
    configuration: OracleDataConnectionConfiguration


@dataclass
class SlackDataConnection(BaseDataConnection):
    engine: Literal["slack"] = "slack"
    configuration: SlackDataConnectionConfiguration


@dataclass
class SalesforceDataConnection(BaseDataConnection):
    engine: Literal["salesforce"] = "salesforce"
    configuration: SalesforceDataConnectionConfiguration


@dataclass
class TimescaleDBDataConnection(BaseDataConnection):
    engine: Literal["timescaledb"] = "timescaledb"
    configuration: TimescaledbDataConnectionConfiguration


@dataclass
class PgvectorDataConnection(BaseDataConnection):
    engine: Literal["pgvector"] = "pgvector"
    configuration: PgvectorDataConnectionConfiguration


@dataclass
class BigqueryDataConnection(BaseDataConnection):
    engine: Literal["bigquery"] = "bigquery"
    configuration: BigqueryDataConnectionConfiguration


@dataclass
class SemaknowledgebaseDataConnection(BaseDataConnection):
    engine: Literal["sema4_knowledge_base"] = "sema4_knowledge_base"
    configuration: SemaknowledgebaseDataConnectionConfiguration


@dataclass
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


# Data connection inspection models
@dataclass
class TableToInspect:
    name: str
    database: str | None
    schema: str | None
    # If the columns are passed, inspect only those columns, if not passed, inspect all columns
    columns_to_inspect: list[str] | None = None


@dataclass
class DataConnectionsInspectRequest:
    # If the tables are passed, inspect only those tables, if not passed, inspect all tables
    tables_to_inspect: list[TableToInspect] | None = None
    inspect_columns: Annotated[bool, "If True, inspect the columns of the tables"] = True
    n_sample_rows: Annotated[int, "The number of rows to sample from the tables"] = 10


@dataclass
class ColumnInfo:
    name: str
    data_type: str
    sample_values: list[Any] | None
    primary_key: bool | None
    unique: bool | None
    description: str | None
    synonyms: list[str] | None


@dataclass
class TableInfo:
    name: str
    database: str | None
    schema: str | None
    description: str | None
    columns: list[ColumnInfo]


@dataclass
class DataConnectionsInspectResponse:
    tables: list[TableInfo]
