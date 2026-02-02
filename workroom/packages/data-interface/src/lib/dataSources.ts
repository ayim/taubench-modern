import { z, registry } from 'zod';
import { commaSeparatedStringParsing } from './utils';

export type DataSourceEngineWithConnection =
  | 'postgres'
  | 'redshift'
  | 'snowflake'
  | 'confluence'
  | 'mysql'
  | 'mssql'
  | 'oracle'
  | 'slack'
  | 'salesforce'
  | 'timescaledb'
  | 'sema4_knowledge_base'
  | 'pgvector'
  | 'bigquery'
  | 'databricks';
export type DataSourceEngine =
  | DataSourceEngineWithConnection
  | 'files'
  | 'prediction:lightwood'
  | 'custom';

const NonEmptyString = z.string().min(1);

/**
 * This allows UIs to render bespoke components when a specific custom schema type is used
 */
export enum CustomSchemaType {
  Secret = 'secret',
  KeyValueRecord = 'key_value_record',
  StringTupleArray = 'string_tuple_array',
}

export const dataSourcesZodRegistry = registry<{ customSchemaType: CustomSchemaType }>();

/**
 * Client-side secrets (Control Room / Studio)
 * A string that should be treated as a secret value
 */
const Secret = z.string().nonempty();
dataSourcesZodRegistry.add(Secret, { customSchemaType: CustomSchemaType.Secret });

/**
 * A record of configuration parameters that can be strings, numbers, or booleans
 * Useful for flexible configuration objects where values can be mixed types
 */
const KeyValueRecord = z.record(z.string(), z.union([z.string(), z.number(), z.boolean()]));
type KeyValueRecord = z.infer<typeof KeyValueRecord>;

dataSourcesZodRegistry.add(KeyValueRecord, { customSchemaType: CustomSchemaType.KeyValueRecord });

/**
 * An array of string key-value pairs (tuples)
 * Useful for HTTP headers, query parameters, or other paired string data
 */
const StringTupleArray = z.array(z.tuple([z.string(), z.string()])).refine(
  (tuples) => {
    const keys = tuples.map(([key]) => key);
    const uniqueKeys = new Set(keys);
    return keys.length === uniqueKeys.size;
  },
  {
    message: 'Duplicate keys found in tuple array. Each key must be unique.',
  },
);
type StringTupleArray = z.infer<typeof StringTupleArray>;
dataSourcesZodRegistry.add(StringTupleArray, {
  customSchemaType: CustomSchemaType.StringTupleArray,
});

/**
 * ACE secret: the secret is a pointer to the OSB
 */
const ACEAWSSecretManagerSecret = z.object({
  type: z.literal('aws-secrets-manager'),
  details: z.object({
    roleARN: NonEmptyString,
    secretARN: NonEmptyString,
    secretKey: NonEmptyString.nullable(),
  }),
});

const ControlRoomAWSSecretManagerSecret = z.object({
  id: z.string(),
  location: z.object({
    type: z.literal('aws-secrets-manager'),
    details: z.object({
      roleARN: z.string(),
      secretARN: z.string(),
      secretKey: z.string().nullable(),
    }),
  }),
});

