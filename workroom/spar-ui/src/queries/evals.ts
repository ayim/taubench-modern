import { useCallback } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import type { components, paths } from '@sema4ai/agent-server-interface';
import { createSparQuery, createSparQueryOptions, createSparMutation } from './shared';
import { useSparUIContext } from '../api/context';

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

const getListScenariosQueryKey = ({ agentId, limit }: { agentId: string; limit?: number }) => [
  'scenarios',
  agentId,
  limit ?? 0,
];
const getScenarioQueryKey = ({ scenarioId }: { scenarioId: string }) => ['scenario', scenarioId];
const getLatestScenarioRunQueryKey = ({ scenarioId }: { scenarioId: string }) => [
  'scenario-run-latest',
  scenarioId,
];
const getScenarioRunsQueryKey = ({ scenarioId, limit }: { scenarioId: string; limit?: number }) => [
  'scenario-runs',
  scenarioId,
  limit ?? 0,
];
const getScenarioRunQueryKey = ({ scenarioId, scenarioRunId }: { scenarioId: string; scenarioRunId: string }) => [
  'scenario-run',
  scenarioId,
  scenarioRunId,
];

export const listScenariosQueryOptions = createSparQueryOptions<{
  agentId: string;
  limit?: number;
}>()(({ sparAPIClient, agentId, limit }) => ({
  queryKey: getListScenariosQueryKey({ agentId, limit }),
  queryFn: async (): Promise<ListScenariosResponse> => {
    const response = await sparAPIClient.queryAgentServer('get', '/api/v2/evals/scenarios', {
      params: {
        query: {
          ...(agentId && { agent_id: agentId }),
          ...(limit && { limit }),
        },
      },
    });
    if (!response.success) {
      throw new Error(response.message);
    }
    return response.data;
  },
}));

export const scenarioQueryOptions = createSparQueryOptions<{
  scenarioId: string;
}>()(({ sparAPIClient, scenarioId }) => ({
  queryKey: getScenarioQueryKey({ scenarioId }),
  queryFn: async (): Promise<Scenario> => {
    const response = await sparAPIClient.queryAgentServer('get', '/api/v2/evals/scenarios/{scenario_id}', {
      params: { path: { scenario_id: scenarioId } },
    });
    if (!response.success) {
      throw new Error(response.message);
    }
    return response.data;
  },
}));

export const latestScenarioRunQueryOptions = createSparQueryOptions<{
  scenarioId: string;
}>()(({ sparAPIClient, scenarioId }) => ({
  queryKey: getLatestScenarioRunQueryKey({ scenarioId }),
  queryFn: async (): Promise<ScenarioRun | null> => {
    const response = await sparAPIClient.queryAgentServer(
      'get',
      '/api/v2/evals/scenarios/{scenario_id}/runs/latest',
      {
        params: { path: { scenario_id: scenarioId } },
      },
    );
    if (!response.success) {
      throw new Error(response.message);
    }
    return response.data;
  },
}));

export const scenarioRunsQueryOptions = createSparQueryOptions<{
  scenarioId: string;
  limit?: number;
}>()(({ sparAPIClient, scenarioId, limit }) => ({
  queryKey: getScenarioRunsQueryKey({ scenarioId, limit }),
  queryFn: async (): Promise<ScenarioRun[]> => {
    const response = await sparAPIClient.queryAgentServer(
      'get',
      '/api/v2/evals/scenarios/{scenario_id}/runs',
      {
        params: { 
          path: { scenario_id: scenarioId },
          ...(limit && { query: { limit } }),
        },
      },
    );
    if (!response.success) {
      throw new Error(response.message);
    }
    return response.data;
  },
}));

export const scenarioRunQueryOptions = createSparQueryOptions<{
  scenarioId: string;
  scenarioRunId: string;
}>()(({ sparAPIClient, scenarioId, scenarioRunId }) => ({
  queryKey: getScenarioRunQueryKey({ scenarioId, scenarioRunId }),
  queryFn: async (): Promise<ScenarioRun> => {
    const response = await sparAPIClient.queryAgentServer(
      'get',
      '/api/v2/evals/scenarios/{scenario_id}/runs/{scenario_run_id}',
      {
        params: { 
          path: { 
            scenario_id: scenarioId,
            scenario_run_id: scenarioRunId 
          } 
        },
      },
    );
    if (!response.success) {
      throw new Error(response.message);
    }
    return response.data;
  },
}));

export const useListScenariosQuery = createSparQuery(listScenariosQueryOptions);
export const useScenarioQuery = createSparQuery(scenarioQueryOptions);
export const useLatestScenarioRunQuery = createSparQuery(latestScenarioRunQueryOptions);
export const useScenarioRunsQuery = createSparQuery(scenarioRunsQueryOptions);
export const useScenarioRunQuery = createSparQuery(scenarioRunQueryOptions);

