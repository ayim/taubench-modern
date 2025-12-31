import { useMutation } from '@tanstack/react-query';
import { useSparUIContext } from '../api/context';
import {
  createSparQueryOptions,
  createSparQuery,
  createSparMutation,
  QueryError,
  ResourceType,
  ServerRequest,
  ServerResponse,
} from './shared';
import { AgentPackageInspectionResponse } from './agentPackageInspection';

export const mcpServersQueryKey = () => ['mcp-servers'];
export const mcpServerQueryKey = (mcpServerId: string) => ['mcp-server', mcpServerId];

export const mcpServersQueryOptions = createSparQueryOptions<object>()(({ sparAPIClient }) => ({
  queryKey: mcpServersQueryKey(),
  queryFn: async () => {
    const response = await sparAPIClient.queryAgentServer('get', '/api/v2/mcp-servers/', {});

    if (!response.success) {
      throw new QueryError(response.message || 'Failed to fetch MCP servers', {
        code: response.code,
        resource: ResourceType.McpServer,
      });
    }

    return response.data;
  },
}));

export const useMcpServersQuery = createSparQuery(mcpServersQueryOptions);

export type McpServerGetResponse = ServerResponse<'get', '/api/v2/mcp-servers/{mcp_server_id}'>;

export const getMCPServerQueryOptions = createSparQueryOptions<{ mcpServerId: string }>()(
  ({ sparAPIClient, mcpServerId }) => ({
    queryKey: mcpServerQueryKey(mcpServerId),
    queryFn: async () => {
      const response = await sparAPIClient.queryAgentServer('get', '/api/v2/mcp-servers/{mcp_server_id}', {
        params: { path: { mcp_server_id: mcpServerId } },
      });

      if (!response.success) {
        throw new QueryError(response.message || 'Failed to fetch MCP server', {
          code: response.code,
          resource: ResourceType.McpServer,
        });
      }

      return response.data;
    },
  }),
);

export const useMcpServerQuery = createSparQuery(getMCPServerQueryOptions);

export const useCreateMcpServerMutation = createSparMutation<object, { body: McpServerCreateInput }>()(
  ({ sparAPIClient, queryClient }) => ({
    mutationFn: async ({ body }) => {
      const response = await sparAPIClient.queryAgentServer('post', '/api/v2/mcp-servers/', {
        body,
      });

      if (!response.success) {
        throw new QueryError(response.message || 'Failed to create MCP server', {
          code: response.code,
          resource: ResourceType.McpServer,
        });
      }

      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: mcpServersQueryKey() });
    },
  }),
);

type McpServerUpdate = ServerRequest<'put', '/api/v2/mcp-servers/{mcp_server_id}', 'requestBody'>;
type McpServerUpdateResponse = ServerResponse<'put', '/api/v2/mcp-servers/{mcp_server_id}'>;

export const useUpdateMcpServerMutation = createSparMutation<object, { mcpServerId: string; body: McpServerUpdate }>()(
  ({ sparAPIClient, queryClient }) => ({
    mutationFn: async ({ mcpServerId, body }) => {
      const response = await sparAPIClient.queryAgentServer('put', '/api/v2/mcp-servers/{mcp_server_id}', {
        params: { path: { mcp_server_id: mcpServerId } },
        body,
      });

      if (!response.success) {
        throw new QueryError(response.message || 'Failed to update MCP server', {
          code: response.code,
          resource: ResourceType.McpServer,
        });
      }

      return response.data;
    },
    onSuccess: (mcpServer, { mcpServerId }) => {
      queryClient.setQueryData(mcpServersQueryKey(), (prev: Record<string, McpServerUpdateResponse> | undefined) => ({
        ...(prev ?? {}),
        [mcpServer.mcp_server_id]: mcpServer,
      }));
      queryClient.invalidateQueries({ queryKey: mcpServerQueryKey(mcpServerId) });
    },
  }),
);

type McpServerDeleteResponse = ServerResponse<'delete', '/api/v2/mcp-servers/{mcp_server_id}'>;

export const useDeleteMcpServerMutation = createSparMutation<object, { mcpServerId: string }>()(
  ({ sparAPIClient, queryClient }) => ({
    mutationFn: async ({ mcpServerId }) => {
      const response = await sparAPIClient.queryAgentServer('delete', '/api/v2/mcp-servers/{mcp_server_id}', {
        params: { path: { mcp_server_id: mcpServerId } },
      });

      if (!response.success) {
        throw new QueryError(response.message || 'Failed to delete MCP server', {
          code: response.code,
          resource: ResourceType.McpServer,
        });
      }

      return response.data;
    },
    onSuccess: (_response, { mcpServerId }) => {
      queryClient.setQueryData(mcpServersQueryKey(), (prev: Record<string, McpServerDeleteResponse> | undefined) => {
        if (!prev) return prev;
        // eslint-disable-next-line @typescript-eslint/no-unused-vars
        const { [mcpServerId]: _removed, ...rest } = prev;
        return rest;
      });
    },
  }),
);

