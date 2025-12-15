import { components } from '@sema4ai/agent-server-interface';
import {
  createSparMutation,
  createSparQuery,
  createSparQueryOptions,
  QueryError,
  ResourceType,
  ServerResponse,
} from './shared';

export type ObservabilityIntegration = components['schemas']['ObservabilityIntegrationResponse'];

// ObservabilitySettings is now a discriminated union (GrafanaSettingsREST | LangSmithSettingsREST)
export type ObservabilitySettings = components['schemas']['ObservabilityIntegrationResponse']['settings'];

export type ObservabilityIntegrationUpsertRequest = components['schemas']['ObservabilityIntegrationUpsertRequest'];

const observabilityIntegrationsQueryKey = () => ['observabilityIntegrations'];

export const observabilityIntegrationsQueryOptions = createSparQueryOptions<object>()(({ sparAPIClient }) => ({
  queryKey: observabilityIntegrationsQueryKey(),
  queryFn: async (): Promise<ServerResponse<'get', '/api/v2/observability/integrations'>> => {
    const response = await sparAPIClient.queryAgentServer('get', '/api/v2/observability/integrations', {
      params: {},
    });

    if (!response.success) {
      throw new QueryError(response.message, { code: response.code, resource: ResourceType.Integration });
    }

    return response.data;
  },
}));

export const useObservabilityIntegrationsQuery = createSparQuery(observabilityIntegrationsQueryOptions);

export const observabilityIntegrationQueryKey = (id: string) => ['observabilityIntegration', id];

export const observabilityIntegrationQueryOptions = createSparQueryOptions<{ integrationId: string }>()(
  ({ sparAPIClient, integrationId }) => ({
    queryKey: observabilityIntegrationQueryKey(integrationId),
    queryFn: async (): Promise<ServerResponse<'get', '/api/v2/observability/integrations/{integration_id}'>> => {
      const response = await sparAPIClient.queryAgentServer(
        'get',
        '/api/v2/observability/integrations/{integration_id}',
        {
          params: { path: { integration_id: integrationId } },
        },
      );

      if (!response.success) {
        throw new QueryError(response.message, { code: response.code, resource: ResourceType.Integration });
      }

      return response.data;
    },
  }),
);

export const useObservabilityIntegrationQuery = createSparQuery(observabilityIntegrationQueryOptions);

export const useCreateObservabilityIntegrationMutation = createSparMutation<
  Record<string, never>,
  ObservabilitySettings
>()(({ sparAPIClient, queryClient }) => ({
  mutationFn: async (observabilitySettings) => {
    const payload: ObservabilityIntegrationUpsertRequest = {
      settings: {
        ...observabilitySettings,
      },
      /**
       * Required for observability integrations - has no meaning to the UI/UX right now,
       * so we're hardcoding it to 1.
       */
      version: '1',
    };

    const response = await sparAPIClient.queryAgentServer('post', '/api/v2/observability/integrations', {
      body: payload,
    });

    if (!response.success) {
      throw new QueryError(response.message || 'Failed to create observability integration', {
        code: response.code,
        resource: ResourceType.Integration,
      });
    }

    return response.data;
  },
  onSuccess: (observabilityIntegration) => {
    queryClient.setQueryData(
      observabilityIntegrationsQueryKey(),
      (observabilityIntegrations: ObservabilityIntegration[]) => {
        return [observabilityIntegration, ...(observabilityIntegrations || [])];
      },
    );

    queryClient.setQueryData(observabilityIntegrationQueryKey(observabilityIntegration.id), observabilityIntegration);
  },
}));

export const useUpdateObservabilityIntegrationMutation = createSparMutation<
  { integrationId: string },
  ObservabilitySettings
>()(({ sparAPIClient, queryClient, integrationId }) => ({
  mutationFn: async (observabilitySettings) => {
    const payload: ObservabilityIntegrationUpsertRequest = {
      settings: {
        ...observabilitySettings,
      },
      /**
       * Required for observability integrations - has no meaning to the UI/UX right now,
       * so we're hardcoding it to 1.
       */
      version: '1',
    };

    const response = await sparAPIClient.queryAgentServer(
      'put',
      '/api/v2/observability/integrations/{integration_id}',
      {
        params: { path: { integration_id: integrationId } },
        body: payload,
      },
    );

    if (!response.success) {
      throw new QueryError(response.message || 'Failed to update observability integration', {
        code: response.code,
        resource: ResourceType.Integration,
      });
    }

    return response.data;
  },
  onSuccess: (observabilityIntegration) => {
    queryClient.setQueryData(
      observabilityIntegrationsQueryKey(),
      (observabilityIntegrations: ObservabilityIntegration[]) => {
        return observabilityIntegrations.map((curr) => (curr.id === integrationId ? observabilityIntegration : curr));
      },
    );
    queryClient.setQueryData(observabilityIntegrationQueryKey(integrationId), observabilityIntegration);
  },
}));
