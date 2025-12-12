import { z } from 'zod';
import { DataConnection } from '@sema4ai/data-interface';

import { createSparMutation, createSparQuery, createSparQueryOptions, QueryError, ResourceType } from './shared';
import { DataConnectionFormSchema } from '../components/SemanticData/SemanticDataConfiguration/components/form';
import { InspectedTableInfo } from './dataConnections';

// TODO: This model is not complete, update once agent-server-interface is updated and returns correct shape of SemanticModel

export enum SemanticDataValidationErrorKind {
  'semantic_model_missing_required_field' = 'semantic_model_missing_required_field',
  'semantic_model_duplicate_table' = 'semantic_model_duplicate_table',
  'data_connection_not_found' = 'data_connection_not_found',
  'data_connection_connection_failed' = 'data_connection_connection_failed',
  'data_connection_table_not_found' = 'data_connection_table_not_found',
  'missing_data_connection' = 'missing_data_connection',
  'data_connection_table_access_error' = 'data_connection_table_access_error',
  'data_connection_column_invalid_expression' = 'data_connection_column_invalid_expression',
  'file_reference_unresolved' = 'file_reference_unresolved',
  'file_missing_thread_context' = 'file_missing_thread_context',
  'file_not_found' = 'file_not_found',
  'file_inspection_error' = 'file_inspection_error',
  'file_sheet_missing' = 'file_sheet_missing',
  'file_column_missing' = 'file_column_missing',
  'validation_execution_error' = 'validation_execution_error',
  'verified_query_missing_sql_field' = 'verified_query_missing_sql_field',
  'verified_query_references_missing_tables' = 'verified_query_references_missing_tables',
  'verified_query_references_data_frame' = 'verified_query_references_data_frame',
  'verified_query_sql_validation_failed' = 'verified_query_sql_validation_failed',
  'verified_query_missing_nlq_field' = 'verified_query_missing_nlq_field',
  'verified_query_missing_name_field' = 'verified_query_missing_name_field',
  'verified_query_name_validation_failed' = 'verified_query_name_validation_failed',
  'verified_query_name_not_unique' = 'verified_query_name_not_unique',
}

const ValidationMessage = z.object({
  message: z.string(),
  level: z.enum(['error', 'warning']),
  kind: z.enum(SemanticDataValidationErrorKind),
});

export const Dimension = z.object({
  name: z.string(),
  expr: z.string(),
  data_type: z.string(),
  description: z.string().optional(),
  synonyms: z.array(z.string()).optional(),
  sample_values: z.array(z.any()).optional(),
  errors: z.array(ValidationMessage).optional(),
});
export type Dimension = z.infer<typeof Dimension>;

export const VerifiedQuery = z.object({
  name: z.string(),
  nlq: z.string(),
  verified_at: z.string(),
  verified_by: z.string(),
  sql: z.string(),
  sql_errors: z.array(ValidationMessage).optional(),
  nlq_errors: z.array(ValidationMessage).optional(),
  name_errors: z.array(ValidationMessage).optional(),
});
export type VerifiedQuery = z.infer<typeof VerifiedQuery>;

