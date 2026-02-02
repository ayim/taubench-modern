import type { DataSourceEngine, DataSourceEngineWithConnection } from './dataSources';

export type Result<T> =
  | { success: true; data: T }
  | { success: false; error: { code: string; message: string } };

export const createModelId = ({
  projectName,
  modelName,
}: {
  projectName: string;
  modelName: string;
}) => {
  return `${projectName}:${modelName}`;
};

export const parseModelId = ({
  modelId,
}: {
  modelId: string;
}): Result<{ projectName: string; modelName: string }> => {
  const tokens = modelId.split(':');
  if (tokens.length !== 2) {
    return {
      success: false,
      error: {
        code: 'parse_error',
        message: `Cannot parse model id: expected "PROJECT_NAME:MODEL_NAME"`,
      },
    };
  }
  return {
    success: true,
    data: {
      projectName: tokens[0],
      modelName: tokens[1],
    },
  };
};

const capitalize = (str: string) => str.charAt(0).toUpperCase() + str.slice(1).toLowerCase();

export const customerFacingDataSourceEngineName = (engine: DataSourceEngine) => {
  switch (engine) {
    case 'prediction:lightwood':
      return 'Lightwood Predictions';
    case 'postgres':
      return 'PostgreSQL';
    case 'snowflake':
    case 'redshift':
    case 'custom':
    case 'files':
    case 'confluence':
    case 'oracle':
    case 'slack':
    case 'salesforce':
    case 'databricks':
      return capitalize(engine);
    case 'mysql':
      return 'MySQL';
    case 'mssql':
      return 'Microsoft SQL Server';
    case 'timescaledb':
      return 'TimescaleDB';
    case 'sema4_knowledge_base':
      return 'Knowledge Base';
    case 'pgvector':
      return 'PGVector';
    case 'bigquery':
      return 'BigQuery';
    default:
      engine satisfies never;
      const safeEngineName = typeof engine !== 'string' ? 'Unknown' : engine;
      return capitalize(safeEngineName);
  }
};

/**
 * Returns the default service port for a given data source engine.
 * @param engine The engine of the data source.
 * @returns The default port for the data source engine.
 *
 * Used in:
 * - SPCS: `buildNetworkRuleConfigurationUpdateCommand` to generate Snowflake EAI rules that require a hostname:port format
 */
export const getDefaultPortForDataSource = (engine: DataSourceEngineWithConnection): number => {
  switch (engine) {
    case 'postgres':
    case 'pgvector':
      return 5432;
    case 'mysql':
      return 3306;
    case 'mssql':
      return 1433;
    case 'oracle':
      return 1521;
    case 'redshift':
      return 5439;
    case 'timescaledb':
      return 5432;
    case 'snowflake':
    case 'confluence':
    case 'slack':
    case 'salesforce':
    case 'sema4_knowledge_base':
    case 'bigquery':
    case 'databricks':
      return 443;
    default:
      engine satisfies never;
      return 443;
  }
};

export const commaSeparatedStringParsing = (val: string | string[]): string[] => {
  if (Array.isArray(val)) {
    return val.flatMap((s) => commaSeparatedStringParsing(s));
  }

  return val
    .split(',')
    .map((s) => s.trim())
    .filter((s) => s !== '');
};