const getDataConnectionConfigurationSchemas = <SecretSchema extends z.ZodType>({
  secretSchema,
}: {
  secretSchema: SecretSchema;
}) => {
  // prettier-ignore
  return {
    postgres: z.object({
      host: NonEmptyString.describe('The hostname, IP address, or URL of the PostgreSQL server'),
      port: z.number().min(0).max(65535).describe('The port number for connecting to the PostgreSQL server'),
      database: NonEmptyString.describe('The name of the PostgreSQL database to connect to'),
      user: NonEmptyString.describe('The username for the PostgreSQL database'),
      password: secretSchema.describe('The password for the PostgreSQL database'),
      schema: NonEmptyString.default('public').describe('The database schema to use. Default is public'),
      sslmode: z.enum(['require', 'disable', 'allow', 'prefer']).optional().describe('The SSL mode for the connection'),
    }),
    redshift: z.object({
      host: NonEmptyString.describe('The host name or IP address of the Redshift cluster'),
      port: z.number().min(0).max(65535).describe(' The port to use when connecting with the Redshift cluster'),
      database: NonEmptyString.describe('The database name to use when connecting with the Redshift cluster'),
      user: NonEmptyString.describe('The username to authenticate the user with the Redshift cluster'),
      password: secretSchema.describe('The password to authenticate the user with the Redshift cluster'),
      schema: NonEmptyString.optional().describe('The database schema to use. Default is public'),
      sslmode: z.enum(['require', 'disable', 'allow', 'prefer']).optional().describe('The SSL mode for the connection'),
    }),
    snowflake: z.union([
      z.object({
        credential_type: z.literal('linked').describe('Use linked Snowflake account credentials.'),
        warehouse: NonEmptyString.describe('The Snowflake warehouse to use for running queries'),
        database: NonEmptyString.describe('The name of the Snowflake database to connect to'),
        schema: NonEmptyString.describe('The database schema to use within the Snowflake database. Default is PUBLIC'),
      }),
      z.object({
        credential_type: z.literal('custom-key-pair').describe('Use linked Snowflake account credentials.'),
        account: NonEmptyString.describe('The Snowflake account identifier.'),
        user: NonEmptyString.describe('The username for the Snowflake account'),
        role: NonEmptyString.optional().describe('The Snowflake role to use'),
        private_key_path: NonEmptyString.describe('Path to the private key file for the Snowflake account'),
        private_key_passphrase: secretSchema.optional().describe('The passphrase for the private key file for the Snowflake account'),
        warehouse: NonEmptyString.describe('The Snowflake warehouse to use for running queries'),
        database: NonEmptyString.describe('The name of the Snowflake database to connect to'),
        schema: NonEmptyString.describe('The database schema to use within the Snowflake database. Default is PUBLIC'),
      }),
      z.object({
        credential_type: z.literal("password").describe('Using the legacy username and password.'),
        account: NonEmptyString.describe('The Snowflake account identifier.'),
        user: NonEmptyString.describe('The username for the Snowflake account'),
        password: secretSchema.describe('The password for the Snowflake account'),
        role: NonEmptyString.optional().describe('The Snowflake role to use'),
        warehouse: NonEmptyString.describe('The Snowflake warehouse to use for running queries'),
        database: NonEmptyString.describe('The name of the Snowflake database to connect to'),
        schema: NonEmptyString.describe('The database schema to use within the Snowflake database. Default is PUBLIC'),
      }),
      z.object({
        credential_type: z.literal('programmatic-access-token').describe('Use a Snowflake programmatic access token (PAT).'),
        account: NonEmptyString.describe('The Snowflake account identifier.'),
        user: NonEmptyString.describe('The username for the Snowflake account'),
        password: secretSchema.describe('The programmatic access token for the Snowflake account'),
        role: NonEmptyString.optional().describe('The Snowflake role to use'),
        warehouse: NonEmptyString.describe('The Snowflake warehouse to use for running queries'),
        database: NonEmptyString.describe('The name of the Snowflake database to connect to'),
        schema: NonEmptyString.describe('The database schema to use within the Snowflake database. Default is PUBLIC'),
      }),
      // The configuration for credential_type: "undefined" is identical to the password one. 
      // Used for backward-compatibility: some data connection configurations were created without any credential_type set (the credential type was introduced later on)
      z.object({
        credential_type: z.literal(undefined).describe('Using the legacy username and password.'),
        account: NonEmptyString.describe('The Snowflake account identifier.'),
        user: NonEmptyString.describe('The username for the Snowflake account'),
        password: secretSchema.describe('The password for the Snowflake account'),
        role: NonEmptyString.optional().describe('The Snowflake role to use'),
        warehouse: NonEmptyString.describe('The Snowflake warehouse to use for running queries'),
        database: NonEmptyString.describe('The name of the Snowflake database to connect to'),
        schema: NonEmptyString.describe('The database schema to use within the Snowflake database. Default is PUBLIC'),
      }),
    ]),
    // https://github.com/mindsdb/mindsdb/blob/main/mindsdb/integrations/handlers/confluence_handler/connection_args.py
    confluence: z.object({
      api_base: NonEmptyString.describe('Confluence URL'),
      username: NonEmptyString.describe('Confluence username'),
      password: secretSchema.describe('Confluence API token used to authenticate.'),
    }),
    // https://github.com/mindsdb/mindsdb/blob/main/mindsdb/integrations/handlers/mysql_handler/connection_args.py
    mysql: z.object({
      host: NonEmptyString.describe('The host name or IP address of the MySQL server.'),
      port: z.number().min(0).max(65535).describe('The TCP/IP port of the MySQL server.'),
      database: NonEmptyString.describe('The database name to use when connecting with the MySQL server.'),
      user: NonEmptyString.describe('The user name used to authenticate with the MySQL server.'),
      password: secretSchema.describe('The password to authenticate the user with the MySQL server.'),
      ssl: z.boolean().optional().describe('Set it to True to enable ssl.'),
      ssl_ca: NonEmptyString.optional().describe('Path or URL of the Certificate Authority (CA) certificate file.'),
      ssl_cert: NonEmptyString.optional().describe('Path name or URL of the server public key certificate file.'),
      ssl_key: NonEmptyString.optional().describe('The path name or URL of the server private key file.'),
    }),
    // https://github.com/mindsdb/mindsdb/blob/main/mindsdb/integrations/handlers/mssql_handler/connection_args.py
    mssql: z.object({
      host: NonEmptyString.describe('The host name or IP address of the Microsoft SQL Server.'),
      port: z.number().min(0).max(65535).optional().describe('The TCP/IP port of the Microsoft SQL Server. Default is 1433'),
      database: NonEmptyString.describe('The database name to use when connecting with the Microsoft SQL Server.'),
      user: NonEmptyString.describe('The user name used to authenticate with the Microsoft SQL Server.'),
      password: secretSchema.describe('The password to authenticate the user with the Microsoft SQL Server.'),
      server: NonEmptyString.optional().describe('The server name of the Microsoft SQL Server. Typically only used with named instances or Azure SQL Database.'),
    }),
    // https://github.com/mindsdb/mindsdb/blob/main/mindsdb/integrations/handlers/oracle_handler/connection_args.py
    oracle: z.object({
      host: NonEmptyString.describe('The hostname, IP address, or URL of the Oracle server.'),
      port: z.number().min(0).max(65535).optional().describe('The port number for connecting to the Oracle database. Default is 1521'),
      user: NonEmptyString.describe('The username for the Oracle database'),
      password: secretSchema.describe('The password for the Oracle database'),
      service_name: NonEmptyString.describe('The service name of the Oracle database'),
      dsn: NonEmptyString.optional().describe('The data source name (DSN) for the Oracle database'),
      sid: NonEmptyString.optional().describe('The system identifier (SID) of the Oracle database'),
      disable_oob: z.boolean().optional().describe('The boolean parameter to disable out-of-band breaks. Default is false.'),
      auth_mode: NonEmptyString.optional().describe('The authorization mode to use'),
    }),
    // https://github.com/mindsdb/mindsdb/blob/main/mindsdb/integrations/handlers/slack_handler/connection_args.py
    slack: z.object({
      token: secretSchema.describe('The bot token for the Slack app.'),
      app_token: secretSchema.describe('The app token for the Slack app.'),
    }),
    // https://github.com/mindsdb/mindsdb/blob/main/mindsdb/integrations/handlers/salesforce_handler/connection_args.py
    salesforce: z.object({
      username: NonEmptyString.describe('The username for the Salesforce account'),
      password: secretSchema.describe('The password for the Salesforce account'),
      client_id: NonEmptyString.describe('The client ID (consumer key) from a connected app in Salesforce'),
      client_secret: secretSchema.describe('The client secret (consumer secret) from a connected app in Salesforce'),
    }),
    // https://docs.mindsdb.com/integrations/data-integrations/timescaledb#usage
    timescaledb: z.object({
      host: NonEmptyString.describe('The hostname, IP address, or URL of the TimescaleDB server'),
      port: z.number().min(0).max(65535).describe('The port number for connecting to the TimescaleDB server'),
      database: NonEmptyString.describe('The name of the TimescaleDB database to connect to'),
      user: NonEmptyString.describe('The username for the TimescaleDB database'),
      password: secretSchema.describe('The password for the TimescaleDB database'),
    }),
    sema4_knowledge_base: z.object({
      embedding_model: z.discriminatedUnion('provider', [
        z.object({
          provider: z.literal('openai'),
          model_name: z.string().describe('The name of the embedding model'),
          api_key: secretSchema.describe('The API key for the embedding model provider'),
        }),
        z.object({
          provider: z.literal('azure_openai'),
          model_name: z.string().describe('The name of the embedding model'),
          api_key: secretSchema.describe('The API key for the embedding model provider'),
          base_url: z.string().url().describe('The Azure OpenAI endpoint URL'),
          api_version: z.string().describe('The Azure OpenAI API version'),
        }),
      ]).describe('The embedding model to use for the Sema4 Knowledge Base'),
      reranking_model: z.discriminatedUnion('provider', [
        z.object({
          provider: z.literal('openai'),
          model_name: z.string().describe('The name of the reranking model'),
          api_key: secretSchema.describe('The API key for the reranking model provider'),
        }),
        z.object({
          provider: z.literal('azure_openai'),
          model_name: z.string().describe('The name of the reranking model'),
          api_key: secretSchema.describe('The API key for the reranking model provider'),
          base_url: z.string().url().describe('The Azure OpenAI endpoint URL'),
          api_version: z.string().describe('The Azure OpenAI API version'),
        }),
      ]).optional().describe('The reranking model to use for the Knowledge Base'),
      storage: z.string()
        .regex(/^[a-zA-Z_][a-zA-Z0-9_]*\.[a-zA-Z_][a-zA-Z0-9_]*$/, 'Storage must be in format datasource_name.table_name.')
        .describe('The PGVector storage table for the Knowledge Base content embeddings. Please provide table name like datasource_name.table_name.'),
      metadata_columns: z.union([z.string(), z.array(z.string())]).transform(commaSeparatedStringParsing).optional().describe('List of columns to be used as metadata. Comma-separated values: column_a,column_b'),
      content_columns: z.union([z.string(), z.array(z.string())]).transform(commaSeparatedStringParsing).optional().describe('List of columns to be used as content. Comma-separated values: column_a,column_b'),
      id_column: z.string().optional().describe('The column to be used as the unique identifier. If not provided, it is generated from the hash of the content columns.'),
    }),
    pgvector: z.object({
      host: NonEmptyString.describe('The hostname, IP address, or URL of the PostgreSQL server'),
      port: z.number().min(0).max(65535).describe('The port number for connecting to the PostgreSQL server'),
      database: NonEmptyString.describe('The name of the PostgreSQL database to connect to'),
      user: NonEmptyString.describe('The username for the PostgreSQL database'),
      password: secretSchema.describe('The password for the PostgreSQL database'),
      schema: NonEmptyString.default('public').describe('The database schema to use. Default is public'),
      sslmode: z.enum(['require', 'disable', 'allow', 'prefer']).optional().describe('The SSL mode for the connection'),
    }),
    // https://github.com/mindsdb/mindsdb/blob/main/mindsdb/integrations/handlers/bigquery_handler/connection_args.py
    bigquery: z.object({
      project_id: NonEmptyString.describe('The BigQuery project id.'),
      dataset: NonEmptyString.describe('The BigQuery dataset name.'),
      service_account_keys: secretSchema.optional().describe('Full path or URL to the service account JSON file.'),
      service_account_json: secretSchema.optional().describe('Content of service account JSON file.'),
    }),
    databricks: z.object({
      server_hostname: NonEmptyString.describe('The server hostname of the cluster or SQL warehouse'),
      http_path: NonEmptyString.describe('The http path to the cluster or SQL warehouse'),
      access_token: secretSchema.describe('The personal Databricks access token'),
      schema: NonEmptyString.optional().describe('The schema name (defaults to `default` if left blank)'),
      catalog: NonEmptyString.optional().describe('The catalog (defaults to `hive_metastore` if left blank)'),
      session_configuration: KeyValueRecord.optional().describe('The dictionary of Spark session configuration parameters. {"spark.sql.variable.substitute": True, "statement_timeout": 10}'),
      http_headers: StringTupleArray.optional().describe('The additional (key, value) pairs to set in HTTP headers on every RPC request the client makes. [["X-Databricks-Feature", "experimental-client"], ["X-Request-Source", "python-sql-connector"]]'),
      
    }),
  } satisfies Record<DataSourceEngineWithConnection, unknown>;
};

