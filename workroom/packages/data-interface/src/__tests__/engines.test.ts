import { z } from 'zod';
import { describe, expect, it } from 'vitest';

import {
  DataSourceWithConnectionConfiguration,
  getDataConnectionEngineConfigurationSchemas,
} from '../lib/dataSources';

type DataConnectionProviders = Extract<
  DataSourceWithConnectionConfiguration,
  { engine: 'sema4_knowledge_base' }
>['configuration'];

describe('getDataConnectionEngineConfigurationSchemas', () => {
  it('parses the sema4_knowledge_base engine correctly when the metadata_columns are specified as string arrays', () => {
    const engineSchemas = getDataConnectionEngineConfigurationSchemas({ secretSchema: z.string() });

    const schemaToParse = {
      engine: 'sema4_knowledge_base',
      configuration: {
        embedding_model: {
          provider: 'openai',
          model_name: 'some model',
          api_key: 'api_key_secret',
        },
        storage: 'test_kb_storage.test_kb_storage_table',
        metadata_columns: ['column_a  ', ' column_b   '], // Leading and trailing spaces
        content_columns: ['column_a', 'column_b'],
        id_column: 'test_id_column',
      },
    };

    const parsedSchema = engineSchemas.safeParse(schemaToParse);

    expect(parsedSchema.success).toBe(true);

    expect((parsedSchema.data?.configuration as DataConnectionProviders).metadata_columns).toEqual([
      'column_a',
      'column_b',
    ]);
    expect((parsedSchema.data?.configuration as DataConnectionProviders).content_columns).toEqual([
      'column_a',
      'column_b',
    ]);
  });

  it('parses the sema4_knowledge_base engine correctly when the metadata_columns are specified as a string of comma-separated values', () => {
    const engineSchemas = getDataConnectionEngineConfigurationSchemas({ secretSchema: z.string() });

    const schemaToParse = {
      engine: 'sema4_knowledge_base',
      configuration: {
        embedding_model: {
          provider: 'openai',
          model_name: 'some model',
          api_key: 'api_key_secret',
        },
        storage: 'test_kb_storage.test_kb_storage_table',
        metadata_columns: 'column_a   ,  column_b', // Leading and trailing spaces
        content_columns: 'column_a, column_b',
        id_column: 'test_id_column',
      },
    };

    const parsedSchema = engineSchemas.safeParse(schemaToParse);

    expect(parsedSchema.success).toBe(true);

    expect((parsedSchema.data?.configuration as DataConnectionProviders).metadata_columns).toEqual([
      'column_a',
      'column_b',
    ]);
    expect((parsedSchema.data?.configuration as DataConnectionProviders).content_columns).toEqual([
      'column_a',
      'column_b',
    ]);
  });

  it('validate the sema4_knowledge_base engine storage format', () => {
    const engineSchemas = getDataConnectionEngineConfigurationSchemas({ secretSchema: z.string() });

    const schemaWithGoodStorage = {
      engine: 'sema4_knowledge_base',
      configuration: {
        embedding_model: {
          provider: 'openai',
          model_name: 'some model',
          api_key: 'api_key_secret',
        },
        storage: 'test_kb_storage.test_kb_storage_table',
        metadata_columns: 'column_a   ,  column_b',
        content_columns: 'column_a, column_b',
        id_column: 'test_id_column',
      },
    };

    const parsedSchemaWithGoodStorage = engineSchemas.safeParse(schemaWithGoodStorage);

    expect(parsedSchemaWithGoodStorage.success).toBe(true);

    const schemaWithBadStorage = {
      engine: 'sema4_knowledge_base',
      configuration: {
        embedding_model: {
          provider: 'openai',
          model_name: 'some model',
          api_key: 'api_key_secret',
        },
        storage: 'test_kb_storage_table', // No datasource name for storage table
        metadata_columns: 'column_a   ,  column_b',
        content_columns: 'column_a, column_b',
        id_column: 'test_id_column',
      },
    };

    const parsedSchemaWithBadStorage = engineSchemas.safeParse(schemaWithBadStorage);

    expect(parsedSchemaWithBadStorage.success).toBe(false);
  });

  it('validates databricks engine http_headers field format', () => {
    const engineSchemas = getDataConnectionEngineConfigurationSchemas({ secretSchema: z.string() });

    const schemaWithInvalidHttpHeaders = {
      engine: 'databricks',
      configuration: {
        server_hostname: 'adb-1234567890123456.7.azuredatabricks.net',
        http_path: '/sql/1.0/warehouses/1234567890abcdef',
        access_token: 'dapi1234567890abcdef',
        http_headers: [
          ['X-Databricks-Feature', 'experimental-feature-1'],
          ['X-Databricks-Feature', 'experimental-feature-2'],
        ],
      },
    };

    const parsedSchemaInvalidHttpHeaders = engineSchemas.safeParse(schemaWithInvalidHttpHeaders);
    expect(parsedSchemaInvalidHttpHeaders.success).toBe(false);

    const schemaWithValidHttpHeaders = {
      engine: 'databricks',
      configuration: {
        server_hostname: 'adb-1234567890123456.7.azuredatabricks.net',
        http_path: '/sql/1.0/warehouses/1234567890abcdef',
        access_token: 'dapi1234567890abcdef',
        http_headers: [
          ['X-Databricks-Feature', 'experimental-client'],
          ['X-Request-Source', 'python-sql-connector'],
        ],
      },
    };

    const parsedSchemaValidHttpHeaders = engineSchemas.safeParse(schemaWithValidHttpHeaders);
    expect(parsedSchemaValidHttpHeaders.success).toBe(true);
  });

  it('accepts snowflake programmatic access token credentials', () => {
    const engineSchemas = getDataConnectionEngineConfigurationSchemas({ secretSchema: z.string() });

    const schemaToParse = {
      engine: 'snowflake',
      configuration: {
        credential_type: 'programmatic-access-token',
        account: 'account_id',
        user: 'user_name',
        password: 'pat_token',
        role: 'ACCOUNTADMIN',
        warehouse: 'COMPUTE_WH',
        database: 'MY_DB',
        schema: 'PUBLIC',
      },
    } as const;

    const parsedSchema = engineSchemas.safeParse(schemaToParse);
    if (!parsedSchema.success) {
      throw new Error(parsedSchema.error.message);
    }

    const { configuration } = parsedSchema.data;
    expect('credential_type' in configuration).toBe(true);
    if ('credential_type' in configuration) {
      expect(configuration.credential_type).toBe('programmatic-access-token');
    }
    expect(configuration).toMatchObject(schemaToParse.configuration);
  });
});
