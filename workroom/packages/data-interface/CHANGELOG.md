# @sema4ai/data-interface

## 3.2.1

### Patch Changes

- e3107a2: fix: re-introduce the undefined credential_type for snowflake connections for backward-compatibility

## 3.2.0

### Minor Changes

- 3bbbefc: Fix Snowflake `configuration.credential_type`password type to match Agent Server returned value

## 3.1.0

### Minor Changes

- b097d25: Enable file logging with log rotation and disable console logging for data server

## 3.0.0

### Major Changes

- a1d6f99: Define custom field types using custom Zod registry `dataSourcesZodRegistry`
- a1d6f99: Update to Zod v4

## 2.3.0

### Minor Changes

- 141a14d: Support for databricks data source

## 2.2.3

### Patch Changes

- eac7f00: expose aceDataSourceConnectionConfigurationSchemaByEngine

## 2.2.2

### Patch Changes

- 70d5b8a: Revert fix for Bigquery connection issue with service_account_json param

## 2.2.1

### Patch Changes

- 9e6e225: Fix: Bigquery connection issue with `service_account_json` param

## 2.2.0

### Minor Changes

- 2c7f93e: Added support for `BigQuery` data source

## 2.1.1

### Patch Changes

- 4f4634d: Fixed typo in embedding and reranking model provider name for kb.

## 2.1.0

### Minor Changes

- 8a4bc56: - Removed the `chromadb` engine.
  - Made `storage` parameter mandatory for `sema4_knowledge_base` engine and `id` column optional.
  - Updated tests.

## 2.0.4

### Patch Changes

- 90c0c3e: Improve schema parsing for comma-separated fields

## 2.0.3

### Patch Changes

- 9964695: Copy tweaks for the knowledge base fields

## 2.0.2

### Patch Changes

- bbf4325: chore: update data server config to be compatible with the latest supported MindsDB release

## 2.0.1

### Patch Changes

- 56d035f: Expose schema creation with custom secret schema

## 2.0.0

### Major Changes

- 322feff: - Added new engine `sema4_knowledge_base` in data-interface to represent knowledge base.
  - Added new engines `pgvector` and `chromadb` for vector dbs required by knowledge base.
  - Updated `addDataSource`, `listDataSources`, `deleteDataSource` methods in data-client to support knowledge base operations in case of `sema4_knowledge_base` engine.
  - Added test cases for knowledge base with pgvector and chromadb.

## 1.4.1

### Patch Changes

- 7987782: Updated data server config to set default_project.

## 1.4.0

### Minor Changes

- 350d2ff: Updated connection params for confluence. Added data client tests for data sources.

## 1.3.0

### Minor Changes

- 0defea2: Added connection params for oracle data source

## 1.2.0

### Minor Changes

- e1d0b0d: Add `getDefaultPortForDataSource` to retrieve default service port for a given data source engine

## 1.1.0

### Minor Changes

- 919de64: Dropping Oracle temporarily

### Patch Changes

- b75a579: Fixed tests

## 1.0.2

### Patch Changes

- 8496372: Stricter data interface types + Slack credentials fix

## 1.0.1

### Patch Changes

- 5710a1b: Removed `pgvector` and `teams` datasource engines. Made `password` required for snowflake legacy auth type. Made `host` and `service_name` required for oracle.

## 1.0.0

### Major Changes

- 2ddb0a8: Add keypair authentication for Snowflake
- fd249d1: Change in Snowflake data types, and getting to semver

## 0.19.0

### Minor Changes

- 557002e: Fields for Snowflake connection are reqquired. Better separation of data in union.
- 557002e: Fields for Snowflake connection are reqquired. Better separation of data in union.

## 0.18.0

### Minor Changes

- 6ad0a36: Snowflake data source in Snowflake

## 0.17.1

### Patch Changes

- 9bca908: Fix: make Slack app_token optional (regression introduced in the previous version)

## 0.17.0

### Minor Changes

- 3182254: fixed the connection params for confluence. also updated the param descriptions for other data sources as per the mindsdb /api/handlers response.

## 0.16.0

### Minor Changes

- 1a20050: Add TimescaleDB and Salesforce data sources

## 0.15.0

### Minor Changes

- 2831130: Replaced `storage_dir` config with `paths.root`, `log` config with `logging`. Added configs `api.http.max_restart_interval_seconds`, `api.mysql.max_restart_interval_seconds` and `auth.http_permanent_session_lifetime`.

## 0.14.0

### Minor Changes

- 9722f7a: Add pgvector, Confluence, MySQL, Microsoft SQL Server, Oracle, Slack and Microsoft Teams data sources

## 0.13.0

### Minor Changes

- 586a068: export customerFacingDataSourceEngineName

## 0.12.0

### Minor Changes

- fb2f86f: Add custom data source to DataSource definition

## 0.11.0

### Minor Changes

- f2e0fcd: Add `custom` Data Source engine type

## 0.10.2

### Patch Changes

- 0caf58c: Added restart on failure for Data Server Rest and SQL interfaces

## 0.10.1

### Patch Changes

- 7418255: Monorepo update

## 0.9.0

### Minor Changes

- 04db5d9: Add back removed types and rename ACEDataConnection

## 0.8.1

### Patch Changes

- 5eb14c3: export helper methods

## 0.8.0

### Minor Changes

- e8bb87c: add utilities to manage model opaque ids

## 0.7.0

### Minor Changes

- add58ea: Remove unused type and rename connectionConfiguration to configuration

## 0.6.2

### Patch Changes

- 1f84e04: Fix host value for the data server config in ACE

## 0.6.1

### Patch Changes

- f4e9c83: Fix: incorrect types for DataConnectionWithSecretPointer

## 0.6.0

### Minor Changes

- 109d14f: Expose DataConnection and DataConnectionWithSecretPointer

## 0.5.0

### Minor Changes

- 7b2f05b: feat: surface ControlRoomDataSource

## 0.4.0

### Minor Changes

- 57f796c: Added 'files' and 'prediction:lightwood' as available engines, improved typing and naming

## 0.3.2

### Patch Changes

- da2fbc1: Fixed stringy booleans in getDataServerConfiguration

## 0.3.1

### Patch Changes

- 804eae3: Add DataSource type

## 0.3.0

### Minor Changes

- c26a4dc: - introduce getDataServerConfiguration
  - match datasource types to MindsDB one (sslMode => sslmode)
  - export ACE datasources

## 0.2.0

### Minor Changes

- 4d9fdbe: Expose getDataSourceSchemas to allow specifying a secret schema

## 0.1.1

### Patch Changes

- b440633: Add explanatory comment

## 0.1.0

### Minor Changes

- e830c97: Initial release