export const getDataConnectionEngineConfigurationSchemas = <SecretSchema extends z.ZodType>({
  secretSchema,
}: {
  secretSchema: SecretSchema;
}) => {
  const configurationSchema = getDataConnectionConfigurationSchemas({ secretSchema });
  return z.discriminatedUnion('engine', [
    z.object({
      engine: z.literal('postgres'),
      configuration: configurationSchema.postgres,
    }),
    z.object({
      engine: z.literal('redshift'),
      configuration: configurationSchema.redshift,
    }),
    z.object({
      engine: z.literal('snowflake'),
      configuration: configurationSchema.snowflake,
    }),
    z.object({
      engine: z.literal('confluence'),
      configuration: configurationSchema.confluence,
    }),
    z.object({
      engine: z.literal('mysql'),
      configuration: configurationSchema.mysql,
    }),
    z.object({
      engine: z.literal('mssql'),
      configuration: configurationSchema.mssql,
    }),
    z.object({
      engine: z.literal('oracle'),
      configuration: configurationSchema.oracle,
    }),
    z.object({
      engine: z.literal('slack'),
      configuration: configurationSchema.slack,
    }),
    z.object({
      engine: z.literal('salesforce'),
      configuration: configurationSchema.salesforce,
    }),
    z.object({
      engine: z.literal('timescaledb'),
      configuration: configurationSchema.timescaledb,
    }),
    z.object({
      engine: z.literal('sema4_knowledge_base'),
      configuration: configurationSchema.sema4_knowledge_base,
    }),
    z.object({
      engine: z.literal('pgvector'),
      configuration: configurationSchema.pgvector,
    }),
    z.object({
      engine: z.literal('bigquery'),
      configuration: configurationSchema.bigquery,
    }),
    z.object({
      engine: z.literal('databricks'),
      configuration: configurationSchema.databricks,
    }),
  ]);
};