export const useCreateScenarioMutation = createSparMutation<Record<string, never>, { body: CreateScenarioPayload }>()(
  ({ sparAPIClient, queryClient }) => ({
    mutationFn: async ({ body }): Promise<Scenario> => {
      const response = await sparAPIClient.queryAgentServer('post', '/api/v2/evals/scenarios', {
        body,
      });
      if (!response.success) {
        throw new Error(response.message);
      }
      return response.data;
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['scenarios'] });
    },
  }),
);

export const useDeleteScenarioMutation = createSparMutation<Record<string, never>, { scenarioId: string }>()(
  ({ sparAPIClient, queryClient }) => ({
    mutationFn: async ({ scenarioId }): Promise<Scenario> => {
      const response = await sparAPIClient.queryAgentServer('delete', '/api/v2/evals/scenarios/{scenario_id}', {
        params: { path: { scenario_id: scenarioId } },
      });
      if (!response.success) {
        throw new Error(response.message);
      }
      return response.data;
    },
    onSuccess: async (_data, { scenarioId }) => {
      await queryClient.invalidateQueries({ queryKey: ['scenarios'] });
      await queryClient.invalidateQueries({ queryKey: ['scenario', scenarioId] });
    },
  }),
);

export const useCreateScenarioRunMutation = createSparMutation<
  Record<string, never>,
  { scenarioId: string; body: CreateScenarioRunPayload }
>()(({ sparAPIClient, queryClient }) => ({
  mutationFn: async ({ scenarioId, body }): Promise<ScenarioRun> => {
    const response = await sparAPIClient.queryAgentServer('post', '/api/v2/evals/scenarios/{scenario_id}/runs', {
      params: { path: { scenario_id: scenarioId } },
      body,
    });
    if (!response.success) {
      throw new Error(response.message);
    }
    return response.data;
  },
  onSuccess: async (_data, { scenarioId }) => {
    await queryClient.invalidateQueries({ queryKey: ['scenario-run-latest', scenarioId] });
    await queryClient.invalidateQueries({ queryKey: ['scenario-runs', scenarioId] });
  },
}));

export const useSuggestScenarioMutation = createSparMutation<Record<string, never>, { body: SuggestScenarioPayload }>()(
  ({ sparAPIClient }) => ({
    mutationFn: async ({ body }): Promise<ScenarioSuggestion> => {
      const response = await sparAPIClient.queryAgentServer('post', '/api/v2/evals/scenarios/suggest', {
        body,
      });
      if (!response.success) {
        throw new Error(response.message);
      }
      return response.data;
    },
  }),
);

export const useCancelScenarioRunMutation = createSparMutation<
  Record<string, never>,
  { scenarioId: string; scenarioRunId: string }
>()(({ sparAPIClient, queryClient }) => ({
  mutationFn: async ({ scenarioId, scenarioRunId }): Promise<null> => {
    const response = await sparAPIClient.queryAgentServer(
      'delete',
      '/api/v2/evals/scenarios/{scenario_id}/runs/{scenario_run_id}',
      {
        params: { 
          path: { 
            scenario_id: scenarioId,
            scenario_run_id: scenarioRunId 
          } 
        },
      },
    );
    if (!response.success) {
      throw new Error(response.message);
    }
    return null;
  },
  onSuccess: async (_data, { scenarioId, scenarioRunId }) => {
    await queryClient.invalidateQueries({ queryKey: ['scenario-run', scenarioId, scenarioRunId] });
    await queryClient.invalidateQueries({ queryKey: ['scenario-run-latest', scenarioId] });
  },
}));

export const usePollScenarioRun = () => {
  const { sparAPIClient } = useSparUIContext();
  const queryClient = useQueryClient();

  const pollForCompletion = useCallback(
    async (scenarioId: string): Promise<void> => {
      const poll = async (attempt: number): Promise<void> => {
        if (attempt >= MAX_POLLING_ATTEMPTS) {
          throw new Error('Trial execution timed out after 60 seconds');
        }

        if (attempt > 0) {
          await new Promise<void>((resolve) => {
            setTimeout(() => resolve(), POLLING_INTERVAL);
          });
        }

        try {
          const response = await sparAPIClient.queryAgentServer(
            'get',
            '/api/v2/evals/scenarios/{scenario_id}/runs/latest',
            {
              params: { path: { scenario_id: scenarioId } },
            },
          );

          if (response.success) {
            const allTrialsComplete =
              response.data.trials?.every((trial) => trial.status === 'COMPLETED' || trial.status === 'ERROR') ??
              false;

            const completedTrialsHaveResults =
              response.data.trials?.every((trial) => {
                if (trial.status !== 'COMPLETED' && trial.status !== 'ERROR') return true; // Skip non terminal states
                return trial.evaluation_results && trial.evaluation_results.length > 0;
              }) ?? false;

            if (allTrialsComplete && completedTrialsHaveResults) {
              await queryClient.invalidateQueries({ queryKey: ['scenario-run-latest', scenarioId] });
              await queryClient.invalidateQueries({ queryKey: ['scenario-runs', scenarioId] });
              return;
            }
          }
        } catch {
          // Polling attempt failed, retry.
        }

        await poll(attempt + 1);
      };

      return poll(0);
    },
    [sparAPIClient, queryClient],
  );

  return { pollForCompletion };
};
