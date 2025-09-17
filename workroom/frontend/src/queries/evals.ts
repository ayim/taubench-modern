import { queryOptions, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useCallback } from 'react';
import type { components, paths } from '@sema4ai/agent-server-interface';
import { QueryProps } from './shared';
import { useRouteContext } from '@tanstack/react-router';

type ListScenariosResponse = paths['/api/v2/evals/scenarios']['get']['responses']['200']['content']['application/json'];
export type Scenario = components['schemas']['Scenario'];
type CreateScenarioPayload = components['schemas']['CreateScenarioPayload'];
type CreateScenarioRunPayload = components['schemas']['CreateScenarioRunPayload'];
type SuggestScenarioPayload =
  paths['/api/v2/evals/scenarios/suggest']['post']['requestBody']['content']['application/json'];
export type ScenarioSuggestion = components['schemas']['ScenarioSuggestion'];
export type Trial = components['schemas']['Trial'];
type ScenarioRun = components['schemas']['ScenarioRun'];

const MAX_POLLING_ATTEMPTS = 60;
const POLLING_INTERVAL = 2000;

export const getListScenariosQueryOptions = ({
  tenantId,
  agentAPIClient,
  agentId,
  limit,
}: QueryProps<{
  tenantId: string;
  agentId?: string;
  limit?: number;
}>) =>
  queryOptions({
    queryKey: ['scenarios', tenantId, agentId, limit],
    queryFn: async (): Promise<ListScenariosResponse> => {
      const response = await agentAPIClient.agentFetch(tenantId, 'get', '/api/v2/evals/scenarios', {
        params: {
          query: {
            ...(agentId && { agent_id: agentId }),
            ...(limit && { limit }),
          },
        },
        silent: true,
      });
      if (!response.success) {
        throw new Error(response.message);
      }
      return response.data;
    },
  });

export const getScenarioQueryOptions = ({
  tenantId,
  scenarioId,
  agentAPIClient,
}: QueryProps<{ tenantId: string; scenarioId: string }>) =>
  queryOptions({
    queryKey: ['scenario', tenantId, scenarioId],
    queryFn: async (): Promise<Scenario> => {
      const response = await agentAPIClient.agentFetch(tenantId, 'get', '/api/v2/evals/scenarios/{scenario_id}', {
        params: { path: { scenario_id: scenarioId } },
        silent: true,
      });
      if (!response.success) {
        throw new Error(response.message);
      }
      return response.data;
    },
  });

export const getLatestScenarioRunQueryOptions = ({
  tenantId,
  scenarioId,
  agentAPIClient,
}: QueryProps<{ tenantId: string; scenarioId: string }>) =>
  queryOptions({
    queryKey: ['scenario-run-latest', tenantId, scenarioId],
    queryFn: async (): Promise<ScenarioRun | null> => {
      const response = await agentAPIClient.agentFetch(
        tenantId,
        'get',
        '/api/v2/evals/scenarios/{scenario_id}/runs/latest',
        {
          params: { path: { scenario_id: scenarioId } },
          silent: true,
        },
      );
      if (!response.success) {
        throw new Error(response.message);
      }
      return response.data;
    },
    retry: false,
  });

export const useScenariosQuery = ({ tenantId, agentId }: { tenantId: string; agentId: string }) => {
  const { agentAPIClient } = useRouteContext({ from: '/tenants/$tenantId' });
  return useQuery(
    getListScenariosQueryOptions({
      tenantId,
      agentId,
      agentAPIClient,
    }),
  );
};

export const useCreateScenarioMutation = () => {
  const { agentAPIClient } = useRouteContext({ from: '/tenants/$tenantId' });
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ tenantId, body }: { tenantId: string; body: CreateScenarioPayload }): Promise<Scenario> => {
      const response = await agentAPIClient.agentFetch(tenantId, 'post', '/api/v2/evals/scenarios', {
        body,
        errorMsg: 'Failed to create scenario',
      });
      if (!response.success) {
        throw new Error(response.message);
      }
      return response.data;
    },
    onSuccess: async (_data, { tenantId }) => {
      await queryClient.invalidateQueries({ queryKey: ['scenarios', tenantId] });
    },
  });
};