// Used to display Datasources
export type DataSource = z.infer<typeof DataSource>;
export const DataSource = z.object({
  customerFacingName: NonEmptyString,
  engine: z.union([
    z.literal('postgres'),
    z.literal('redshift'),
    z.literal('snowflake'),
    z.literal('files'),
    z.literal('prediction:lightwood'),
    z.literal('custom'),
    z.literal('confluence'),
    z.literal('mysql'),
    z.literal('mssql'),
    z.literal('oracle'),
    z.literal('slack'),
    z.literal('salesforce'),
    z.literal('timescaledb'),
    z.literal('sema4_knowledge_base'),
    z.literal('pgvector'),
    z.literal('bigquery'),
    z.literal('databricks'),
  ]),
  description: z.string(),
});

export type DataSourceSpec = z.infer<typeof DataSourceSpec>;
export const DataSourceSpec = z.discriminatedUnion('engine', [
  z.object({
    engine: z.literal('postgres'),
    name: NonEmptyString,
    description: NonEmptyString,
  }),
  z.object({
    engine: z.literal('redshift'),
    name: NonEmptyString,
    description: NonEmptyString,
  }),
  z.object({
    engine: z.literal('snowflake'),
    name: NonEmptyString,
    description: NonEmptyString,
  }),
  z.object({
    engine: z.literal('confluence'),
    name: NonEmptyString,
    description: NonEmptyString,
  }),
  z.object({
    engine: z.literal('mysql'),
    name: NonEmptyString,
    description: NonEmptyString,
  }),
  z.object({
    engine: z.literal('mssql'),
    name: NonEmptyString,
    description: NonEmptyString,
  }),
  z.object({
    engine: z.literal('oracle'),
    name: NonEmptyString,
    description: NonEmptyString,
  }),
  z.object({
    engine: z.literal('slack'),
    name: NonEmptyString,
    description: NonEmptyString,
  }),
  z.object({
    engine: z.literal('salesforce'),
    name: NonEmptyString,
    description: NonEmptyString,
  }),
  z.object({
    engine: z.literal('timescaledb'),
    name: NonEmptyString,
    description: NonEmptyString,
  }),
  z.object({
    engine: z.literal('files'),
    description: NonEmptyString,
    file: NonEmptyString,
    createdTable: NonEmptyString,
  }),
  z.object({
    engine: z.literal('prediction:lightwood'),
    modelName: NonEmptyString,
    description: NonEmptyString,
    setupSQL: z.array(z.string()),
  }),
  z.object({
    engine: z.literal('sema4_knowledge_base'),
    name: NonEmptyString,
    description: NonEmptyString,
  }),
  z.object({
    engine: z.literal('pgvector'),
    name: NonEmptyString,
    description: NonEmptyString,
  }),
  z.object({
    engine: z.literal('bigquery'),
    name: NonEmptyString,
    description: NonEmptyString,
  }),
  z.object({
    engine: z.literal('databricks'),
    name: NonEmptyString,
    description: NonEmptyString,
  }),
]);

