import { DataConnection as DataConnectionBase } from '@sema4ai/data-interface';

import type { ServerResponse } from '@sema4ai/agent-server-interface';
import { createSparQueryOptions, createSparQuery, createSparMutation, QueryError, ResourceType } from './shared';

import { getAgentSemanticDataValidationQueryKey, SemanticModel } from './semanticData';
import { getTableDimensions } from '../lib/SemanticDataModels';

export type DataConnection = DataConnectionBase & {
  id: string;
  tags?: string[];
  created_at?: string;
  updated_at?: string;
};

/**
 * List Data Connections query
 */
export const dataConnectionsQueryKey = () => ['dataConnections'];
export type InspectedTableInfo = ServerResponse<'post', '/api/v2/data-connections/{connection_id}/inspect'> & {
  inspectionMismatches?: { table: string; columns: string[] }[];
};

export const dataConnectionsQueryOptions = createSparQueryOptions<object>()(({ agentAPIClient }) => ({
  queryKey: dataConnectionsQueryKey(),
  queryFn: async () => {
    const response = await agentAPIClient.agentFetch('get', '/api/v2/data-connections/', {});

    if (!response.success) {
      throw new QueryError(response.message || 'Failed to fetch data connections', {
        code: response.code,
        resource: ResourceType.DataConnection,
      });
    }
    return response.data as DataConnection[];
  },
}));

export const useDataConnectionsQuery = createSparQuery(dataConnectionsQueryOptions);

/**
 * Get Data Connection query
 */
export const dataConnectionQueryKey = (id: string) => ['dataConnection', id];

export const dataConnectionQueryOptions = createSparQueryOptions<{ dataConnectionId: string }>()(
  ({ agentAPIClient, dataConnectionId }) => ({
    queryKey: dataConnectionQueryKey(dataConnectionId),
    queryFn: async () => {
      const response = await agentAPIClient.agentFetch('get', `/api/v2/data-connections/{connection_id}`, {
        params: { path: { connection_id: dataConnectionId } },
      });

      if (!response.success) {
        throw new QueryError(response.message || 'Failed to fetch data connection', {
          code: response.code,
          resource: ResourceType.DataConnection,
        });
      }

      return response.data as DataConnection;
    },
  }),
);

export const useDataConnectionQuery = createSparQuery(dataConnectionQueryOptions);

/**
 * Create Data Connection mutation
 */
export const useCreateDataConnectionMutation = createSparMutation<Record<string, never>, DataConnectionBase>()(
  ({ agentAPIClient, queryClient }) => ({
    mutationFn: async (dataConnection) => {
      const response = await agentAPIClient.agentFetch('post', '/api/v2/data-connections/', {
        body: dataConnection as never,
      });

      if (!response.success) {
        throw new QueryError(response.message || 'Failed to create data connection', {
          code: response.code,
          resource: ResourceType.DataConnection,
        });
      }

      return response.data as DataConnection;
    },
    onSuccess: (dataConnection) => {
      queryClient.setQueryData(dataConnectionsQueryKey(), (dataConnections: DataConnection[]) => {
        return [dataConnection, ...(dataConnections || [])];
      });
    },
  }),
);

/**
 * Update Data Connection mutation
 */
export const useUpdateDataConnectionMutation = createSparMutation<{ dataConnectionId: string }, DataConnection>()(
  ({ agentAPIClient, queryClient, dataConnectionId }) => ({
    mutationFn: async (dataConnection) => {
      const response = await agentAPIClient.agentFetch('put', '/api/v2/data-connections/{connection_id}', {
        params: { path: { connection_id: dataConnectionId } },
        body: dataConnection as never,
      });

      if (!response.success) {
        throw new QueryError(response.message || 'Failed to update data connection', {
          code: response.code,
          resource: ResourceType.DataConnection,
        });
      }

      return response.data;
    },
    onSuccess: (_, dataConnection) => {
      queryClient.setQueryData(dataConnectionsQueryKey(), (dataConnections: DataConnection[]) => {
        return dataConnections?.map((curr) => (curr.id === dataConnectionId ? dataConnection : curr)) || [];
      });
      queryClient.invalidateQueries({ queryKey: getAgentSemanticDataValidationQueryKey() });
    },
  }),
);

export const useDeleteDataConnectionMutation = createSparMutation<
  { dataConnectionId: string },
  { dataConnectionId: string }
>()(({ agentAPIClient, queryClient, dataConnectionId }) => ({
  mutationFn: async () => {
    const response = await agentAPIClient.agentFetch('delete', '/api/v2/data-connections/{connection_id}', {
      params: { path: { connection_id: dataConnectionId } },
    });

    if (!response.success) {
      throw new QueryError(response.message || 'Failed to delete data connection', {
        code: response.code,
        resource: ResourceType.DataConnection,
      });
    }

    return response.data;
  },
  onSuccess: () => {
    queryClient.setQueryData(dataConnectionsQueryKey(), (dataConnections: DataConnection[]) => {
      return dataConnections.filter((curr) => curr.id !== dataConnectionId);
    });
  },
}));

/**
 * Inspect a database type data Connection data model
 */
export const useDataConnectionDatabaseInspectMutation = createSparMutation<
  object,
  { dataConnectionId: string; semanticModel?: SemanticModel }
>()(({ agentAPIClient }) => ({
  mutationFn: async ({ dataConnectionId, semanticModel }) => {
    const response = await agentAPIClient.agentFetch('post', '/api/v2/data-connections/{connection_id}/inspect', {
      params: { path: { connection_id: dataConnectionId } },
      body: {
        tables_to_inspect: [],
        inspect_columns: true,
        n_sample_rows: 10,
      },
    });

    if (!response.success) {
      throw new QueryError(response.message || 'Failed to inspect data connection', {
        code: response.code,
        resource: ResourceType.DataConnection,
        details: response.details,
      });
    }

    if (!semanticModel) {
      return response.data;
    }

    const inspectionMismatches = semanticModel.tables.flatMap((table) => {
      const tableExists = response.data.tables.find((curr) => curr.name === table.base_table.table);
      if (!tableExists) {
        return [
          { table: table.base_table.table, columns: getTableDimensions(table).map((dimension) => dimension.expr) },
        ];
      }

      const columnMismatches = getTableDimensions(table).flatMap((dimension) => {
        const columnExists = tableExists.columns.find((curr) => curr.name === dimension.expr);
        if (!columnExists) {
          return [dimension.expr];
        }
        return [];
      });

      if (columnMismatches.length > 0) {
        return { table: table.base_table.table, columns: columnMismatches };
      }

      return [];
    });

    if (inspectionMismatches.length > 0) {
      return {
        inspectionMismatches,
        tables: [],
      };
    }

    return response.data;
  },
}));

export const useDataConnectionFileInspectMutation = createSparMutation<
  object,
  { fileName: string; fileContent: Blob }
>()(({ agentAPIClient }) => ({
  mutationFn: async ({ fileName, fileContent }) => {
    const response = await agentAPIClient.agentFetch(
      'post',
      '/api/v2/data-connections/inspect-file-as-data-connection',
      {
        headers: {
          'X-File-Name': fileName,
          'Content-Type': 'application/octet-stream',
        },
        body: fileContent as never, // TODO: Remove type casting once the agent-server-interface is updated
        bodySerializer(body) {
          return body as unknown as Blob;
        },
      },
    );

    if (!response.success) {
      throw new QueryError(response.message || 'Failed to inspect data connection', {
        code: response.code,
        resource: ResourceType.DataConnection,
      });
    }

    return response.data;
  },
}));
