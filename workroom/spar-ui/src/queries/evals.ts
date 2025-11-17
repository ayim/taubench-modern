import { useCallback } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import type { components, paths } from '@sema4ai/agent-server-interface';
import { createSparQuery, createSparQueryOptions, createSparMutation, QueryError, ResourceType } from './shared';
import { useSparUIContext } from '../api/context';

type ListScenariosResponse = paths['/api/v2/evals/scenarios']['get']['responses']['200']['content']['application/json'];
export type Scenario = components['schemas']['Scenario'];
type CreateScenarioPayload = components['schemas']['CreateScenarioPayload'];
type UpdateScenarioPayload = {
  name: string;
  description: string;
  tool_execution_mode?: 'replay' | 'live';
  evaluation_criteria?: (
    | components['schemas']['ActionCalling']
    | components['schemas']['FlowAdherence']
    | components['schemas']['ResponseAccuracy']
  )[];
};
type CreateScenarioRunPayload = components['schemas']['CreateScenarioRunPayload'];
type SuggestScenarioPayload =
  paths['/api/v2/evals/scenarios/suggest']['post']['requestBody']['content']['application/json'];
export type ScenarioSuggestion = components['schemas']['ScenarioSuggestion'];
export type Trial = components['schemas']['Trial'];
type ScenarioRun = components['schemas']['ScenarioRun'];
export type ScenarioBatchRunStatus = 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'CANCELED';
export interface ScenarioBatchRunStatistics {
  total_scenarios: number;
  completed_scenarios: number;
  failed_scenarios: number;
  total_trials: number;
  completed_trials: number;
  failed_trials: number;
  evaluation_totals: Record<
    string,
    {
      total: number;
      passed: number;
    }
  >;
}

export interface ScenarioBatchRun {
  batch_run_id: string;
  agent_id: string;
  user_id: string;
  scenario_ids: string[];
  status: ScenarioBatchRunStatus;
  statistics: ScenarioBatchRunStatistics;
  created_at: string;
  updated_at: string;
  completed_at?: string | null;
}

const POLLING_INTERVAL = 2000;
const TERMINAL_TRIAL_STATUSES: Trial['status'][] = ['COMPLETED', 'ERROR', 'CANCELED'];

const hasRunEvaluationsCompleted = (trial: Trial): boolean => {
  const executionFinishedAt = trial.execution_state?.finished_at ?? null;
  const statusUpdatedAt = trial.status_updated_at ?? trial.updated_at ?? null;

  if (!executionFinishedAt || !statusUpdatedAt) {
    return false;
  }

  const executionFinishedTimestamp = new Date(executionFinishedAt).getTime();
  const statusUpdatedTimestamp = new Date(statusUpdatedAt).getTime();

  if (Number.isNaN(executionFinishedTimestamp) || Number.isNaN(statusUpdatedTimestamp)) {
    return false;
  }

  return statusUpdatedTimestamp >= executionFinishedTimestamp;
};
const TERMINAL_BATCH_STATUSES: ScenarioBatchRunStatus[] = ['COMPLETED', 'FAILED', 'CANCELED'];

const getListScenariosQueryKey = ({ agentId, limit }: { agentId: string; limit?: number }) => [
  'scenarios',
  agentId,
  limit ?? 0,
];
const getScenarioQueryKey = ({ scenarioId }: { scenarioId: string }) => ['scenario', scenarioId];
const getLatestScenarioRunQueryKey = ({ scenarioId }: { scenarioId: string }) => ['scenario-run-latest', scenarioId];
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
const getBatchRunQueryKey = ({ agentId, batchRunId }: { agentId: string; batchRunId: string }) => [
  'scenario-batch-run',
  agentId,
  batchRunId,
];
const getLatestBatchRunQueryKey = ({ agentId }: { agentId: string }) => ['scenario-batch-run-latest', agentId];

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
      throw new QueryError(response.message, { code: response.code, resource: ResourceType.Evaluation });
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
      throw new QueryError(response.message, { code: response.code, resource: ResourceType.Evaluation });
    }
    return response.data;
  },
}));