export const SemanticModel = z.object({
  id: z.string(),
  name: z.string(),
  description: z.string(),
  tables: z.array(
    z.object({
      name: z.string(),
      base_table: z.object({
        data_connection_id: z.string().optional(),
        data_connection_name: z.string().optional(),
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
      dimensions: z.array(Dimension).optional(),
      time_dimensions: z.array(Dimension).optional(),
      facts: z.array(Dimension).optional(),
      metrics: z.array(Dimension).optional(),
      errors: z.array(ValidationMessage).optional(),
    }),
  ),
  verified_queries: z.array(VerifiedQuery).optional(),
  errors: z.array(ValidationMessage).optional(),
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
      throw new QueryError(response.message || 'Failed to get semantic data models', {
        code: response.code,
        resource: ResourceType.SemanticData,
      });
    }

    const semanticModels = response.data.flatMap((curr) => {
      return Object.entries<SemanticModel>(curr as Record<string, SemanticModel>).map(([id, model]) => ({
        id,
        name: model.name,
        description: model.description,
        tables: model.tables,
        verified_queries: model.verified_queries,
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
      throw new QueryError(response.message || 'Failed to get semantic data model', {
        code: response.code,
        resource: ResourceType.SemanticData,
      });
    }

    return response.data as SemanticModel;
  },
}));

export const useSemanticModelQuery = createSparQuery(semanticModelQueryOptions);

/**
 * Get Agents Semantic Data Validation results
 */
export const getAgentSemanticDataValidationQueryKey = (agentId: string, threadId?: string): (string | number)[] =>
  threadId ? ['agent-semantic-data-validation', agentId, threadId] : ['agent-semantic-data-validation', agentId];

const agentSemanticDataValidationQueryOptions = createSparQueryOptions<{ agentId: string; threadId?: string }>()(
  ({ agentId, threadId, sparAPIClient }) => ({
    queryKey: getAgentSemanticDataValidationQueryKey(agentId, threadId),
    queryFn: async () => {
      const response = await sparAPIClient.queryAgentServer('post', '/api/v2/semantic-data-models/validate', {
        params: {},
        body: {
          agent_id: agentId,
          ...(threadId && { thread_id: threadId }),
        },
      });

      if (!response.success) {
        throw new QueryError(response.message || 'Failed to get Semantic Data validation results', {
          code: response.code,
          resource: ResourceType.SemanticData,
        });
      }

      const semanticModels = (
        response.data.results as {
          semantic_data_model_id: string;
          semantic_data_model: SemanticModel;
          errors?: (typeof ValidationMessage)[];
        }[]
      ).map((curr) => {
        return {
          id: curr.semantic_data_model_id,
          name: curr.semantic_data_model.name,
          description: curr.semantic_data_model.description,
          tables: curr.semantic_data_model.tables,
          errors: curr.errors,
        };
      });

      return semanticModels as SemanticModel[];
    },
  }),
);

export const useAgentSemanticDataValidationQuery = createSparQuery(agentSemanticDataValidationQueryOptions);

/**
 * Get Semantic Data Validation results
 */
const getSemanticDataValidationQueryKey = (modelId: string) => ['semantic-data-validation', modelId];

const semanticDataValidationQueryOptions = createSparQueryOptions<{ modelId: string }>()(
  ({ modelId, sparAPIClient }) => ({
    queryKey: getSemanticDataValidationQueryKey(modelId),
    queryFn: async () => {
      const response = await sparAPIClient.queryAgentServer('post', '/api/v2/semantic-data-models/validate', {
        params: {},
        body: {
          semantic_data_model_id: modelId,
        },
      });

      if (!response.success) {
        throw new QueryError(response.message || 'Failed to get Semantic Data validation results', {
          code: response.code,
          resource: ResourceType.SemanticData,
        });
      }

      const validation = response.data.results.find((result) => result.semantic_data_model_id === modelId);
      return validation?.semantic_data_model as SemanticModel;
    },
  }),
);

export const useSemanticDataValidationQuery = createSparQuery(semanticDataValidationQueryOptions);

/**
 * Create Semantic Data Model
 */
export const useCreateSemanticDataMutation = createSparMutation<
  object,
  DataConnectionFormSchema & {
    agentId: string;
    inspectionResult?: InspectedTableInfo;
  }
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
              thread_id: '',
              file_ref: '',
              tables_info: payload.dataSelection,
              inspection_result: payload.inspectionResult,
            },
          ],
        };

    const generateResponse = await sparAPIClient.queryAgentServer('post', '/api/v2/semantic-data-models/generate', {
      body: {
        name: payload.name || 'Semantic Data Model',
        description: payload.description || '',
        agent_id: payload.agentId,
        ...tableData,
      },
    });

    if (!generateResponse.success) {
      throw new QueryError(generateResponse.message || 'Failed to generate Semantic Data model', {
        code: generateResponse.code,
        resource: ResourceType.SemanticData,
      });
    }

    const createResponse = await sparAPIClient.queryAgentServer('post', '/api/v2/semantic-data-models/', {
      body: generateResponse.data,
    });

    if (!createResponse.success) {
      throw new QueryError(createResponse.message || 'Failed to create Semantic Data model', {
        code: createResponse.code,
        resource: ResourceType.SemanticData,
      });
    }

    const existingModels = await sparAPIClient.queryAgentServer('get', '/api/v2/agents/{aid}/semantic-data-models', {
      params: { path: { aid: payload.agentId } },
    });

    if (!existingModels.success) {
      throw new QueryError(existingModels.message || 'Failed to get existing Semantic Data models', {
        code: existingModels.code,
        resource: ResourceType.SemanticData,
      });
    }

    const existingModelIds = existingModels.data.flatMap((curr) => {
      return Object.entries<SemanticModel>(curr as Record<string, SemanticModel>).map(([id]) => id);
    });

    const attachResponse = await sparAPIClient.queryAgentServer('put', '/api/v2/agents/{aid}/semantic-data-models', {
      body: {
        semantic_data_model_ids: [...existingModelIds, createResponse.data.semantic_data_model_id],
      },
      params: { path: { aid: payload.agentId } },
    });

    if (!attachResponse.success) {
      throw new QueryError(attachResponse.message || 'Failed to attach Semantic Data model to Agent', {
        code: attachResponse.code,
        resource: ResourceType.SemanticData,
      });
    }

    return createResponse.data;
  },
  onSuccess: (_, { agentId }) => {
    queryClient.invalidateQueries({ queryKey: getAgentSemanticDataQueryKey(agentId) });
    queryClient.invalidateQueries({ queryKey: getAgentSemanticDataValidationQueryKey(agentId) });
  },
}));