export const useDeleteScenarioMutation = () => {
  const { agentAPIClient } = useRouteContext({ from: '/tenants/$tenantId' });
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ tenantId, scenarioId }: { tenantId: string; scenarioId: string }): Promise<Scenario> => {
      const response = await agentAPIClient.agentFetch(tenantId, 'delete', '/api/v2/evals/scenarios/{scenario_id}', {
        params: { path: { scenario_id: scenarioId } },
        errorMsg: 'Failed to delete scenario',
      });
      if (!response.success) {
        throw new Error(response.message);
      }
      return response.data;
    },
    onSuccess: async (_data, { tenantId, scenarioId }) => {
      await queryClient.invalidateQueries({ queryKey: ['scenarios', tenantId] });
      await queryClient.invalidateQueries({ queryKey: ['scenario', tenantId, scenarioId] });
    },
  });
};

export const useCreateScenarioRunMutation = () => {
  const { agentAPIClient } = useRouteContext({ from: '/tenants/$tenantId' });
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      tenantId,
      scenarioId,
      body,
    }: {
      tenantId: string;
      scenarioId: string;
      body: CreateScenarioRunPayload;
    }): Promise<ScenarioRun> => {
      const response = await agentAPIClient.agentFetch(tenantId, 'post', '/api/v2/evals/scenarios/{scenario_id}/runs', {
        params: { path: { scenario_id: scenarioId } },
        body,
        errorMsg: 'Failed to create scenario run',
      });
      if (!response.success) {
        throw new Error(response.message);
      }
      return response.data;
    },
    onSuccess: async (_data, { tenantId, scenarioId }) => {
      await queryClient.invalidateQueries({ queryKey: ['scenario-run-latest', tenantId, scenarioId] });
    },
  });
};

export const usePollScenarioRun = () => {
  const { agentAPIClient } = useRouteContext({ from: '/tenants/$tenantId' });
  const queryClient = useQueryClient();

  const pollForCompletion = useCallback(
    async (scenarioId: string, tenantId: string): Promise<void> => {
      for (let attempt = 0; attempt < MAX_POLLING_ATTEMPTS; attempt++) {
        if (attempt > 0) {
          await new Promise((resolve) => setTimeout(resolve, POLLING_INTERVAL));
        }

        try {
          const response = await agentAPIClient.agentFetch(
            tenantId,
            'get',
            '/api/v2/evals/scenarios/{scenario_id}/runs/latest',
            {
              params: { path: { scenario_id: scenarioId } },
              silent: true,
            },
          );

          if (response.success) {
            const allTrialsComplete =
              response.data.trials?.every((trial) => trial.status === 'COMPLETED' || trial.status === 'ERROR') ?? false;

            const completedTrialsHaveResults =
              response.data.trials?.every((trial) => {
                if (trial.status !== 'COMPLETED' && trial.status !== 'ERROR') return true; // Skip non termianl states
                return trial.evaluation_results && trial.evaluation_results.length > 0;
              }) ?? false;

            if (allTrialsComplete && completedTrialsHaveResults) {
              await queryClient.invalidateQueries({ queryKey: ['scenario-run-latest', tenantId, scenarioId] });
              return;
            }
          }
        } catch {
          // Polling attempt failed, retry
        }
      }

      throw new Error('Trial execution timed out after 60 seconds');
    },
    [agentAPIClient, queryClient],
  );

  return { pollForCompletion };
};

export const useSuggestScenarioMutation = () => {
  const { agentAPIClient } = useRouteContext({ from: '/tenants/$tenantId' });
  return useMutation({
    mutationFn: async ({
      tenantId,
      body,
    }: {
      tenantId: string;
      body: SuggestScenarioPayload;
    }): Promise<ScenarioSuggestion> => {
      const response = await agentAPIClient.agentFetch(tenantId, 'post', '/api/v2/evals/scenarios/suggest', {
        body,
        errorMsg: 'Failed to generate scenario suggestion',
      });
      if (!response.success) {
        throw new Error(response.message);
      }
      return response.data;
    },
  });
};