export const dataSourceConnectionConfigurationSchemaByEngine =
  getDataConnectionConfigurationSchemas({ secretSchema: Secret });

export const aceDataSourceConnectionConfigurationSchemaByEngine =
  getDataConnectionConfigurationSchemas({ secretSchema: ACEAWSSecretManagerSecret });

export type DataConnection = z.infer<typeof DataConnection>;
export const DataConnection = z.discriminatedUnion('engine', [
  z.object({
    name: NonEmptyString,
    description: NonEmptyString,
    engine: z.literal('postgres'),
    configuration: dataSourceConnectionConfigurationSchemaByEngine.postgres,
  }),
  z.object({
    name: NonEmptyString,
    description: NonEmptyString,
    engine: z.literal('redshift'),
    configuration: dataSourceConnectionConfigurationSchemaByEngine.redshift,
  }),
  z.object({
    name: NonEmptyString,
    description: NonEmptyString,
    engine: z.literal('snowflake'),
    configuration: dataSourceConnectionConfigurationSchemaByEngine.snowflake,
  }),
  z.object({
    name: NonEmptyString,
    description: NonEmptyString,
    engine: z.literal('confluence'),
    configuration: dataSourceConnectionConfigurationSchemaByEngine.confluence,
  }),
  z.object({
    name: NonEmptyString,
    description: NonEmptyString,
    engine: z.literal('mysql'),
    configuration: dataSourceConnectionConfigurationSchemaByEngine.mysql,
  }),
  z.object({
    name: NonEmptyString,
    description: NonEmptyString,
    engine: z.literal('mssql'),
    configuration: dataSourceConnectionConfigurationSchemaByEngine.mssql,
  }),
  z.object({
    name: NonEmptyString,
    description: NonEmptyString,
    engine: z.literal('oracle'),
    configuration: dataSourceConnectionConfigurationSchemaByEngine.oracle,
  }),
  z.object({
    name: NonEmptyString,
    description: NonEmptyString,
    engine: z.literal('slack'),
    configuration: dataSourceConnectionConfigurationSchemaByEngine.slack,
  }),
  z.object({
    name: NonEmptyString,
    description: NonEmptyString,
    engine: z.literal('salesforce'),
    configuration: dataSourceConnectionConfigurationSchemaByEngine.salesforce,
  }),
  z.object({
    name: NonEmptyString,
    description: NonEmptyString,
    engine: z.literal('timescaledb'),
    configuration: dataSourceConnectionConfigurationSchemaByEngine.timescaledb,
  }),
  z.object({
    name: NonEmptyString,
    description: NonEmptyString,
    engine: z.literal('sema4_knowledge_base'),
    configuration: dataSourceConnectionConfigurationSchemaByEngine.sema4_knowledge_base,
  }),
  z.object({
    name: NonEmptyString,
    description: NonEmptyString,
    engine: z.literal('pgvector'),
    configuration: dataSourceConnectionConfigurationSchemaByEngine.pgvector,
  }),
  z.object({
    engine: z.literal('bigquery'),
    name: NonEmptyString,
    description: NonEmptyString,
    configuration: dataSourceConnectionConfigurationSchemaByEngine.bigquery,
  }),
  z.object({
    engine: z.literal('databricks'),
    name: NonEmptyString,
    description: NonEmptyString,
    configuration: dataSourceConnectionConfigurationSchemaByEngine.databricks,
  }),
]);