/**
 * Update Semantic Data Model
 */
export const useUpdateSemanticDataModelMutation = createSparMutation<
  object,
  DataConnectionFormSchema & { modelId: string; agentId: string; shouldRegenerateModel: boolean }
>()(({ sparAPIClient, queryClient }) => ({
  mutationFn: async (payload) => {
    let { tables } = payload;

    if (payload.shouldRegenerateModel) {
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
                thread_id: '',
                file_ref: '',
                tables_info: payload.dataSelection,
              },
            ],
          };

      const generateResponse = await sparAPIClient.queryAgentServer('post', '/api/v2/semantic-data-models/generate', {
        body: {
          name: payload.name || '',
          description: payload.description || '',
          agent_id: payload.agentId,
          ...tableData,
          existing_semantic_data_model: {
            name: payload.name,
            description: payload.description,
            tables: payload.tables,
          },
        },
      });

      if (!generateResponse.success) {
        throw new QueryError(generateResponse.message || 'Failed to generate Semantic Data model', {
          code: generateResponse.code,
          resource: ResourceType.SemanticData,
        });
      }

      tables = generateResponse.data.semantic_model.tables as SemanticModel['tables'];
    }

    const response = await sparAPIClient.queryAgentServer(
      'put',
      '/api/v2/semantic-data-models/{semantic_data_model_id}',
      {
        params: { path: { semantic_data_model_id: payload.modelId } },
        body: {
          semantic_model: {
            name: payload.name,
            description: payload.description,
            tables,
            verified_queries: payload.verifiedQueries,
          },
        },
      },
    );

    if (!response.success) {
      throw new QueryError(response.message || 'Failed to update Semantic Data model', {
        code: response.code,
        resource: ResourceType.SemanticData,
      });
    }

    return response.data;
  },
  onSuccess: (_, { agentId, modelId, name }) => {
    queryClient.setQueriesData(
      { queryKey: getAgentSemanticDataValidationQueryKey(agentId) },
      (oldData: SemanticModel[]) => {
        return oldData.map((curr) => {
          if (curr.id === modelId) {
            return { ...curr, name };
          }
          return curr;
        });
      },
    );

    queryClient.invalidateQueries({ queryKey: getSemanticModelQueryKey(modelId) });
    queryClient.invalidateQueries({ queryKey: getAgentSemanticDataQueryKey(agentId) });
    queryClient.invalidateQueries({ queryKey: getAgentSemanticDataValidationQueryKey(agentId) });
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
        throw new QueryError(deleteResponse.message || 'Failed to delete Semantic Data model', {
          code: deleteResponse.code,
          resource: ResourceType.SemanticData,
        });
      }

      return deleteResponse.data;
    },
    onSuccess: (_, { agentId }) => {
      queryClient.invalidateQueries({ queryKey: getAgentSemanticDataQueryKey(agentId) });
      queryClient.invalidateQueries({ queryKey: getAgentSemanticDataValidationQueryKey(agentId) });
    },
  }),
);

