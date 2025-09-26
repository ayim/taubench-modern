import { createSparMutation, createSparQuery, createSparQueryOptions } from './shared';
import { DataConnectionFormSchema } from '../components/SemanticData/SemanticDataConfiguration/components/form';

// TODO: Remove type casting once interface is fixed
type SemanticModel = {
  id: string;
  name: string;
  description: string;
  tables: {
    name: string;
    base_table: {
      data_connection_id: string;
      database: string | null;
      schema: string | null;
      table: string;
    };
    description: string | null;
    dimensions: {
      name: string;
      expr: string;
      data_type: string;
    }[];
    facts: string[];
    time_dimensions: string[];
  }[];
};

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
  DataConnectionFormSchema & { agentId: string }
>()(({ sparAPIClient, queryClient }) => ({
  mutationFn: async (payload) => {
    const generateResponse = await sparAPIClient.queryAgentServer('post', '/api/v2/semantic-data-models/generate', {
      body: {
        name: 'Semantic Data Model',
        description: payload.description || '',
        data_connections_info: [
          {
            data_connection_id: payload.dataConnectionId,
            tables_info: payload.dataSelection,
          },
        ],
        files_info: [],
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