export const latestScenarioRunQueryOptions = createSparQueryOptions<{
  scenarioId: string;
}>()(({ sparAPIClient, scenarioId }) => ({
  queryKey: getLatestScenarioRunQueryKey({ scenarioId }),
  queryFn: async (): Promise<ScenarioRun | null> => {
    const response = await sparAPIClient.queryAgentServer('get', '/api/v2/evals/scenarios/{scenario_id}/runs/latest', {
      params: { path: { scenario_id: scenarioId } },
    });
    if (!response.success) {
      throw new QueryError(response.message, { code: response.code, resource: ResourceType.Evaluation });
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
    const response = await sparAPIClient.queryAgentServer('get', '/api/v2/evals/scenarios/{scenario_id}/runs', {
      params: {
        path: { scenario_id: scenarioId },
        ...(limit && { query: { limit } }),
      },
    });
    if (!response.success) {
      throw new QueryError(response.message, { code: response.code, resource: ResourceType.Evaluation });
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
            scenario_run_id: scenarioRunId,
          },
        },
      },
    );
    if (!response.success) {
      throw new QueryError(response.message, { code: response.code, resource: ResourceType.Evaluation });
    }
    return response.data;
  },
}));

export const latestBatchRunQueryOptions = createSparQueryOptions<{
  agentId: string;
}>()(({ sparAPIClient, agentId }) => ({
  queryKey: getLatestBatchRunQueryKey({ agentId }),
  queryFn: async (): Promise<ScenarioBatchRun | null> => {
    const response = await sparAPIClient.queryAgentServer('get', '/api/v2/evals/agents/{agent_id}/batches/latest', {
      params: { path: { agent_id: agentId } },
    });

    if (!response.success) {
      if (response.code === 'not_found') {
        return null;
      }
      throw new QueryError(response.message, { code: response.code, resource: ResourceType.Evaluation });
    }

    return response.data as ScenarioBatchRun;
  },
}));

export const useListScenariosQuery = createSparQuery(listScenariosQueryOptions);
export const useScenarioQuery = createSparQuery(scenarioQueryOptions);
export const useLatestScenarioRunQuery = createSparQuery(latestScenarioRunQueryOptions);
export const useScenarioRunsQuery = createSparQuery(scenarioRunsQueryOptions);
export const useScenarioRunQuery = createSparQuery(scenarioRunQueryOptions);
export const useLatestBatchRunQuery = createSparQuery(latestBatchRunQueryOptions);

export const useCreateScenarioMutation = createSparMutation<Record<string, never>, { body: CreateScenarioPayload }>()(
  ({ sparAPIClient, queryClient }) => ({
    mutationFn: async ({ body }): Promise<Scenario> => {
      const response = await sparAPIClient.queryAgentServer('post', '/api/v2/evals/scenarios', {
        body,
      });
      if (!response.success) {
        throw new QueryError(response.message, { code: response.code, resource: ResourceType.Evaluation });
      }
      return response.data;
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['scenarios'] });
    },
  }),
);

export const useUpdateScenarioMutation = createSparMutation<
  Record<string, never>,
  { scenarioId: string; body: UpdateScenarioPayload }
>()(({ sparAPIClient, queryClient }) => ({
  mutationFn: async ({ scenarioId, body }): Promise<Scenario> => {
    const response = await sparAPIClient.queryAgentServer('patch', '/api/v2/evals/scenarios/{scenario_id}', {
      params: { path: { scenario_id: scenarioId } },
      body,
    });
    if (!response.success) {
      throw new QueryError(response.message, { code: response.code, resource: ResourceType.Evaluation });
    }
    return response.data;
  },
  onSuccess: async (_data, { scenarioId }) => {
    await queryClient.invalidateQueries({ queryKey: ['scenarios'] });
    await queryClient.invalidateQueries({ queryKey: ['scenario', scenarioId] });
  },
}));

