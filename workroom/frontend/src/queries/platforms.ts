import { useMutation, useQueryClient } from '@tanstack/react-query';
import type { paths } from '@sema4ai/agent-server-interface';
import { useRouteContext } from '@tanstack/react-router';
import { createSparQuery, createSparQueryOptions, QueryError, ResourceType } from './shared';

export type ListPlatformsResponse =
  paths['/api/v2/platforms/']['get']['responses']['200']['content']['application/json'];
export type CreatePlatformBody = paths['/api/v2/platforms/']['post']['requestBody']['content']['application/json'];
export type UpdatePlatformBody =
  paths['/api/v2/platforms/{platform_id}']['put']['requestBody']['content']['application/json'];
export type GetPlatformResponse =
  paths['/api/v2/platforms/{platform_id}']['get']['responses']['200']['content']['application/json'];

export const getPlatformQueryOptions = createSparQueryOptions<{ platformId: string }>()(
  ({ agentAPIClient, platformId }) => ({
    queryKey: ['platform', platformId],
    queryFn: async () => {
      const response = await agentAPIClient.agentFetch('get', '/api/v2/platforms/{platform_id}', {
        params: { path: { platform_id: platformId } },
      });
      if (!response.success) {
        throw new QueryError(response.message || 'Failed to fetch platform', {
          code: response.code,
          resource: ResourceType.LLMPlatform,
        });
      }
      return response.data;
    },
  }),
);

export const usePlatformQuery = createSparQuery(getPlatformQueryOptions);

export const useDeleteLLMMutation = () => {
  const { agentAPIClient } = useRouteContext({ from: '/tenants/$tenantId' });
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ platformId }: { platformId: string }) => {
      await agentAPIClient.agentFetch('delete', '/api/v2/platforms/{platform_id}', {
        params: { path: { platform_id: platformId } },
        errorMsg: 'Failed to delete LLM',
      });
    },
    onSuccess: async (_data) => {
      await queryClient.invalidateQueries({ queryKey: ['platforms'] });
    },
  });
};

export const useCreateLLMMutation = () => {
  const { agentAPIClient } = useRouteContext({ from: '/tenants/$tenantId' });
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ validateLLM, body }: { validateLLM: boolean; body: CreatePlatformBody }) => {
      if (validateLLM) {
        const { credentials, ...bodyWithoutCredentials } = body;
        const flattenedBody = {
          ...bodyWithoutCredentials,
          ...(credentials || {}),
        };
        const response = await agentAPIClient.agentFetch('post', '/api/v2/capabilities/platforms/{kind}/test', {
          params: { path: { kind: body.kind } },
          body: flattenedBody,
          errorMsg: 'Failed to validate LLM',
        });
        if (!response.success) {
          throw new Error(response.message);
        }
      }
      const response = await agentAPIClient.agentFetch('post', '/api/v2/platforms/', {
        body,
        errorMsg: 'Failed to create LLM',
      });

      if (!response.success) {
        throw new Error(response.message);
      }

      return response.data;
    },
    onSuccess: async (_data) => {
      await queryClient.invalidateQueries({ queryKey: ['platforms'] });
    },
  });
};

export const useUpdateLLMMutation = () => {
  const { agentAPIClient } = useRouteContext({ from: '/tenants/$tenantId' });
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      platformId,
      validateLLM,
      body,
    }: {
      platformId: string;
      validateLLM: boolean;
      body: UpdatePlatformBody;
    }) => {
      if (validateLLM) {
        const { credentials, id, ...updatedBody } = body;
        const flattenedBody = {
          ...updatedBody,
          ...(credentials || {}),
        };
        const response = await agentAPIClient.agentFetch('post', '/api/v2/capabilities/platforms/{kind}/test', {
          params: { path: { kind: body.kind } },
          body: flattenedBody,
          errorMsg: 'Failed to validate LLM',
        });
        if (!response.success) {
          throw new Error(response.message);
        }
      }
      const response = await agentAPIClient.agentFetch('put', '/api/v2/platforms/{platform_id}', {
        params: { path: { platform_id: platformId } },
        body,
        errorMsg: 'Failed to update LLM',
      });

      if (!response.success) {
        throw new Error(response?.message || 'Failed to update LLM');
      }

      return response.data;
    },
    onSuccess: async (_data, { platformId }) => {
      await queryClient.invalidateQueries({ queryKey: ['platforms'] });
      await queryClient.invalidateQueries({ queryKey: ['platform', platformId] });
    },
  });
};
