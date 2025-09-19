import type { components } from '@sema4ai/agent-server-interface';
import { createSparQueryOptions, createSparQuery } from './shared';

export type DataConnection = 
  | components['schemas']['PostgresDataConnection']
  | components['schemas']['RedshiftDataConnection']
  | components['schemas']['SnowflakeDataConnection']
  | components['schemas']['ConfluenceDataConnection']
  | components['schemas']['MySQLDataConnection']
  | components['schemas']['MSSQLDataConnection']
  | components['schemas']['OracleDataConnection']
  | components['schemas']['SlackDataConnection']
  | components['schemas']['SalesforceDataConnection']
  | components['schemas']['TimescaleDBDataConnection']
  | components['schemas']['PgvectorDataConnection']
  | components['schemas']['BigqueryDataConnection']
  | components['schemas']['SemaknowledgebaseDataConnection']
  | components['schemas']['SQLiteDataConnection'];

/**
 * List Data Connections query
 */
export const dataConnectionsQueryKey = () => ['dataConnections'];

export const dataConnectionsQueryOptions = createSparQueryOptions<object>()(({ sparAPIClient }) => ({
  queryKey: dataConnectionsQueryKey(),
  queryFn: async () => {
    const response = await sparAPIClient.queryAgentServer('get', '/api/v2/data-connections/', {});

    if (!response.success) {
      throw new Error(response.message || 'Failed to fetch data connections');
    }
    
    return response.data;
  },
}));

export const useDataConnectionsQuery = createSparQuery(dataConnectionsQueryOptions);