export const useExportSemanticDataModelQuery = createSparMutation<object, { modelId: string }>()(
  ({ sparAPIClient }) => ({
    mutationFn: async ({ modelId }) => {
      const response = await sparAPIClient.queryAgentServer(
        'get',
        '/api/v2/semantic-data-models/{semantic_data_model_id}/export',
        {
          params: { path: { semantic_data_model_id: modelId } },
        },
      );

      if (!response.success) {
        throw new QueryError(response.message || 'Failed to export Semantic Data model', {
          code: response.code,
          resource: ResourceType.SemanticData,
        });
      }

      return response.data;
    },
  }),
);

export const useImportSemanticDataModelMutation = createSparMutation<
  object,
  DataConnectionFormSchema & { agentId: string }
>()(({ sparAPIClient, queryClient }) => ({
  mutationFn: async (payload) => {
    const response = await sparAPIClient.queryAgentServer('post', '/api/v2/semantic-data-models/import', {
      params: {},
      body: {
        semantic_model: {
          name: payload.name,
          description: payload.description,
          tables:
            payload.tables?.map((table) => ({
              ...table,
              base_table: {
                ...table.base_table,
                data_connection_id: payload.dataConnectionId,
              },
            })) || [],
          verified_queries: payload.verifiedQueries,
        },
        agent_id: payload.agentId,
      },
    });

    if (!response.success) {
      throw new QueryError(response.message || 'Failed to update Semantic Data model', {
        code: response.code,
        resource: ResourceType.SemanticData,
      });
    }

    const validationResponse = await sparAPIClient.queryAgentServer('post', '/api/v2/semantic-data-models/validate', {
      params: {},
      body: {
        semantic_data_model_id: response.data.semantic_data_model_id,
      },
    });

    if (!validationResponse.success) {
      throw new QueryError(validationResponse.message || 'Failed to validate Semantic Data model', {
        code: validationResponse.code,
        resource: ResourceType.SemanticData,
      });
    }

    const withErrors =
      validationResponse.data.summary?.total_errors && validationResponse.data.summary.total_errors > 0;

    return {
      semanticModelId: response.data.semantic_data_model_id,
      withErrors,
    };
  },
  onSuccess: (_, { agentId }) => {
    queryClient.invalidateQueries({ queryKey: getAgentSemanticDataQueryKey(agentId) });
    queryClient.invalidateQueries({ queryKey: getAgentSemanticDataValidationQueryKey(agentId) });
  },
}));

/**
 * Verify Verified Query
 */
export const useVerifyVerifiedQueryMutation = createSparMutation<
  Record<string, never>,
  {
    semantic_data_model: SemanticModel;
    verified_query: VerifiedQuery;
    accept_initial_name: string;
  }
>()(({ sparAPIClient }) => ({
  mutationFn: async (payload) => {
    const response = await sparAPIClient.queryAgentServer(
      'post',
      '/api/v2/semantic-data-models/verify-verified-query',
      {
        params: {},
        body: {
          semantic_data_model: payload.semantic_data_model,
          verified_query: payload.verified_query,
          accept_initial_name: payload.accept_initial_name || '',
        },
      },
    );

    if (!response.success) {
      throw new QueryError(response.message || 'Failed to verify verified query', {
        code: response.code,
        resource: ResourceType.SemanticData,
      });
    }

    return response.data as { verified_query: VerifiedQuery };
  },
}));

const supportedSemanticDataEngineQueryOptions = createSparQueryOptions<object>()(() => ({
  queryKey: ['supported--semantic-data-engines'],
  queryFn: async () => {
    // TODO: Update once Agent Server returns this listing
    return ['snowflake', 'redshift', 'postgres', 'databricks'] as DataConnection['engine'][];
  },
}));

export const useSupportedSemanticDataEnginesQuery = createSparQuery(supportedSemanticDataEngineQueryOptions);
