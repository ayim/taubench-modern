import { DataConnection as DataConnectionBase } from '@sema4ai/data-interface';

import { createSparQueryOptions, createSparQuery, createSparMutation } from './shared';

export type DataConnection = DataConnectionBase & { id: string; tags?: string[] };

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
    return response.data as DataConnection[];
  },
}));

export const useDataConnectionsQuery = createSparQuery(dataConnectionsQueryOptions);

/**
 * Get Data Connection query
 */
export const dataConnectionQueryKey = (id: string) => ['dataConnection', id];

export const dataConnectionQueryOptions = createSparQueryOptions<{ dataConnectionId: string }>()(
  ({ sparAPIClient, dataConnectionId }) => ({
    queryKey: dataConnectionQueryKey(dataConnectionId),
    queryFn: async () => {
      const response = await sparAPIClient.queryAgentServer('get', `/api/v2/data-connections/{connection_id}`, {
        params: { path: { connection_id: dataConnectionId } },
      });

      if (!response.success) {
        throw new Error(response.message || 'Failed to fetch data connection');
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
  ({ sparAPIClient, queryClient }) => ({
    mutationFn: async (dataConnection) => {
      const response = await sparAPIClient.queryAgentServer('post', '/api/v2/data-connections/', {
        body: dataConnection as never,
      });

      if (!response.success) {
        throw new Error(response.message || 'Failed to create data connection');
      }

      return response.data;
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
  ({ sparAPIClient, queryClient, dataConnectionId }) => ({
    mutationFn: async (dataConnection) => {
      const response = await sparAPIClient.queryAgentServer('put', '/api/v2/data-connections/{connection_id}', {
        params: { path: { connection_id: dataConnectionId } },
        body: dataConnection as never,
      });

      if (!response.success) {
        throw new Error(response.message || 'Failed to update data connection');
      }

      return response.data;
    },
    onSuccess: (_, dataConnection) => {
      queryClient.setQueryData(dataConnectionsQueryKey(), (dataConnections: DataConnection[]) => {
        return dataConnections.map((curr) => (curr.id === dataConnectionId ? dataConnection : curr));
      });
    },
  }),
);

export const useDeleteDataConnectionMutation = createSparMutation<
  { dataConnectionId: string },
  { dataConnectionId: string }
>()(({ sparAPIClient, queryClient, dataConnectionId }) => ({
  mutationFn: async () => {
    const response = await sparAPIClient.queryAgentServer('delete', '/api/v2/data-connections/{connection_id}', {
      params: { path: { connection_id: dataConnectionId } },
    });

    if (!response.success) {
      throw new Error(response.message || 'Failed to delete data connection');
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
 * Inspect a Data Connection data model
 */

export const dataConnectionInspectQueryKey = (id: string) => ['dataConnectionInspect', id];

export const dataConnectionInspectQueryOptions = createSparQueryOptions<{ dataConnectionId: string }>()(
  ({ sparAPIClient, dataConnectionId }) => ({
    queryKey: dataConnectionInspectQueryKey(dataConnectionId),
    queryFn: async () => {
      const response = await sparAPIClient.queryAgentServer(
        'post',
        '/api/v2/data-connections/{connection_id}/inspect',
        {
          params: { path: { connection_id: dataConnectionId } },
          body: {
            tables_to_inspect: [],
            inspect_columns: true,
            n_sample_rows: 10,
          },
        },
      );

      if (!response.success) {
        throw new Error(response.message || 'Failed to inspect data connection');
      }

      return response.data.tables;
    },
  }),
);

export const useDataConnectionInspectQuery = createSparQuery(dataConnectionInspectQueryOptions);
