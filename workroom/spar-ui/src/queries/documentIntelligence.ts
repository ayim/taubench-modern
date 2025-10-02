import type { components } from '@sema4ai/agent-server-interface';
import { createSparQuery, createSparQueryOptions, createSparMutation, ServerResponse, ServerRequest } from './shared';
import { SparAPIClient } from '../api';

const getListModelsQueryKey = () => ['document-intelligence', 'data-models'];
const getDataModelQueryKey = (modelName: string) => ['document-intelligence', 'data-models', modelName];
const getLayoutsQueryKey = () => ['document-intelligence', 'layouts'];
const getLayoutQueryKey = (layoutName: string, dataModelName: string) => [
  'document-intelligence',
  'layouts',
  layoutName,
  dataModelName,
];

type CreateDataModelRequest = components['schemas']['CreateDataModelRequest'];
type UpdateDataModelRequest = components['schemas']['UpdateDataModelRequest'];

type ExtractDocumentPayload = components['schemas']['ExtractDocumentPayload'];

type GenerateDataQualityChecksRequest = components['schemas']['GenerateDataQualityChecksRequest'];
type ExecuteQualityChecksRequest = ServerRequest<
  'post',
  '/api/v2/document-intelligence/quality-checks/execute',
  'requestBody'
>;

// File upload types for document intelligence endpoints
type DocumentIntelligenceFileUpload = File;

// Layout data type from agent-server-interface
type DocumentLayoutPayload = components['schemas']['DocumentLayoutPayload'];

export const listModelsQueryOptions = ({ sparAPIClient }: { sparAPIClient: SparAPIClient }) => ({
  queryKey: getListModelsQueryKey(),
  queryFn: async (): Promise<ServerResponse<'get', '/api/v2/document-intelligence/data-models'>> => {
    const response = await sparAPIClient.queryAgentServer('get', '/api/v2/document-intelligence/data-models', {
      params: {},
    });
    if (!response.success) {
      throw new Error(response.message);
    }
    return response.data;
  },
});
export const useListModelsQuery = createSparQuery(listModelsQueryOptions);

export const getDataModelQueryOptions = createSparQueryOptions<{ modelName: string }>()(
  ({ sparAPIClient, modelName }) => ({
    queryKey: getDataModelQueryKey(modelName),
    queryFn: async (): Promise<ServerResponse<'get', '/api/v2/document-intelligence/data-models/{model_name}'>> => {
      const response = await sparAPIClient.queryAgentServer(
        'get',
        '/api/v2/document-intelligence/data-models/{model_name}',
        {
          params: { path: { model_name: modelName } },
        },
      );
      if (!response.success) {
        throw new Error(response.message);
      }
      return response.data;
    },
  }),
);

export const useGetDataModelQuery = createSparQuery(getDataModelQueryOptions);

export const useParseDocumentMutation = createSparMutation<
  object,
  {
    threadId: string;
    formData: DocumentIntelligenceFileUpload;
  }
>()(({ sparAPIClient }) => ({
  mutationFn: async ({
    threadId,
    formData,
  }): Promise<ServerResponse<'post', '/api/v2/document-intelligence/documents/parse'>> => {
    const response = await sparAPIClient.queryAgentServer('post', '/api/v2/document-intelligence/documents/parse', {
      params: {
        query: {
          thread_id: threadId,
        },
      },
      body: { file: formData as unknown as string },
      bodySerializer(body: { file: string }) {
        const formDataSerializer = new FormData();
        formDataSerializer.append('file', body.file);
        return formDataSerializer;
      },
    });
    if (!response.success) {
      throw new Error(response.message);
    }
    return response.data;
  },
}));

export const useExtractDocumentMutation = createSparMutation<
  object,
  {
    threadId: ExtractDocumentPayload['thread_id'];
    fileName: ExtractDocumentPayload['file_name'];
    dataModelName?: ExtractDocumentPayload['data_model_name'];
    dataModelPrompt?: ExtractDocumentPayload['data_model_prompt'];
    layoutName?: ExtractDocumentPayload['layout_name'];
    documentLayout?: ExtractDocumentPayload['document_layout'];
    generateCitations?: ExtractDocumentPayload['generate_citations'];
  }
>()(({ sparAPIClient }) => ({
  mutationFn: async ({
    threadId,
    fileName,
    dataModelName,
    dataModelPrompt,
    layoutName,
    documentLayout,
    generateCitations,
  }): Promise<ServerResponse<'post', '/api/v2/document-intelligence/documents/extract'>> => {
    const response = await sparAPIClient.queryAgentServer('post', '/api/v2/document-intelligence/documents/extract', {
      body: {
        thread_id: threadId,
        file_name: fileName,
        data_model_name: dataModelName,
        data_model_prompt: dataModelPrompt,
        layout_name: layoutName,
        document_layout: documentLayout,
        generate_citations: generateCitations ?? true,
      } satisfies ExtractDocumentPayload,
    });
    if (!response.success) {
      throw new Error(response.message);
    }
    return response.data;
  },
}));

