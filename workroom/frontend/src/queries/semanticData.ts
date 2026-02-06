import { z } from 'zod';
import { DataConnection } from '@sema4ai/data-interface';

import { createSparMutation, createSparQuery, createSparQueryOptions, QueryError, ResourceType } from './shared';
import { threadMessagesQueryKey } from './threads';
import { DataConnectionFormSchema } from '../components/SemanticData/SemanticDataConfiguration/components/types';
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
  'verified_query_name_not_unique' = 'verified_query_name_not_unique',
  'verified_query_name_invalid_format' = 'verified_query_name_invalid_format',
  'verified_query_parameters_validation_failed' = 'verified_query_parameters_validation_failed',
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

export const QueryParameterType = z.enum(['integer', 'float', 'boolean', 'string', 'datetime']);
export type QueryParameterType = z.infer<typeof QueryParameterType>;

export const QueryParameter = z.object({
  name: z.string(),
  data_type: QueryParameterType,
  example_value: z.union([z.string(), z.number(), z.boolean(), z.null()]).optional(),
  description: z.string(),
});
export type QueryParameter = z.infer<typeof QueryParameter>;

export const VerifiedQuery = z.object({
  name: z.string(),
  nlq: z.string(),
  verified_at: z.string(),
  verified_by: z.string(),
  sql: z.string(),
  parameters: z.array(QueryParameter).optional().catch(undefined),
  sql_errors: z.array(ValidationMessage).optional().catch(undefined),
  nlq_errors: z.array(ValidationMessage).optional().catch(undefined),
  name_errors: z.array(ValidationMessage).optional().catch(undefined),
  parameter_errors: z.array(ValidationMessage).optional().catch(undefined),
  result_type: z.enum(['table', 'rows_affected']).nullish(),
});
export type VerifiedQuery = z.infer<typeof VerifiedQuery>;

export const RelationshipColumn = z.object({
  left_column: z.string(),
  right_column: z.string(),
});
export type RelationshipColumn = z.infer<typeof RelationshipColumn>;

export const Relationship = z.object({
  name: z.string(),
  left_table: z.string(),
  right_table: z.string(),
  relationship_columns: z.array(RelationshipColumn),
});
export type Relationship = z.infer<typeof Relationship>;

export const Schema = z.object({
  name: z.string(),
  description: z.string(),
  json_schema: z.record(z.string(), z.unknown()).catch({}),
  validations: z
    .array(
      z.object({
        name: z.string(),
        description: z.string(),
        jq_expression: z.string(),
      }),
    )
    .optional(),
  transformations: z
    .array(
      z.object({
        target_schema_name: z.string(),
        jq_expression: z.string(),
      }),
    )
    .optional(),
});