export type ACEDataSourceWithConnectionConfiguration = z.infer<
  typeof ACEDataSourceWithConnectionConfiguration
>;
export const ACEDataSourceWithConnectionConfiguration = z.discriminatedUnion('engine', [
  z.object({
    engine: z.literal('postgres'),
    name: NonEmptyString,
    configuration: aceDataSourceConnectionConfigurationSchemaByEngine.postgres,
  }),
  z.object({
    engine: z.literal('redshift'),
    name: NonEmptyString,
    configuration: aceDataSourceConnectionConfigurationSchemaByEngine.redshift,
  }),
  z.object({
    engine: z.literal('snowflake'),
    name: NonEmptyString,
    configuration: aceDataSourceConnectionConfigurationSchemaByEngine.snowflake,
  }),
  z.object({
    engine: z.literal('confluence'),
    name: NonEmptyString,
    configuration: aceDataSourceConnectionConfigurationSchemaByEngine.confluence,
  }),
  z.object({
    engine: z.literal('mysql'),
    name: NonEmptyString,
    configuration: aceDataSourceConnectionConfigurationSchemaByEngine.mysql,
  }),
  z.object({
    engine: z.literal('mssql'),
    name: NonEmptyString,
    configuration: aceDataSourceConnectionConfigurationSchemaByEngine.mssql,
  }),
  z.object({
    engine: z.literal('oracle'),
    name: NonEmptyString,
    configuration: aceDataSourceConnectionConfigurationSchemaByEngine.oracle,
  }),
  z.object({
    engine: z.literal('slack'),
    name: NonEmptyString,
    configuration: aceDataSourceConnectionConfigurationSchemaByEngine.slack,
  }),
  z.object({
    engine: z.literal('salesforce'),
    name: NonEmptyString,
    configuration: aceDataSourceConnectionConfigurationSchemaByEngine.salesforce,
  }),
  z.object({
    engine: z.literal('timescaledb'),
    name: NonEmptyString,
    configuration: aceDataSourceConnectionConfigurationSchemaByEngine.timescaledb,
  }),
  z.object({
    engine: z.literal('sema4_knowledge_base'),
    name: NonEmptyString,
    configuration: aceDataSourceConnectionConfigurationSchemaByEngine.sema4_knowledge_base,
  }),
  z.object({
    engine: z.literal('pgvector'),
    name: NonEmptyString,
    configuration: aceDataSourceConnectionConfigurationSchemaByEngine.pgvector,
  }),
  z.object({
    engine: z.literal('bigquery'),
    name: NonEmptyString,
    configuration: aceDataSourceConnectionConfigurationSchemaByEngine.bigquery,
  }),
  z.object({
    engine: z.literal('databricks'),
    name: NonEmptyString,
    configuration: aceDataSourceConnectionConfigurationSchemaByEngine.databricks,
  }),
]);