export const useCreateDataModelMutation = createSparMutation<
  object,
  {
    agentId: string;
    threadId?: string;
    dataModel: CreateDataModelRequest['data_model'];
  }
>()(({ sparAPIClient, queryClient }) => ({
  mutationFn: async ({ agentId, threadId, dataModel }) => {
    const response = await sparAPIClient.queryAgentServer('post', '/api/v2/document-intelligence/data-models', {
      params: {
        query: {
          agent_id: agentId,
          thread_id: threadId,
        },
      },
      body: {
        data_model: dataModel,
      } satisfies CreateDataModelRequest,
    });
    if (!response.success) {
      throw new Error(response.message);
    }
    return response.data;
  },
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: getListModelsQueryKey() });
  },
}));

export const useUpdateDataModelMutation = createSparMutation<
  object,
  {
    modelName: string;
    dataModel: UpdateDataModelRequest['data_model'];
  }
>()(({ sparAPIClient, queryClient }) => ({
  mutationFn: async ({ modelName, dataModel }) => {
    const response = await sparAPIClient.queryAgentServer(
      'put',
      '/api/v2/document-intelligence/data-models/{model_name}',
      {
        params: { path: { model_name: modelName } },
        body: {
          data_model: dataModel,
        } satisfies UpdateDataModelRequest,
      },
    );
    if (!response.success) {
      throw new Error(response.message);
    }
    return response.data;
  },
  onSuccess: (data, { modelName }) => {
    queryClient.invalidateQueries({ queryKey: getListModelsQueryKey() });
    queryClient.invalidateQueries({ queryKey: getDataModelQueryKey(modelName) });
  },
}));

export const useDeleteDataModelMutation = createSparMutation<object, { modelName: string }>()(
  ({ sparAPIClient, queryClient }) => ({
    mutationFn: async ({ modelName }) => {
      const response = await sparAPIClient.queryAgentServer(
        'delete',
        '/api/v2/document-intelligence/data-models/{model_name}',
        {
          params: { path: { model_name: modelName } },
        },
      );
      if (!response.success) {
        throw new Error(response.message);
      }
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: getListModelsQueryKey() });
    },
  }),
);

export const useGenerateDataModelMutation = createSparMutation<
  object,
  {
    threadId: string;
    agentId: string;
    formData: DocumentIntelligenceFileUpload;
  }
>()(({ sparAPIClient }) => ({
  mutationFn: async ({
    threadId,
    agentId,
    formData,
  }): Promise<ServerResponse<'post', '/api/v2/document-intelligence/data-models/generate'>> => {
    const response = await sparAPIClient.queryAgentServer(
      'post',
      '/api/v2/document-intelligence/data-models/generate',
      {
        params: { query: { thread_id: threadId, agent_id: agentId } },
        body: { file: formData as unknown as string },
        bodySerializer(body: { file: string }) {
          const formDataSerializer = new FormData();
          formDataSerializer.append('file', body.file);
          return formDataSerializer;
        },
      },
    );
    if (!response.success) {
      throw new Error(response.message);
    }
    return response.data;
  },
}));

export const useGenerateDataModelDescriptionMutation = createSparMutation<
  object,
  {
    threadId: string;
    agentId: string;
    fileRef: string;
  }
>()(({ sparAPIClient }) => ({
  mutationFn: async ({
    threadId,
    agentId,
    fileRef,
  }): Promise<ServerResponse<'post', '/api/v2/document-intelligence/data-models/generate-description'>> => {
    const response = await sparAPIClient.queryAgentServer(
      'post',
      '/api/v2/document-intelligence/data-models/generate-description',
      {
        params: { query: { agent_id: agentId, thread_id: threadId, file_ref: fileRef } },
      },
    );
    if (!response.success) {
      throw new Error(response.message);
    }
    return response.data;
  },
}));

export const listLayoutsQueryOptions = ({ sparAPIClient }: { sparAPIClient: SparAPIClient }) => ({
  queryKey: getLayoutsQueryKey(),
  queryFn: async (): Promise<ServerResponse<'get', '/api/v2/document-intelligence/layouts'>> => {
    const response = await sparAPIClient.queryAgentServer('get', '/api/v2/document-intelligence/layouts', {
      params: {},
    });
    if (!response.success) {
      throw new Error(response.message);
    }
    return response.data;
  },
});
export const useListLayoutsQuery = createSparQuery(listLayoutsQueryOptions);