/**
 * Create Hosted MCP Server mutation (with file upload)
 *
 * This mutation uploads an agent package ZIP file and creates a hosted MCP server.
 * Only available in Workroom (not Studio).
 */

type McpServerCreateInput = ServerRequest<'post', '/api/v2/mcp-servers/', 'requestBody'>;
export type McpServerCreateResponse = ServerResponse<'post', '/api/v2/mcp-servers/'>;

export const useCreateHostedMcpServerMutation = createSparMutation<
  object,
  {
    name: string;
    file: File;
    headers?: McpServerCreateInput['headers'];
    mcpServerMetadata: AgentPackageInspectionResponse;
  }
>()(({ sparAPIClient, queryClient }) => ({
  mutationFn: async ({ name, file, headers, mcpServerMetadata }) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('name', name);
    if (headers) {
      formData.append('headers', JSON.stringify(headers));
    }
    if (mcpServerMetadata) {
      formData.append('mcp_server_metadata', JSON.stringify(mcpServerMetadata));
    }

    const response = await sparAPIClient.queryAgentServer('post', '/api/v2/mcp-servers/mcp-servers-hosted', {
      body: formData as never,
    });

    if (!response.success) {
      throw new QueryError(response.message || 'Failed to create hosted MCP server', {
        code: response.code,
        resource: ResourceType.McpServer,
      });
    }

    return response.data;
  },
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: mcpServersQueryKey() });
  },
}));

export const useValidateMcpServerCapabilitiesMutation = createSparMutation<
  object,
  { mcpServer: McpServerCreateInput }
>()(({ sparAPIClient }) => ({
  mutationFn: async ({ mcpServer }) => {
    const response = await sparAPIClient.queryAgentServer('post', '/api/v2/capabilities/mcp/tools', {
      body: { mcp_servers: [mcpServer] },
    });

    if (!response.success) {
      throw new QueryError(response.message || 'Failed to validate MCP server', {
        code: response.code,
        resource: ResourceType.McpServer,
      });
    }

    const results = response.data?.results ?? [];
    const allIssues = results.flatMap((result) => result.issues ?? []);
    if (allIssues.length > 0) {
      throw new QueryError(allIssues.join('; '), { resource: ResourceType.McpServer });
    }

    return response.data;
  },
}));

type HostedMcpUploadResult = {
  file: File;
  data: NonNullable<AgentPackageInspectionResponse>;
};

export type UseHostedMcpUploadResult = {
  file: File | null;
  inspectionData: NonNullable<AgentPackageInspectionResponse> | null;
  isPending: boolean;
  error: QueryError | null;
  handleDrop: (files: File[]) => Promise<HostedMcpUploadResult | null>;
  reset: () => void;
};

export const useHostedMcpUpload = (): UseHostedMcpUploadResult => {
  const { sparAPIClient } = useSparUIContext();

  const mutation = useMutation<HostedMcpUploadResult, QueryError, File>({
    mutationFn: async (droppedFile: File) => {
      const isZip = droppedFile.name.toLowerCase().endsWith('.zip');
      if (!isZip) {
        throw new QueryError('File type is not valid. Only ZIP files are allowed.');
      }

      const formData = new FormData();
      formData.append('package_zip_file', droppedFile, droppedFile.name);
      formData.append('name', droppedFile.name.replace(/\.zip$/i, ''));
      formData.append('description', 'Agent package uploaded from UI');

      const response = await sparAPIClient.queryAgentServer('post', '/api/v2/package/inspect/agent', {
        params: {},
        body: formData as never,
      });

      if (!response.success) {
        throw new QueryError(response.message || 'Failed to inspect agent package', {
          code: response.code,
          resource: ResourceType.Agent,
        });
      }

      const result = response.data;
      if (result?.status === 'failure' || !result?.data) {
        throw new QueryError('Failed to inspect agent package: no data returned', {
          resource: ResourceType.Agent,
        });
      }

      return { file: droppedFile, data: result.data };
    },
  });

  const handleDrop = async (files: File[]): Promise<HostedMcpUploadResult | null> => {
    if (files.length > 1) {
      const error = new QueryError('Only one file can be uploaded at a time. Please select a single ZIP file.');
      mutation.reset();
      return Promise.reject(error);
    }

    const droppedFile = files[0];
    if (!droppedFile) {
      return null;
    }

    return mutation.mutateAsync(droppedFile);
  };

  return {
    file: mutation.data?.file ?? null,
    inspectionData: mutation.data?.data ?? null,
    isPending: mutation.isPending,
    error: mutation.error,
    handleDrop,
    reset: mutation.reset,
  };
};