export const SemanticModel = z.object({
  id: z.string(),
  name: z.string(),
  description: z.string(),
  tables: z.array(
    z.object({
      // Exported SDMs don't have an ID on tables.
      id: z.string().optional(),
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
  schemas: z.array(Schema).optional(),
  relationships: z.array(Relationship).optional(),
  verified_queries: z.array(VerifiedQuery).optional(),
  errors: z.array(ValidationMessage).optional(),
});
export type SemanticModel = z.infer<typeof SemanticModel>;

/**
 * List Agent Semantic data models
 */
const getAgentSemanticDataQueryKey = (agentId: string) => ['agent-semantic-data', agentId];

const agentSemanticDataQueryOptions = createSparQueryOptions<{ agentId: string }>()(({ agentId, agentAPIClient }) => ({
  queryKey: getAgentSemanticDataQueryKey(agentId),
  queryFn: async () => {
    const response = await agentAPIClient.agentFetch('get', '/api/v2/agents/{aid}/semantic-data-models', {
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
        relationships: model.relationships,
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

const semanticModelQueryOptions = createSparQueryOptions<{ modelId: string }>()(({ modelId, agentAPIClient }) => ({
  queryKey: getSemanticModelQueryKey(modelId),
  queryFn: async () => {
    const response = await agentAPIClient.agentFetch('get', '/api/v2/semantic-data-models/{semantic_data_model_id}', {
      params: { path: { semantic_data_model_id: modelId } },
    });

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
export const getAgentSemanticDataValidationQueryKey = (agentId?: string, threadId?: string): (string | number)[] => {
  if (agentId && threadId) {
    return ['agent-semantic-data-validation', agentId, threadId];
  }
  if (agentId) {
    return ['agent-semantic-data-validation', agentId];
  }
  return ['agent-semantic-data-validation'];
};

const agentSemanticDataValidationQueryOptions = createSparQueryOptions<{ agentId: string; threadId?: string }>()(
  ({ agentId, threadId, agentAPIClient }) => ({
    queryKey: getAgentSemanticDataValidationQueryKey(agentId, threadId),
    queryFn: async () => {
      const response = await agentAPIClient.agentFetch('post', '/api/v2/semantic-data-models/validate', {
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
          relationships: curr.semantic_data_model.relationships,
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
  ({ modelId, agentAPIClient }) => ({
    queryKey: getSemanticDataValidationQueryKey(modelId),
    queryFn: async () => {
      const response = await agentAPIClient.agentFetch('post', '/api/v2/semantic-data-models/validate', {
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
      return (validation?.semantic_data_model as SemanticModel) ?? null;
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
    threadId: string;
    inspectionResult?: InspectedTableInfo;
  }
>()(({ agentAPIClient, queryClient }) => ({
  mutationFn: async (payload) => {
    const hasSchemas = (payload.schemas ?? []).length > 0;
    const hasTabularData = !!payload.dataConnectionId || !!payload.fileRefId;

    if (!hasSchemas && !hasTabularData) {
      throw new QueryError('At least one of data connection, file, or schemas must be provided', {
        code: 'BAD_REQUEST',
        resource: ResourceType.SemanticData,
      });
    }

    // Build table data: data connections and files are mutually exclusive
    const buildTableData = () => {
      if (payload.dataConnectionId) {
        return {
          data_connections_info: [
            {
              data_connection_id: payload.dataConnectionId,
              tables_info: payload.dataSelection,
            },
          ],
          files_info: [],
        };
      }

      if (payload.fileRefId) {
        return {
          data_connections_info: [],
          files_info: [
            {
              thread_id: payload.threadId,
              file_ref: '',
              tables_info: payload.dataSelection,
              inspection_result: payload.inspectionResult,
            },
          ],
        };
      }

      return { data_connections_info: [], files_info: [] };
    };

    const tableData = buildTableData();

    const generateResponse = await agentAPIClient.agentFetch('post', '/api/v2/semantic-data-models/generate', {
      body: {
        name: payload.name || 'Semantic Data Model',
        description: payload.description || '',
        agent_id: payload.agentId,
        thread_id: payload.threadId,
        schemas: payload.schemas ?? [],
        ...tableData,
      },
    });

    if (!generateResponse.success) {
      throw new QueryError(generateResponse.message || 'Failed to generate Semantic Data model', {
        code: generateResponse.code,
        resource: ResourceType.SemanticData,
      });
    }

    const createResponse = await agentAPIClient.agentFetch('post', '/api/v2/semantic-data-models/', {
      body: {
        ...generateResponse.data,
        thread_id: payload.threadId,
      },
    });

    if (!createResponse.success) {
      throw new QueryError(createResponse.message || 'Failed to create Semantic Data model', {
        code: createResponse.code,
        resource: ResourceType.SemanticData,
      });
    }

    const existingModels = await agentAPIClient.agentFetch('get', '/api/v2/agents/{aid}/semantic-data-models', {
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

    const attachResponse = await agentAPIClient.agentFetch('put', '/api/v2/agents/{aid}/semantic-data-models', {
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
  onSuccess: (_, { agentId, threadId }) => {
    queryClient.invalidateQueries({ queryKey: getAgentSemanticDataQueryKey(agentId) });
    queryClient.invalidateQueries({ queryKey: getAgentSemanticDataValidationQueryKey(agentId) });
    queryClient.invalidateQueries({ queryKey: threadMessagesQueryKey(threadId) });
  },
}));

/**
 * Update Semantic Data Model
 */
export const useUpdateSemanticDataModelMutation = createSparMutation<
  object,
  DataConnectionFormSchema & { modelId: string; agentId: string; shouldRegenerateModel: boolean; threadId: string }
>()(({ agentAPIClient, queryClient }) => ({
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
                thread_id: payload.threadId,
                file_ref: '',
                tables_info: payload.dataSelection,
              },
            ],
          };

      const generateResponse = await agentAPIClient.agentFetch('post', '/api/v2/semantic-data-models/generate', {
        body: {
          name: payload.name || '',
          description: payload.description || '',
          agent_id: payload.agentId,
          thread_id: payload.threadId,
          schemas: payload.schemas ?? [],
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

    tables = tables?.map((table: SemanticModel['tables'][number]) => {
      return {
        ...table,
        base_table: {
          ...table.base_table,
          data_connection_id: payload.dataConnectionId,
        },
      };
    });

    const response = await agentAPIClient.agentFetch('put', '/api/v2/semantic-data-models/{semantic_data_model_id}', {
      params: { path: { semantic_data_model_id: payload.modelId } },
      body: {
        thread_id: payload.threadId,
        semantic_model: {
          name: payload.name || '',
          description: payload.description || '',
          tables,
          relationships: payload.relationships,
          verified_queries: payload.verifiedQueries,
          schemas: payload.schemas,
        },
      },
    });

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
  ({ agentAPIClient, queryClient }) => ({
    mutationFn: async ({ modelId }) => {
      const deleteResponse = await agentAPIClient.agentFetch(
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
  ({ agentAPIClient }) => ({
    mutationFn: async ({ modelId }) => {
      const response = await agentAPIClient.agentFetch(
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
  DataConnectionFormSchema & { agentId: string; threadId: string }
>()(({ agentAPIClient, queryClient }) => ({
  mutationFn: async (payload) => {
    const response = await agentAPIClient.agentFetch('post', '/api/v2/semantic-data-models/import', {
      params: {},
      body: {
        semantic_model: {
          name: payload.name || '',
          description: payload.description || '',
          tables:
            payload.tables?.map((table: SemanticModel['tables'][number]) => ({
              ...table,
              base_table: {
                ...table.base_table,
                data_connection_id: payload.dataConnectionId,
              },
            })) || [],
          relationships: payload.relationships,
          verified_queries: payload.verifiedQueries,
        },
        agent_id: payload.agentId,
        thread_id: payload.threadId,
      },
    });

    if (!response.success) {
      throw new QueryError(response.message || 'Failed to update Semantic Data model', {
        code: response.code,
        resource: ResourceType.SemanticData,
      });
    }

    const validationResponse = await agentAPIClient.agentFetch('post', '/api/v2/semantic-data-models/validate', {
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
  onSuccess: (_, { agentId, threadId }) => {
    queryClient.invalidateQueries({ queryKey: getAgentSemanticDataQueryKey(agentId) });
    queryClient.invalidateQueries({ queryKey: getAgentSemanticDataValidationQueryKey(agentId) });
    queryClient.invalidateQueries({ queryKey: threadMessagesQueryKey(threadId) });
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
>()(({ agentAPIClient }) => ({
  mutationFn: async (payload) => {
    const response = await agentAPIClient.agentFetch('post', '/api/v2/semantic-data-models/verify-verified-query', {
      params: {},
      body: {
        semantic_data_model: payload.semantic_data_model,
        verified_query: payload.verified_query,
        accept_initial_name: payload.accept_initial_name || '',
      },
    });

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

/**
 * Validate JSON Schema
 */

export const ValidateJsonSchemaPayload = z.object({
  json_schema: z.record(z.string(), z.unknown()),
});
export type ValidateJsonSchemaPayload = z.infer<typeof ValidateJsonSchemaPayload>;

export const SchemaValidationError = z.object({
  path: z.string(),
  message: z.string(),
});
export type SchemaValidationError = z.infer<typeof SchemaValidationError>;

export const ValidateJsonSchemaResponse = z.object({
  is_valid: z.boolean(),
  errors: z.array(SchemaValidationError),
});
export type ValidateJsonSchemaResponse = z.infer<typeof ValidateJsonSchemaResponse>;

export const useValidateJsonSchemaMutation = createSparMutation<Record<string, never>, ValidateJsonSchemaPayload>()(
  ({ agentAPIClient }) => ({
    mutationFn: async (payload) => {
      const response = await agentAPIClient.agentFetch('post', '/api/v2/semantic-data-models/schemas/validate', {
        params: {},
        body: payload,
      });

      if (!response.success) {
        throw new QueryError(response.message || 'Failed to validate JSON schema', {
          code: response.code,
          resource: ResourceType.SemanticData,
        });
      }

      return response.data as ValidateJsonSchemaResponse;
    },
  }),
);