export const useDeleteScenarioMutation = createSparMutation<Record<string, never>, { scenarioId: string }>()(
  ({ sparAPIClient, queryClient }) => ({
    mutationFn: async ({ scenarioId }): Promise<Scenario> => {
      const response = await sparAPIClient.queryAgentServer('delete', '/api/v2/evals/scenarios/{scenario_id}', {
        params: { path: { scenario_id: scenarioId } },
      });
      if (!response.success) {
        throw new QueryError(response.message, { code: response.code, resource: ResourceType.Evaluation });
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
      throw new QueryError(response.message, { code: response.code, resource: ResourceType.Evaluation });
    }
    return response.data;
  },
  onSuccess: async (_data, { scenarioId }) => {
    await queryClient.invalidateQueries({ queryKey: ['scenario-run-latest', scenarioId] });
    await queryClient.invalidateQueries({ queryKey: ['scenario-runs', scenarioId] });
  },
}));

export const useCreateBatchRunMutation = createSparMutation<
  Record<string, never>,
  { agentId: string; body: { num_trials: number } }
>()(({ sparAPIClient }) => ({
  mutationFn: async ({ agentId, body }): Promise<ScenarioBatchRun> => {
    const response = await sparAPIClient.queryAgentServer('post', '/api/v2/evals/agents/{agent_id}/batches', {
      params: { path: { agent_id: agentId } },
      body,
    });
    if (!response.success) {
      throw new QueryError(response.message, { code: response.code, resource: ResourceType.Evaluation });
    }
    return response.data as ScenarioBatchRun;
  },
}));

export const useSuggestScenarioMutation = createSparMutation<Record<string, never>, { body: SuggestScenarioPayload }>()(
  ({ sparAPIClient }) => ({
    mutationFn: async ({ body }): Promise<ScenarioSuggestion> => {
      const response = await sparAPIClient.queryAgentServer('post', '/api/v2/evals/scenarios/suggest', {
        body,
      });
      if (!response.success) {
        throw new QueryError(response.message, { code: response.code, resource: ResourceType.Evaluation });
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
            scenario_run_id: scenarioRunId,
          },
        },
      },
    );
    if (!response.success) {
      throw new QueryError(response.message, { code: response.code, resource: ResourceType.Evaluation });
    }
    return null;
  },
  onSuccess: async (_data, { scenarioId, scenarioRunId }) => {
    await queryClient.invalidateQueries({ queryKey: ['scenario-run', scenarioId, scenarioRunId] });
    await queryClient.invalidateQueries({ queryKey: ['scenario-run-latest', scenarioId] });
  },
}));

export const useExportScenariosMutation = createSparMutation<Record<string, never>, { agentId: string }>()(
  ({ sparAPIClient }) => ({
    mutationFn: async ({ agentId }): Promise<{ blob: Blob; filename: string }> => {
      const response = await sparAPIClient.queryAgentServer('get', '/api/v2/evals/scenarios/export', {
        params: { query: { agent_id: agentId } },
        parseAs: 'stream',
      });

      if (!response.success) {
        throw new QueryError(response.message, { code: response.code, resource: ResourceType.Evaluation });
      }

      const stream = response.data as ReadableStream<Uint8Array> | null | undefined;
      const reader = stream?.getReader?.();

      if (!reader) {
        throw new QueryError('Failed to prepare scenarios archive for download', {
          code: 'unexpected',
          resource: ResourceType.Evaluation,
        });
      }

      const chunks: BlobPart[] = [];
      let done = false;

      while (!done) {
        // eslint-disable-next-line no-await-in-loop
        const { value, done: streamDone } = await reader.read();
        if (value) {
          const chunk = value.buffer.slice(value.byteOffset, value.byteOffset + value.byteLength) as ArrayBuffer;
          chunks.push(chunk);
        }
        done = streamDone ?? false;
      }

      const blob = new Blob(chunks, { type: 'application/zip' });

      const sanitize = (value: string, fallback: string) => {
        const sanitized = value.replace(/[^A-Za-z0-9_.-]/g, '_');
        return sanitized || fallback;
      };

      const isoTimestamp = new Date().toISOString();
      const timestamp = isoTimestamp.replace(/[-:]/g, '').replace(/\.\d+Z$/, 'Z');
      const filename = `agent_${sanitize(agentId, 'agent')}_scenarios_${timestamp}.zip`;

      return { blob, filename };
    },
  }),
);