export const getLayoutQueryOptions = createSparQueryOptions<{
  layoutName: string;
  dataModelName: string;
}>()(({ sparAPIClient, layoutName, dataModelName }) => ({
  queryKey: getLayoutQueryKey(layoutName, dataModelName),
  queryFn: async (): Promise<ServerResponse<'get', '/api/v2/document-intelligence/layouts/{layout_name}'>> => {
    const response = await sparAPIClient.queryAgentServer(
      'get',
      '/api/v2/document-intelligence/layouts/{layout_name}',
      {
        params: {
          path: { layout_name: layoutName },
          query: { data_model_name: dataModelName },
        },
      },
    );
    if (!response.success) {
      throw new Error(response.message);
    }
    return response.data;
  },
}));
export const useGetLayoutQuery = createSparQuery(getLayoutQueryOptions);

export const useUpsertLayoutMutation = createSparMutation<
  object,
  {
    layoutData: DocumentLayoutPayload;
  }
>()(({ sparAPIClient, queryClient }) => ({
  mutationFn: async ({ layoutData }) => {
    const response = await sparAPIClient.queryAgentServer('post', '/api/v2/document-intelligence/layouts', {
      body: layoutData,
    });
    if (!response.success) {
      throw new Error(response.message);
    }
    return response.data;
  },
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: getLayoutsQueryKey() });
  },
}));

export const useGenerateLayoutMutation = createSparMutation<
  object,
  {
    dataModelName: string;
    threadId: string;
    agentId: string;
    formData: DocumentIntelligenceFileUpload;
  }
>()(({ sparAPIClient }) => ({
  mutationFn: async ({
    dataModelName,
    threadId,
    agentId,
    formData,
  }): Promise<ServerResponse<'post', '/api/v2/document-intelligence/layouts/generate'>> => {
    const response = await sparAPIClient.queryAgentServer('post', '/api/v2/document-intelligence/layouts/generate', {
      params: {
        query: {
          data_model_name: dataModelName,
          thread_id: threadId,
          agent_id: agentId,
        },
      },
      body: { file: formData as unknown as string },
      bodySerializer(body: { file: string }) {
        const formDataSerializer = new FormData();
        formDataSerializer.append('file', body.file);
        return formDataSerializer;
      },
    });
    if (!response.success) {
      throw new Error(response.message);
    }
    return response.data;
  },
}));

export const useIngestDocumentMutation = createSparMutation<
  object,
  {
    threadId: string;
    dataModelName: string;
    layoutName: string;
    agentId: string;
    formData: DocumentIntelligenceFileUpload;
  }
>()(({ sparAPIClient }) => ({
  mutationFn: async ({
    threadId,
    dataModelName,
    layoutName,
    agentId,
    formData,
  }): Promise<ServerResponse<'post', '/api/v2/document-intelligence/documents/ingest'>> => {
    const response = await sparAPIClient.queryAgentServer('post', '/api/v2/document-intelligence/documents/ingest', {
      params: {
        query: {
          thread_id: threadId,
          data_model_name: dataModelName,
          layout_name: layoutName,
          agent_id: agentId,
        },
      },
      body: { file: formData as unknown as string },
      bodySerializer(body: { file: string }) {
        const formDataSerializer = new FormData();
        formDataSerializer.append('file', body.file);
        return formDataSerializer;
      },
    });
    if (!response.success) {
      throw new Error(response.message);
    }
    return response.data;
  },
}));

export const useGenerateQualityChecksMutation = createSparMutation<
  object,
  {
    agentId: string;
    dataModelName: GenerateDataQualityChecksRequest['data_model_name'];
    threadId?: string;
    description?: GenerateDataQualityChecksRequest['description'];
    limit?: GenerateDataQualityChecksRequest['limit'];
  }
>()(({ sparAPIClient }) => ({
  mutationFn: async ({
    agentId,
    dataModelName,
    threadId,
    description,
    limit,
  }): Promise<ServerResponse<'post', '/api/v2/document-intelligence/quality-checks/generate'>> => {
    const response = await sparAPIClient.queryAgentServer(
      'post',
      '/api/v2/document-intelligence/quality-checks/generate',
      {
        params: {
          query: {
            agent_id: agentId,
            thread_id: threadId,
          },
        },
        body: {
          data_model_name: dataModelName,
          description,
          limit: description ? 1 : (limit ?? 1),
        } satisfies GenerateDataQualityChecksRequest,
      },
    );
    if (!response.success) {
      throw new Error(response.message);
    }
    return response.data;
  },
}));

export const useExecuteQualityChecksMutation = createSparMutation<
  object,
  {
    qualityChecks: ExecuteQualityChecksRequest['quality_checks'];
    documentId: ExecuteQualityChecksRequest['document_id'];
  }
>()(({ sparAPIClient }) => ({
  mutationFn: async ({
    qualityChecks,
    documentId,
  }): Promise<ServerResponse<'post', '/api/v2/document-intelligence/quality-checks/execute'>> => {
    const response = await sparAPIClient.queryAgentServer(
      'post',
      '/api/v2/document-intelligence/quality-checks/execute',
      {
        body: {
          quality_checks: qualityChecks,
          document_id: documentId,
        },
      },
    );
    if (!response.success) {
      throw new Error(response.message);
    }
    return response.data;
  },
}));