export type DataSourceWithConnectionConfiguration = z.infer<
  typeof DataSourceWithConnectionConfiguration
>;

export const DataSourceWithConnectionConfiguration = z.discriminatedUnion('engine', [
  z.object({
    engine: z.literal('postgres'),
    name: NonEmptyString,
    configuration: dataSourceConnectionConfigurationSchemaByEngine.postgres,
  }),
  z.object({
    engine: z.literal('redshift'),
    name: NonEmptyString,
    configuration: dataSourceConnectionConfigurationSchemaByEngine.redshift,
  }),
  z.object({
    engine: z.literal('snowflake'),
    name: NonEmptyString,
    configuration: dataSourceConnectionConfigurationSchemaByEngine.snowflake,
  }),
  z.object({
    engine: z.literal('confluence'),
    name: NonEmptyString,
    configuration: dataSourceConnectionConfigurationSchemaByEngine.confluence,
  }),
  z.object({
    engine: z.literal('mysql'),
    name: NonEmptyString,
    configuration: dataSourceConnectionConfigurationSchemaByEngine.mysql,
  }),
  z.object({
    engine: z.literal('mssql'),
    name: NonEmptyString,
    configuration: dataSourceConnectionConfigurationSchemaByEngine.mssql,
  }),
  z.object({
    engine: z.literal('oracle'),
    name: NonEmptyString,
    configuration: dataSourceConnectionConfigurationSchemaByEngine.oracle,
  }),
  z.object({
    engine: z.literal('slack'),
    name: NonEmptyString,
    configuration: dataSourceConnectionConfigurationSchemaByEngine.slack,
  }),
  z.object({
    engine: z.literal('salesforce'),
    name: NonEmptyString,
    configuration: dataSourceConnectionConfigurationSchemaByEngine.salesforce,
  }),
  z.object({
    engine: z.literal('timescaledb'),
    name: NonEmptyString,
    configuration: dataSourceConnectionConfigurationSchemaByEngine.timescaledb,
  }),
  z.object({
    engine: z.literal('sema4_knowledge_base'),
    name: NonEmptyString,
    configuration: dataSourceConnectionConfigurationSchemaByEngine.sema4_knowledge_base,
  }),
  z.object({
    engine: z.literal('pgvector'),
    name: NonEmptyString,
    configuration: dataSourceConnectionConfigurationSchemaByEngine.pgvector,
  }),
  z.object({
    engine: z.literal('bigquery'),
    name: NonEmptyString,
    configuration: dataSourceConnectionConfigurationSchemaByEngine.bigquery,
  }),
  z.object({
    engine: z.literal('databricks'),
    name: NonEmptyString,
    configuration: dataSourceConnectionConfigurationSchemaByEngine.databricks,
  }),
]);

export type DataConnectionWithSecretPointer = z.infer<typeof DataConnectionWithSecretPointer>;
const DataConnectionWithSecretPointer = getDataConnectionEngineConfigurationSchemas({
  secretSchema: ControlRoomAWSSecretManagerSecret,
});