export const useImportScenariosMutation = createSparMutation<Record<string, never>, { agentId: string; file: File }>()(
  ({ sparAPIClient, queryClient }) => ({
    mutationFn: async ({ agentId, file }): Promise<Scenario[]> => {
      const response = await sparAPIClient.queryAgentServer('post', '/api/v2/evals/scenarios/import', {
        params: { query: { agent_id: agentId } },
        body: { file } as never,
        bodySerializer(body: { file: string }) {
          const formData = new FormData();
          formData.append('file', body.file);
          return formData;
        },
      });

      if (!response.success) {
        throw new QueryError(response.message || 'Failed to import scenarios', {
          code: response.code,
          resource: ResourceType.Evaluation,
        });
      }

      return response.data as Scenario[];
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['scenarios'] });
    },
  }),
);

export const usePollScenarioRun = () => {
  const { sparAPIClient } = useSparUIContext();
  const queryClient = useQueryClient();

  const pollForCompletion = useCallback(
    async (scenarioId: string): Promise<ScenarioRun | null> => {
      const poll = async (attempt: number): Promise<ScenarioRun | null> => {
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
            queryClient.setQueryData(['scenario-run-latest', scenarioId], response.data);

            const trials = response.data.trials ?? [];
            const hasTrials = trials.length > 0;

            const allTrialsComplete = hasTrials
              ? trials.every((trial) => TERMINAL_TRIAL_STATUSES.includes(trial.status))
              : false;

            const allTrialsEvaluated = hasTrials ? trials.every((trial) => hasRunEvaluationsCompleted(trial)) : false;

            const allTrialsCanceled = hasTrials ? trials.every((trial) => trial.status === 'CANCELED') : false;

            if (allTrialsComplete && (allTrialsEvaluated || allTrialsCanceled)) {
              await queryClient.invalidateQueries({ queryKey: ['scenario-run-latest', scenarioId] });
              await queryClient.invalidateQueries({ queryKey: ['scenario-runs', scenarioId] });

              return response.data;
            }
          }
        } catch {
          // Polling attempt failed, retry.
        }

        return poll(attempt + 1);
      };

      return poll(0);
    },
    [sparAPIClient, queryClient],
  );

  return { pollForCompletion };
};

export const usePollBatchRun = () => {
  const { sparAPIClient } = useSparUIContext();
  const queryClient = useQueryClient();

  const pollBatchRun = useCallback(
    async ({ agentId, batchRunId }: { agentId: string; batchRunId: string }): Promise<ScenarioBatchRun | null> => {
      const poll = async (attempt: number): Promise<ScenarioBatchRun | null> => {
        if (attempt > 0) {
          await new Promise<void>((resolve) => {
            setTimeout(() => resolve(), POLLING_INTERVAL);
          });
        }

        try {
          const response = await sparAPIClient.queryAgentServer(
            'get',
            '/api/v2/evals/agents/{agent_id}/batches/{batch_run_id}',
            {
              params: { path: { agent_id: agentId, batch_run_id: batchRunId } },
            },
          );

          if (response.success) {
            const batchRun = response.data as ScenarioBatchRun;
            queryClient.setQueryData(getBatchRunQueryKey({ agentId, batchRunId }), batchRun);
            if (TERMINAL_BATCH_STATUSES.includes(batchRun.status)) {
              await queryClient.invalidateQueries({ queryKey: getBatchRunQueryKey({ agentId, batchRunId }) });
              return batchRun;
            }
          }
        } catch {
          // retry
        }

        return poll(attempt + 1);
      };

      return poll(0);
    },
    [sparAPIClient, queryClient],
  );

  return { pollBatchRun };
};
