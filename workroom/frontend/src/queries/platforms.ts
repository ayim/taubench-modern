import { queryOptions, useMutation, useQueryClient } from '@tanstack/react-query';
import type { paths } from '@sema4ai/agent-server-interface';
import { QueryProps } from './shared';
import { useRouteContext } from '@tanstack/react-router';
import { transformPlatformForEditing, type PlatformForEditing } from './agent-interface-patches';

export type ListPlatformsResponse =
  paths['/api/v2/platforms/']['get']['responses']['200']['content']['application/json'];
export type CreatePlatformBody = paths['/api/v2/platforms/']['post']['requestBody']['content']['application/json'];
export type UpdatePlatformBody =
  paths['/api/v2/platforms/{platform_id}']['put']['requestBody']['content']['application/json'];
export type GetPlatformResponse =
  paths['/api/v2/platforms/{platform_id}']['get']['responses']['200']['content']['application/json'];

export const getListPlatformsQueryOptions = ({ tenantId, agentAPIClient }: QueryProps<{ tenantId: string }>) =>
  queryOptions({
    queryKey: ['platforms', tenantId],
    queryFn: async (): Promise<ListPlatformsResponse> => {
      const response = await agentAPIClient.agentFetch(tenantId, 'get', '/api/v2/platforms/', {
        silent: true,
      });

      if (!response.success) {
        throw new Error(response?.message || 'Failed to fetch platforms');
      }

      return response.data;
    },
  });

export const getPlatformQueryOptions = ({
  tenantId,
  platformId,
  agentAPIClient,
}: QueryProps<{ tenantId: string; platformId: string }>) =>
  queryOptions({
    queryKey: ['platform', tenantId, platformId],
    queryFn: async (): Promise<PlatformForEditing> => {
      const response = await agentAPIClient.agentFetch(tenantId, 'get', '/api/v2/platforms/{platform_id}', {
        params: { path: { platform_id: platformId } },
        silent: true,
      });

      if (!response.success) {
        throw new Error(response?.message || 'Failed to fetch platform');
      }

      return transformPlatformForEditing(response.data);
    },
  });

export const useDeleteLLMMutation = () => {
  const { agentAPIClient } = useRouteContext({ from: '/tenants/$tenantId' });
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ tenantId, platformId }: { tenantId: string; platformId: string }) => {
      await agentAPIClient.agentFetch(tenantId, 'delete', '/api/v2/platforms/{platform_id}', {
        params: { path: { platform_id: platformId } },
        errorMsg: 'Failed to delete LLM',
      });
    },
    onSuccess: async (_data, { tenantId }) => {
      await queryClient.invalidateQueries({ queryKey: ['platforms', tenantId] });
    },
  });
};

export const useCreateLLMMutation = () => {
  const { agentAPIClient } = useRouteContext({ from: '/tenants/$tenantId' });
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ tenantId, body }: { tenantId: string; body: CreatePlatformBody }) => {
      const response = await agentAPIClient.agentFetch(tenantId, 'post', '/api/v2/platforms/', {
        body,
        errorMsg: 'Failed to create LLM',
      });

      if (!response.success) {
        throw new Error(response.message);
      }

      return response.data;
    },
    onSuccess: async (_data, { tenantId }) => {
      await queryClient.invalidateQueries({ queryKey: ['platforms', tenantId] });
    },
  });
};

export const useUpdateLLMMutation = () => {
  const { agentAPIClient } = useRouteContext({ from: '/tenants/$tenantId' });
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      tenantId,
      platformId,
      body,
    }: {
      tenantId: string;
      platformId: string;
      body: UpdatePlatformBody;
    }) => {
      const response = await agentAPIClient.agentFetch(tenantId, 'put', '/api/v2/platforms/{platform_id}', {
        params: { path: { platform_id: platformId } },
        body,
        errorMsg: 'Failed to update LLM',
      });

      if (!response.success) {
        throw new Error(response?.message || 'Failed to update LLM');
      }

      return response.data;
    },
    onSuccess: async (_data, { tenantId, platformId }) => {
      await queryClient.invalidateQueries({ queryKey: ['platforms', tenantId] });
      await queryClient.invalidateQueries({ queryKey: ['platform', tenantId, platformId] });
    },
  });
};
