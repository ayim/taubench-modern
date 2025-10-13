import { z } from 'zod';

import { createSparMutation, createSparQuery, createSparQueryOptions } from './shared';
import { DataConnectionFormSchema } from '../components/SemanticData/SemanticDataConfiguration/components/form';

// TODO: This model is not complete, update once agent-server-interface is updated and returns correct shape of SemanticModel
export const SemanticModel = z.object({
  id: z.string(),
  name: z.string(),
  description: z.string(),
  tables: z.array(
    z.object({
      name: z.string(),
      base_table: z.object({
        data_connection_id: z.string().optional(),
        database: z.string().nullable().optional(),
        schema: z.string().nullable().optional(),
        table: z.string(),
        file_reference: z
          .object({
            thread_id: z.string(),
            file_ref: z.string(),
            sheet_name: z.string().nullable().optional(),
          })
          .optional(),
      }),
      description: z.string().nullable().optional(),
      dimensions: z.array(
        z.object({
          name: z.string(),
          expr: z.string(),
          data_type: z.string(),
          description: z.string().optional(),
          synonyms: z.array(z.string()).optional(),
          sample_values: z.array(z.any()).optional(),
        }),
      ),
    }),
  ),
});
export type SemanticModel = z.infer<typeof SemanticModel>;

/**
 * List Agent Semantic data models
 */
const getAgentSemanticDataQueryKey = (agentId: string) => ['agent-semantic-data', agentId];

const agentSemanticDataQueryOptions = createSparQueryOptions<{ agentId: string }>()(({ agentId, sparAPIClient }) => ({
  queryKey: getAgentSemanticDataQueryKey(agentId),
  queryFn: async () => {
    const response = await sparAPIClient.queryAgentServer('get', '/api/v2/agents/{aid}/semantic-data-models', {
      params: { path: { aid: agentId } },
    });

    if (!response.success) {
      throw new Error(response.message || 'Failed to get semantic data models');
    }

    const semanticModels = response.data.flatMap((curr) => {
      return Object.entries<SemanticModel>(curr as Record<string, SemanticModel>).map(([id, model]) => ({
        id,
        name: model.name,
        description: model.description,
        tables: model.tables,
      }));
    });

    return semanticModels;
  },
}));

export const useAgentSemanticDataQuery = createSparQuery(agentSemanticDataQueryOptions);

/**
 * Get Semantic Data Model
 */
const getSemanticModelQueryKey = (modelId: string) => ['semantic-data-model', modelId];

const semanticModelQueryOptions = createSparQueryOptions<{ modelId: string }>()(({ modelId, sparAPIClient }) => ({
  queryKey: getSemanticModelQueryKey(modelId),
  queryFn: async () => {
    const response = await sparAPIClient.queryAgentServer(
      'get',
      '/api/v2/semantic-data-models/{semantic_data_model_id}',
      {
        params: { path: { semantic_data_model_id: modelId } },
      },
    );

    if (!response.success) {
      throw new Error(response.message || 'Failed to get semantic data model');
    }

    return response.data as SemanticModel;
  },
}));

export const useSemanticModelQuery = createSparQuery(semanticModelQueryOptions);

/**
 * Create Semantic Data Model
 */
export const useCreateSemanticDataMutation = createSparMutation<
  object,
  DataConnectionFormSchema & { agentId: string; threadId: string }
>()(({ sparAPIClient, queryClient }) => ({
  mutationFn: async (payload) => {
    const tableData = payload.dataConnectionId
      ? {
          data_connections_info: [
            {
              data_connection_id: payload.dataConnectionId,
              tables_info: payload.dataSelection,
            },
          ],
          files_info: [],
        }
      : {
          data_connections_info: [],
          files_info: [
            {
              thread_id: payload.threadId,
              file_ref: 'selected-services-june-2025-quarter.csv',
              tables_info: payload.dataSelection,
            },
          ],
        };

    const generateResponse = await sparAPIClient.queryAgentServer('post', '/api/v2/semantic-data-models/generate', {
      body: {
        name: 'Semantic Data Model',
        description: payload.description || '',
        agent_id: payload.agentId,
        ...tableData,
      },
    });

    if (!generateResponse.success) {
      throw new Error(generateResponse.message || 'Failed to generate Semantic Data model');
    }

    const createResponse = await sparAPIClient.queryAgentServer('post', '/api/v2/semantic-data-models/', {
      body: generateResponse.data,
    });

    if (!createResponse.success) {
      throw new Error(createResponse.message || 'Failed to create Semantic Data model');
    }

    const attachResponse = await sparAPIClient.queryAgentServer('put', '/api/v2/agents/{aid}/semantic-data-models', {
      body: {
        semantic_data_model_ids: [createResponse.data.semantic_data_model_id],
      },
      params: { path: { aid: payload.agentId } },
    });

    if (!attachResponse.success) {
      throw new Error(attachResponse.message || 'Failed to attach Semantic Data model to Agent');
    }

    return attachResponse.data;
  },
  onSuccess: (_, { agentId }) => {
    queryClient.invalidateQueries({ queryKey: getAgentSemanticDataQueryKey(agentId) });
  },
}));

/**
 * Update Semantic Data Model
 */
export const useUpdateSemanticDataModelMutation = createSparMutation<
  object,
  DataConnectionFormSchema & { modelId: string; agentId: string }
>()(({ sparAPIClient, queryClient }) => ({
  mutationFn: async (payload) => {
    const response = await sparAPIClient.queryAgentServer(
      'put',
      '/api/v2/semantic-data-models/{semantic_data_model_id}',
      {
        params: { path: { semantic_data_model_id: payload.modelId } },
        body: {
          semantic_model: {
            name: payload.name,
            description: payload.description,
            tables: payload.tables,
          },
        },
      },
    );

    if (!response.success) {
      throw new Error(response.message || 'Failed to update Semantic Data model');
    }

    return response.data;
  },
  onSuccess: (_, { agentId, modelId }) => {
    queryClient.invalidateQueries({ queryKey: getSemanticModelQueryKey(modelId) });
    queryClient.invalidateQueries({ queryKey: getAgentSemanticDataQueryKey(agentId) });
  },
}));

/**
 * Delete Semantic Data Model
 */
export const useDeleteSemanticDataModelMutation = createSparMutation<object, { agentId: string; modelId: string }>()(
  ({ sparAPIClient, queryClient }) => ({
    mutationFn: async ({ modelId }) => {
      const deleteResponse = await sparAPIClient.queryAgentServer(
        'delete',
        '/api/v2/semantic-data-models/{semantic_data_model_id}',
        {
          params: { path: { semantic_data_model_id: modelId } },
        },
      );

      if (!deleteResponse.success) {
        throw new Error(deleteResponse.message || 'Failed to delete Semantic Data model');
      }

      return deleteResponse.data;
    },
    onSuccess: (_, { agentId }) => {
      queryClient.invalidateQueries({ queryKey: getAgentSemanticDataQueryKey(agentId) });
    },
  }),
);
