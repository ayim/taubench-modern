import {
  ActionType,
  DocClass,
  DocTypeConfiguration,
  DocumentAPI,
  DocumentTrainAnnotation,
  IDocumentClassList,
  sortByType,
} from '@sema4ai/agent-components';
import { AgentAPIClient } from './AgentAPIClient';
import { errorToast, successToast } from '~/utils/toasts';
import { SortDirection } from '@sema4ai/components';

export const getDocumentAPIClient = (tenantId: string, agentAPIClient: AgentAPIClient): DocumentAPI => ({
  getDocumentTypesList: async () => {
    return agentAPIClient.docIntelliFetch(
      tenantId,
      'get',
      '/api/v1/document-intelligence/workspace-id/{workspaceId}/document-types/workitems-summary',
      { params: { path: { workspaceId: tenantId } } },
    );
  },
  getDocumentsList: async (
    documentTypeName: string,
    offset: number,
    pageSize: number,
    status: string[],
    showLastNDays: number,
    docNameOrFormatNamePattern?: string,
    is_training?: boolean,
    sortBy?: sortByType,
    sortOrder?: SortDirection,
  ) => {
    return agentAPIClient.docIntelliFetch(
      tenantId,
      'get',
      '/api/v1/document-intelligence/workspace-id/{workspaceId}/document-types/{documentTypeName}/paginated-document-work-items',
      {
        params: {
          path: { documentTypeName, workspaceId: tenantId },
          query: {
            offset,
            showLastNDays,
            docNameOrFormatNamePattern,
            status,
            pageSize,
            is_training,
            sort_by: sortBy,
            sort_order: sortOrder,
          },
        },
      },
    );
  },
  getDocumentDetails: async (documentTypeName, documentId) => {
    return agentAPIClient.docIntelliFetch(
      tenantId,
      'get',
      '/api/v1/document-intelligence/workspace-id/{workspaceId}/document-types/{documentTypeName}/paginated-document-workitems/{documentId}',
      { params: { path: { documentId, documentTypeName, workspaceId: tenantId } } },
    );
  },
  getFile: async (query_param, document_id) => {
    // TODO: maybe improve this function
    return agentAPIClient.docIntelliFetch(
      tenantId,
      'get',
      '/api/v1/document-intelligence/workspace-id/{workspaceId}/raw-content',
      {
        params: { query: { [query_param]: document_id }, path: { workspaceId: tenantId } },
        parseAs: 'blob',
        errorMsg: 'Failed to download the file',
      },
    );
  },
  createDocumentType: async (config) => {
    return agentAPIClient.docIntelliFetch(
      tenantId,
      'post',
      '/api/v1/document-intelligence/workspace-id/{workspaceId}/document-types',
      {
        params: { path: { workspaceId: tenantId } },
        body: {
          document_type_name: config.document_type_name,
          doc_file_format: config.doc_file_format,
        },
        requestBody: { content: 'application/json' },
      },
    );
  },
  getRegisteredAgents: () => {
    return agentAPIClient.agentEventsFetch(tenantId, 'get', '/api/v1/agentevents/triggers/', {
      params: {
        query: { tenant_id: tenantId },
      },
    });
  },
  getDocTypeConfigurations: async (document_type_name: string) => {
    return agentAPIClient.docIntelliFetch(
      tenantId,
      'get',
      '/api/v1/document-intelligence/workspace-id/{workspaceId}/document-types/{documentTypeName}/config',
      { params: { path: { documentTypeName: document_type_name, workspaceId: tenantId } } },
    );
  },
  updateDocTypeConfigurations: async (document_type_name: string, configuration: DocTypeConfiguration) => {
    return agentAPIClient.docIntelliFetch(
      tenantId,
      'post',
      '/api/v1/document-intelligence/workspace-id/{workspaceId}/document-types/{documentTypeName}/config',
      {
        params: { path: { documentTypeName: document_type_name, workspaceId: tenantId } },
        body: configuration,
      },
    );
  },
  getDocumentClassList: async (document_type_name: string) => {
    const documentClasses = agentAPIClient.docIntelliFetch(
      tenantId,
      'get',
      '/api/v1/document-intelligence/workspace-id/{workspaceId}/document-types/{documentTypeName}/document-format',
      { params: { path: { documentTypeName: document_type_name, workspaceId: tenantId } } },
    ) as unknown as IDocumentClassList[];
    return documentClasses;
  },
  getDocumentClass: async (document_type_name: string, document_class_name: string) => {
    return agentAPIClient.docIntelliFetch(
      tenantId,
      'get',
      '/api/v1/document-intelligence/workspace-id/{workspaceId}/document-types/{documentTypeName}/document-format/{documentFormatName}',
      {
        params: {
          path: {
            documentTypeName: document_type_name,
            documentFormatName: document_class_name,
            workspaceId: tenantId,
          },
        },
      },
    );
  },
  updateDocumentFormatConfig: async (document_type_name: string, configuration: DocClass) => {
    return agentAPIClient.docIntelliFetch(
      tenantId,
      'post',
      '/api/v1/document-intelligence/workspace-id/{workspaceId}/document-types/{documentTypeName}/document-format',
      {
        params: { path: { documentTypeName: document_type_name, workspaceId: tenantId } },
        body: configuration,
      },
    );
  },
  updateTrainingDoc: async (document_type_name: string, document_class_name: string, training_doc) => {
    return agentAPIClient.docIntelliFetch(
      tenantId,
      'post',
      '/api/v1/document-intelligence/workspace-id/{workspaceId}/document-types/{documentTypeName}/document-format/{documentFormatName}/training-doc',
      {
        params: {
          path: {
            documentTypeName: document_type_name,
            workspaceId: tenantId,
            documentFormatName: document_class_name,
          },
        },
        body: {
          doc_encoded: training_doc.doc_encoded,
          path_prefix: training_doc.path_prefix,
          file_name: training_doc.file_name,
        },
      },
    );
  },
  getTrainingDoc: async (document_type_name: string, document_class_name: string) => {
    return agentAPIClient.docIntelliFetch(
      tenantId,
      'get',
      '/api/v1/document-intelligence/workspace-id/{workspaceId}/document-types/{documentTypeName}/document-format/{documentFormatName}/training-doc',
      {
        params: {
          path: {
            documentFormatName: document_class_name,
            documentTypeName: document_type_name,
            workspaceId: tenantId,
          },
        },
        errorMsg: 'Training Doc not available.',
      },
    );
  },
  documentAction: async (documentTypeName: string, documentFormatName: string, action: ActionType) => {
    return agentAPIClient.docIntelliFetch(
      tenantId,
      'post',
      '/api/v1/document-intelligence/workspace-id/{workspaceId}/document-types/{documentTypeName}/document-format/{documentFormatName}/training-action',
      {
        params: {
          path: {
            documentTypeName: documentTypeName,
            documentFormatName: documentFormatName,
            workspaceId: tenantId,
          },
        },
        body: {
          action: action,
        },
      },
    );
  },
  updateAnnotations: (
    document_type_name: string,
    document_class_name: string,
    annotations: DocumentTrainAnnotation,
  ) => {
    return agentAPIClient.docIntelliFetch(
      tenantId,
      'post',
      '/api/v1/document-intelligence/workspace-id/{workspaceId}/document-types/{documentTypeName}/document-format/{documentFormatName}/training-annotations',
      {
        params: {
          path: {
            documentTypeName: document_type_name,
            documentFormatName: document_class_name,
            workspaceId: tenantId,
          },
        },
        body: annotations,
      },
    );
  },
  getAnnotations: (document_type_name: string, document_class_name: string) => {
    return agentAPIClient.docIntelliFetch(
      tenantId,
      'get',
      '/api/v1/document-intelligence/workspace-id/{workspaceId}/document-types/{documentTypeName}/document-format/{documentFormatName}/training-annotations',
      {
        params: {
          path: {
            documentTypeName: document_type_name,
            documentFormatName: document_class_name,
            workspaceId: tenantId,
          },
        },
      },
    );
  },
  documentsReproces: async (document_type_name, document_id) => {
    return agentAPIClient.docIntelliFetch(
      tenantId,
      'post',
      '/api/v1/document-intelligence/workspace-id/{workspaceId}/document-types/{documentTypeName}/document-work-items/action',
      {
        params: {
          query: { workItemId: document_id },
          path: { documentTypeName: document_type_name, workspaceId: tenantId },
        },
        body: { action: 'reprocess' },
      },
    );
  },
  postNotificationConfig: async (document_type_name, notificationConfig) => {
    return agentAPIClient.docIntelliFetch(
      tenantId,
      'post',
      '/api/v1/document-intelligence/workspace-id/{workspaceId}/document-types/{documentTypeName}/notif-config',
      {
        params: {
          path: { documentTypeName: document_type_name, workspaceId: tenantId },
        },
        body: {
          document_type_name: notificationConfig.document_type_name ?? '',
          notify_extraction: notificationConfig.notify_extraction ?? false,
          notify_training: notificationConfig.notify_training ?? false,
          password: notificationConfig.password ?? '',
          receivers: notificationConfig.receivers ?? [],
          sender_email: notificationConfig.sender_email ?? '',
          smtp_host: notificationConfig.smtp_host ?? '',
          smtp_port: notificationConfig.smtp_port ?? 0,
          smtp_username: notificationConfig.smtp_username ?? '',
          workspace_id: tenantId,
        },
      },
    );
  },
  getNotificationConfig: async (document_type_name) => {
    return agentAPIClient.docIntelliFetch(
      tenantId,
      'get',
      '/api/v1/document-intelligence/workspace-id/{workspaceId}/document-types/{documentTypeName}/notif-config',
      {
        params: {
          path: {
            documentTypeName: document_type_name,
            workspaceId: tenantId,
          },
        },
      },
    );
  },
  deleteDocumentFormat: async (document_type_name: string, document_class_name: string) => {
    return agentAPIClient.docIntelliFetch(
      tenantId,
      'delete',
      '/api/v1/document-intelligence/workspace-id/{workspaceId}/document-types/{documentTypeName}/document-format/{documentFormatName}',
      {
        params: {
          path: {
            workspaceId: tenantId,
            documentTypeName: document_type_name,
            documentFormatName: document_class_name,
          },
        },
      },
    );
  },
  getExtractionMarkdown(tableAnnotations) {
    return agentAPIClient.docIntelliFetch(
      tenantId,
      'post',
      '/api/v1/document-intelligence/workspace-id/{workspaceId}/llm-service/extract-markdown',
      {
        params: {
          path: { workspaceId: tenantId },
        },
        body: tableAnnotations,
        errorMsg: 'Failed to extract table row examples',
      },
    );
  },
  exportFormats: async (document_type_name, document_classes) => {
    return agentAPIClient.docIntelliFetch(
      tenantId,
      'post',
      '/api/v1/document-intelligence/workspace-id/{workspaceId}/document-types/{documentTypeName}/document-format/export',
      {
        params: { path: { workspaceId: tenantId, documentTypeName: document_type_name } },
        body: document_classes,
        parseAs: 'blob',
      },
    );
  },
  importFormats: async (document_type_name, reqBody) => {
    return agentAPIClient.docIntelliFetch(
      tenantId,
      'post',
      '/api/v1/document-intelligence/workspace-id/{workspaceId}/document-types/{documentTypeName}/document-format/import',
      {
        params: { path: { workspaceId: tenantId, documentTypeName: document_type_name } },
        body: reqBody as { file?: string | undefined; overwrite?: 'true' | 'false' | undefined },
        parseAs: 'blob',
      },
    );
  },
  exportDocTypeNFormats: async (document_type_name) => {
    return agentAPIClient.docIntelliFetch(
      tenantId,
      'post',
      '/api/v1/document-intelligence/workspace-id/{workspaceId}/document-types/{documentTypeName}/export',
      {
        params: { path: { workspaceId: tenantId, documentTypeName: document_type_name } },
        parseAs: 'blob',
      },
    );
  },
  importDocTypeNFormats: async (reqBody) => {
    return agentAPIClient.docIntelliFetch(
      tenantId,
      'post',
      '/api/v1/document-intelligence/workspace-id/{workspaceId}/document-types/import',
      {
        params: { path: { workspaceId: tenantId } },
        body: reqBody as unknown as { file: string; document_type_name: string },
        parseAs: 'blob',
      },
    );
  },
  getLLMDebuggingResult: async (document_type_name, document_class_name, document_id) => {
    return agentAPIClient.docIntelliFetch(
      tenantId,
      'get',
      '/api/v1/document-intelligence/workspace-id/{workspaceId}/document-types/{documentTypeName}/document-format/{documentFormatName}/document-work-item/{documentId}/llm-service/debug-extraction',
      {
        params: {
          path: {
            workspaceId: tenantId,
            documentFormatName: document_class_name,
            documentTypeName: document_type_name,
            documentId: document_id,
          },
        },
        errorMsg: 'Failed to get LLM Debugging result',
      },
    );
  },

  onSuccess: (message: string) => successToast(message),
  onError: (message: string) => errorToast(message),
});
