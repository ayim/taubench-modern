import { useMemo, useEffect, useRef, useCallback, useState, type Dispatch, type SetStateAction } from 'react';
import { useQueries, useQueryClient } from '@tanstack/react-query';
import { useSnackbar } from '@sema4ai/components';
import type { components } from '@sema4ai/agent-server-interface';
import {
  latestScenarioRunQueryOptions,
  scenarioRunsQueryOptions,
  scenarioRunQueryOptions,
  useCreateScenarioMutation,
  useCreateScenarioRunMutation,
  useCreateBatchRunMutation,
  useDeleteScenarioMutation,
  useListScenariosQuery,
  usePollScenarioRun,
  usePollBatchRun,
  useLatestBatchRunQuery,
  useSuggestScenarioMutation,
  useCancelScenarioRunMutation,
  useCancelBatchRunMutation,
  useExportScenariosMutation,
  useImportScenariosMutation,
  useUpdateScenarioMutation,
} from '../../../../../queries/evals';
import type {
  ScenarioBatchRun,
  ScenarioBatchRunMetadata,
  ScenarioBatchRunStatus,
  ScenarioBatchRunTrialStatus,
} from '../../../../../queries/evals';
import { useAgentQuery } from '../../../../../queries/agents';
import { useSparUIContext } from '../../../../../api/context';
import { sortByCreatedAtDesc } from '../../../../../lib/utils';
import type { CreateEvalFormData } from '../components/CreateEvalDialog';
import type { BatchSummary, EvaluationItem, ScenarioRun, Scenario, Trial } from '../types';
import { useAnalytics } from '../../../../../queries';

export interface UseEvalSidebarDataProps {
  agentId: string;
  threadId: string;
  selectedRunIndices: Map<string, number>;
  setSelectedRunIndices: (value: Map<string, number> | ((prev: Map<string, number>) => Map<string, number>)) => void;
  expandResults: (scenarioId: string) => void;
  expandedResults: Set<string>;
  setLastBatchSummary: Dispatch<SetStateAction<BatchSummary | null>>;
  setBatchSummaryOutdated: Dispatch<SetStateAction<boolean>>;
}

type EvaluationCriterionConfig =
  | components['schemas']['ActionCalling']
  | components['schemas']['FlowAdherence']
  | components['schemas']['ResponseAccuracy'];

const TERMINAL_BATCH_STATUSES: ScenarioBatchRunStatus[] = ['COMPLETED', 'FAILED', 'CANCELED'];
const TERMINAL_TRIAL_STATUSES: Trial['status'][] = ['COMPLETED', 'ERROR', 'CANCELED'];

type BatchScenarioState = {
  runStartedAt: number | null;
  scenarioRunId?: string;
};

export const useEvalSidebarData = ({
  agentId,
  threadId,
  selectedRunIndices,
  setSelectedRunIndices,
  expandResults,
  expandedResults,
  setLastBatchSummary,
  setBatchSummaryOutdated,
}: UseEvalSidebarDataProps) => {
  const { sparAPIClient } = useSparUIContext();
  const { track } = useAnalytics();
  const queryClient = useQueryClient();
  const { addSnackbar } = useSnackbar();
  const [isCancelingAll, setIsCancelingAll] = useState(false);
  const [isDeletingAll, setIsDeletingAll] = useState(false);
  const batchScenarioTrackingRef = useRef<Map<string, BatchScenarioState>>(new Map());
  const processedBatchScenarioRunsRef = useRef<Set<string>>(new Set());
  const batchTrialStatusRef = useRef<Map<string, Map<string, Trial['status']>>>(new Map());
  const batchPollingRunIdRef = useRef<string | null>(null);
  const batchPollingPromiseRef = useRef<Promise<ScenarioBatchRun | null> | null>(null);

  const deleteScenarioMutation = useDeleteScenarioMutation({});
  const createScenarioRunMutation = useCreateScenarioRunMutation({});
  const createBatchRunMutation = useCreateBatchRunMutation({});
  const createScenarioMutation = useCreateScenarioMutation({});
  const updateScenarioMutation = useUpdateScenarioMutation({});
  const suggestScenarioMutation = useSuggestScenarioMutation({});
  const cancelScenarioRunMutation = useCancelScenarioRunMutation({});
  const cancelBatchRunMutation = useCancelBatchRunMutation({});
  const exportScenariosMutation = useExportScenariosMutation({});
  const importScenariosMutation = useImportScenariosMutation({});
  const { pollForCompletion } = usePollScenarioRun();
  const { pollBatchRun } = usePollBatchRun();

  const { data: scenarios = [], isLoading: scenariosLoading } = useListScenariosQuery({
    agentId,
  });
  const { data: latestBatchRun } = useLatestBatchRunQuery({ agentId });
  const { data: agent } = useAgentQuery({ agentId });
  const scenarioMap = useMemo(
    () => new Map(scenarios.map((scenario) => [scenario.scenario_id, scenario])),
    [scenarios],
  );
  const buildBatchSummary = useCallback((batchRun: ScenarioBatchRun, fallbackNumTrials?: number): BatchSummary => {
    const totalScenarios = batchRun.statistics.total_scenarios ?? 0;
    const totalTrials = batchRun.statistics.total_trials ?? 0;
    const inferredNumTrials =
      fallbackNumTrials ??
      (totalScenarios > 0 ? Math.max(1, Math.round(totalTrials / Math.max(totalScenarios, 1))) : 1);
    const metadata: ScenarioBatchRunMetadata | null = batchRun.metadata ?? null;

    return {
      batchRunId: batchRun.batch_run_id,
      createdAt: batchRun.created_at,
      status: batchRun.status,
      statistics: batchRun.statistics,
      numTrials: inferredNumTrials,
      metadata,
    };
  }, []);
  useEffect(() => {
    if (latestBatchRun === undefined) {
      return;
    }
    if (latestBatchRun === null) {
      setLastBatchSummary(null);
      setBatchSummaryOutdated(false);
      return;
    }

    setLastBatchSummary((prev) => {
      const newSummary = buildBatchSummary(latestBatchRun, prev?.numTrials);

      if (prev && prev.batchRunId !== latestBatchRun.batch_run_id) {
        const completedTrials =
          (newSummary.statistics.completed_trials ?? 0) + (newSummary.statistics.failed_trials ?? 0);
        if (completedTrials === 0) {
          return prev;
        }
      }

      return newSummary;
    });
    setBatchSummaryOutdated(false);
  }, [latestBatchRun, setLastBatchSummary, buildBatchSummary, setBatchSummaryOutdated]);

  const computeTrackedDuration = useCallback(
    (trials: ScenarioBatchRunTrialStatus['trials'], runStartedAt: number | null): number | null => {
      if (trials.length > 0) {
        const largestInterval = trials.reduce<number | null>((currentMax, trial) => {
          const startedAt = trial.execution_started_at;
          const finishedAt = trial.execution_finished_at;

          if (!startedAt || !finishedAt) {
            return currentMax;
          }

          const startTimestamp = new Date(startedAt).getTime();
          const endTimestamp = new Date(finishedAt).getTime();

          if (Number.isNaN(startTimestamp) || Number.isNaN(endTimestamp) || endTimestamp < startTimestamp) {
            return currentMax;
          }

          const interval = endTimestamp - startTimestamp;
          if (currentMax === null || interval > currentMax) {
            return interval;
          }
          return currentMax;
        }, null);

        if (largestInterval !== null) {
          return largestInterval;
        }
      }

      if (runStartedAt !== null && typeof performance !== 'undefined') {
        return Math.max(Math.round(performance.now() - runStartedAt), 0);
      }

      return null;
    },
    [],
  );

  const handleScenarioCompletionFromBatch = useCallback(
    (trialStatus: ScenarioBatchRunTrialStatus, runStartedAt: number | null) => {
      const trials = trialStatus.trials ?? [];
      const trackedDurationMs = computeTrackedDuration(trials, runStartedAt);

      if (trackedDurationMs !== null) {
        track(
          `scenario_${trialStatus.scenario_id}.run_${trialStatus.scenario_run_id}.duration`,
          trackedDurationMs.toString(),
        );
      }

      queryClient.invalidateQueries({ queryKey: ['scenario-run-latest', trialStatus.scenario_id] });
      queryClient.invalidateQueries({ queryKey: ['scenario-runs', trialStatus.scenario_id] });
      queryClient.invalidateQueries({ queryKey: ['threads', agentId] });
    },
    [agentId, computeTrackedDuration, queryClient, track],
  );

  const handleBatchProgress = useCallback(
    (batchRun: ScenarioBatchRun) => {
      const statuses = batchRun.trial_statuses ?? [];
      statuses.forEach((status) => {
        if (processedBatchScenarioRunsRef.current.has(status.scenario_run_id)) {
          return;
        }

        const existingState = batchScenarioTrackingRef.current.get(status.scenario_id);

        const mergedState: BatchScenarioState = {
          runStartedAt: existingState?.runStartedAt ?? null,
          scenarioRunId: status.scenario_run_id,
        };

        batchScenarioTrackingRef.current.set(status.scenario_id, mergedState);

        const trials = status.trials ?? [];
        const allTerminal =
          trials.length > 0 && trials.every((trial) => TERMINAL_TRIAL_STATUSES.includes(trial.status));

        let trialStatusChanged = false;
        const existingTrialStatuses = batchTrialStatusRef.current.get(status.scenario_run_id) ?? new Map();
        const nextTrialStatuses = new Map(existingTrialStatuses);
        trials.forEach((trial) => {
          const previousStatus = existingTrialStatuses.get(trial.trial_id);
          if (previousStatus !== trial.status) {
            trialStatusChanged = true;
          }
          nextTrialStatuses.set(trial.trial_id, trial.status);
        });

        if (!allTerminal && trialStatusChanged) {
          queryClient.invalidateQueries({ queryKey: ['scenario-run-latest', status.scenario_id] });
        }
        batchTrialStatusRef.current.set(status.scenario_run_id, nextTrialStatuses);

        if (allTerminal) {
          processedBatchScenarioRunsRef.current.add(status.scenario_run_id);
          batchScenarioTrackingRef.current.delete(status.scenario_id);
          batchTrialStatusRef.current.delete(status.scenario_run_id);
          handleScenarioCompletionFromBatch(status, mergedState.runStartedAt);
        }
      });
    },
    [handleScenarioCompletionFromBatch, queryClient],
  );

  const initializeBatchScenarioTracking = useCallback(
    (scenarioIds: string[], runStartedAtMap?: Map<string, number | null>) => {
      scenarioIds.forEach((scenarioId) => {
        const existing = batchScenarioTrackingRef.current.get(scenarioId);
        const runStartedAt = runStartedAtMap?.get(scenarioId) ?? existing?.runStartedAt ?? null;
        batchScenarioTrackingRef.current.set(scenarioId, {
          runStartedAt,
          scenarioRunId: existing?.scenarioRunId,
        });
      });
    },
    [],
  );

  const startBatchPolling = useCallback(
    (batchRun: ScenarioBatchRun): Promise<ScenarioBatchRun | null> | null => {
      if (!batchRun || TERMINAL_BATCH_STATUSES.includes(batchRun.status)) {
        return null;
      }

      if (batchPollingRunIdRef.current === batchRun.batch_run_id && batchPollingPromiseRef.current) {
        return batchPollingPromiseRef.current;
      }

      const promise = pollBatchRun({
        agentId,
        batchRunId: batchRun.batch_run_id,
        onUpdate: handleBatchProgress,
      }).finally(() => {
        if (batchPollingRunIdRef.current === batchRun.batch_run_id) {
          batchPollingRunIdRef.current = null;
          batchPollingPromiseRef.current = null;
        }
      });

      batchPollingRunIdRef.current = batchRun.batch_run_id;
      batchPollingPromiseRef.current = promise;
      return promise;
    },
    [agentId, handleBatchProgress, pollBatchRun],
  );

  const latestRunQueries = useQueries({
    queries: scenarios.map((scenario) =>
      latestScenarioRunQueryOptions({
        scenarioId: scenario.scenario_id,
        sparAPIClient,
      }),
    ),
  });

  const allRunsQueries = useQueries({
    queries: scenarios.map((scenario) =>
      scenarioRunsQueryOptions({
        scenarioId: scenario.scenario_id,
        sparAPIClient,
        limit: 50, // Note: hardcoded limit for safety
      }),
    ),
  });

  const latestRunsData = latestRunQueries.map((query) => query.data ?? null);
  const allRunsData = allRunsQueries.map((query) => query.data ?? null);
  const latestRunsLoading = latestRunQueries.some((query) => query.isLoading);
  const allRunsLoading = allRunsQueries.some((query) => query.isLoading);
  const loading = scenariosLoading || latestRunsLoading || allRunsLoading;

  // Effect to update selected run indices when data changes
  useEffect(() => {
    scenarios.forEach((scenario) => {
      const allRuns = allRunsData[scenarios.indexOf(scenario)] || [];
      if (allRuns.length > 0) {
        const currentIndex = selectedRunIndices.get(scenario.scenario_id);
        if (currentIndex === undefined) {
          setSelectedRunIndices((prev) => new Map(prev).set(scenario.scenario_id, 0));
        } else if (currentIndex >= allRuns.length) {
          setSelectedRunIndices((prev) => new Map(prev).set(scenario.scenario_id, 0));
        }
      }
    });
  }, [scenarios, allRunsData, selectedRunIndices, setSelectedRunIndices]);

  // Query for individual historical runs - preload based on expansion state
  const historicalRunQueries = useQueries({
    queries: scenarios.flatMap((scenario, scenarioIndex) => {
      const currentIndex = selectedRunIndices.get(scenario.scenario_id) ?? 0;
      const allRuns = allRunsData[scenarioIndex] || [];
      const isExpanded = expandedResults.has(scenario.scenario_id);

      let indicesToPreload: number[] = [];

      if (isExpanded) {
        // When expanded (menu visible), preload ALL runs for smooth menu navigation
        indicesToPreload = allRuns
          .map((_, index) => index)
          .filter(
            (index) =>
              index > 0 && // Don't preload latest run (index 0) as we already have it
              index < allRuns.length &&
              allRuns[index],
          );
      } else {
        // When collapsed, only preload adjacent runs for arrow navigation
        indicesToPreload = [currentIndex - 1, currentIndex, currentIndex + 1].filter(
          (index) =>
            index > 0 && // Don't preload latest run (index 0) as we already have it
            index < allRuns.length &&
            allRuns[index],
        );
      }

      return indicesToPreload
        .map((index) =>
          scenarioRunQueryOptions({
            scenarioId: scenario.scenario_id,
            scenarioRunId: allRuns[index]?.scenario_run_id,
            sparAPIClient,
          }),
        )
        .filter((query) => query.queryKey[2]); // Filter out any queries without valid scenario_run_id
    }),
  });

  // Map data into evaluations format (no transformations needed)
  const evaluations: EvaluationItem[] = useMemo(() => {
    return scenarios.map((scenario, index) => {
      const latestRun = latestRunsData[index];
      const allRuns = allRunsData[index] ?? [];
      const currentRunIndex = selectedRunIndices.get(scenario.scenario_id) ?? 0;

      const isRunning =
        latestRun?.trials?.some((trial) => trial.status === 'PENDING' || trial.status === 'EXECUTING') ?? false;

      // Sort runs by creation date (newest first)
      const sortedRuns = [...allRuns].sort(sortByCreatedAtDesc);

      const getCurrentRun = (): ScenarioRun | null => {
        if (currentRunIndex === 0 && latestRun) {
          return latestRun;
        }

        const targetRun = sortedRuns[currentRunIndex];
        if (!targetRun) {
          return null;
        }

        // For historical runs, try to find the corresponding individual query result
        const individualRunQuery = historicalRunQueries.find(
          (q) => q.data?.scenario_run_id === targetRun.scenario_run_id,
        );

        // Prefer detailed data from individual query if available
        // If individual query exists and has data, use it; otherwise fallback to basic run data
        return individualRunQuery?.data ?? targetRun;
      };

      return {
        scenario,
        latestRun,
        allRuns: sortedRuns,
        currentRunIndex,
        currentRun: getCurrentRun(),
        isRunning,
      };
    });
  }, [scenarios, latestRunsData, allRunsData, selectedRunIndices, historicalRunQueries, expandedResults]);

  const isAnyTestRunning = evaluations.some((evaluation) => evaluation.isRunning);
  const isBatchRunning = latestBatchRun?.status === 'RUNNING';
  const runningScenarioIds = useMemo(
    () => evaluations.filter((evaluation) => evaluation.isRunning).map(({ scenario }) => scenario.scenario_id),
    [evaluations],
  );

  // Track which scenarios we've auto-expanded to avoid expanding on every render
  const autoExpandedRef = useRef<Set<string>>(new Set());
  const pollingScenarioIdsRef = useRef<Set<string>>(new Set());
  useEffect(() => {
    if (latestBatchRun === undefined) {
      return;
    }

    if (!latestBatchRun) {
      batchScenarioTrackingRef.current.clear();
      processedBatchScenarioRunsRef.current.clear();
      return;
    }

    if (TERMINAL_BATCH_STATUSES.includes(latestBatchRun.status)) {
      batchScenarioTrackingRef.current.clear();
      processedBatchScenarioRunsRef.current.clear();
      return;
    }

    initializeBatchScenarioTracking(latestBatchRun.scenario_ids ?? []);
    handleBatchProgress(latestBatchRun);
    startBatchPolling(latestBatchRun);
  }, [latestBatchRun, initializeBatchScenarioTracking, handleBatchProgress, startBatchPolling]);

  const startScenarioPolling = useCallback(
    (
      scenarioId: string,
      {
        onSuccess,
        scenarioName,
      }: {
        onSuccess?: (completedRun: ScenarioRun | null) => void;
        scenarioName?: string;
      } = {},
    ) => {
      if (batchScenarioTrackingRef.current.has(scenarioId)) {
        return;
      }
      if (pollingScenarioIdsRef.current.has(scenarioId)) {
        return;
      }

      pollingScenarioIdsRef.current.add(scenarioId);

      pollForCompletion(scenarioId)
        .then((completedRun) => {
          onSuccess?.(completedRun);
        })
        .catch((error) => {
          queryClient.invalidateQueries({ queryKey: ['scenario-run-latest', scenarioId] });
          queryClient.invalidateQueries({ queryKey: ['scenario-runs', scenarioId] });
          addSnackbar({
            message:
              error instanceof Error
                ? error.message
                : `Failed to refresh test status${scenarioName ? ` for "${scenarioName}"` : ''}`,
            variant: 'danger',
          });
        })
        .finally(() => {
          pollingScenarioIdsRef.current.delete(scenarioId);
        });
    },
    [pollForCompletion, queryClient, addSnackbar],
  );

  // Auto-expand scenarios that are currently running (e.g., when user navigates back to sidebar)
  useEffect(() => {
    if (!loading) {
      evaluations.forEach(({ scenario, isRunning }) => {
        if (isRunning && !autoExpandedRef.current.has(scenario.scenario_id)) {
          expandResults(scenario.scenario_id);
          autoExpandedRef.current.add(scenario.scenario_id);
        }
        // Clean up tracking when test completes
        if (!isRunning && autoExpandedRef.current.has(scenario.scenario_id)) {
          autoExpandedRef.current.delete(scenario.scenario_id);
        }
      });
    }
  }, [evaluations, loading, expandResults, expandedResults]);

  // Ensure runs that are already executing keep polling even if user refreshes/navigates.
  useEffect(() => {
    if (latestBatchRun === undefined) {
      return;
    }
    runningScenarioIds.forEach((scenarioId) => {
      const managedByBatch = batchScenarioTrackingRef.current.has(scenarioId);
      if (!managedByBatch) {
        startScenarioPolling(scenarioId);
      }
    });
  }, [runningScenarioIds, startScenarioPolling, latestBatchRun]);

  const buildEvaluationCriteria = (data: CreateEvalFormData) => {
    const evaluationCriteria: EvaluationCriterionConfig[] = [];
    const expectation = data.evaluationCriteria.responseAccuracyExpectation.trim();

    if (data.useLiveExecution) {
      evaluationCriteria.push({
        type: 'response_accuracy',
        expectation,
      });
    } else {
      evaluationCriteria.push({
        type: 'action_calling',
        assert_all_consumed: true,
        allow_llm_arg_validation: false,
        allow_llm_interpolation: false,
      });
      evaluationCriteria.push({ type: 'flow_adherence' });
      if (expectation.length > 0) {
        evaluationCriteria.push({
          type: 'response_accuracy',
          expectation,
        });
      }
    }

    return evaluationCriteria;
  };

  const getScenarioExecutionMode = (scenario: Scenario): 'live' | 'replay' => {
    const metadata = (
      typeof scenario.metadata === 'object' && scenario.metadata !== null
        ? (scenario.metadata as Record<string, unknown>)
        : {}
    ) as Record<string, unknown>;
    const driftPolicyValue = metadata?.drift_policy;
    const driftPolicy =
      typeof driftPolicyValue === 'object' && driftPolicyValue !== null
        ? (driftPolicyValue as Record<string, unknown>)
        : undefined;
    const toolExecutionModeValue = driftPolicy?.tool_execution_mode;
    return toolExecutionModeValue === 'live' ? 'live' : 'replay';
  };

  const handleCreateEvaluation = async (data: CreateEvalFormData) => {
    const evaluationCriteria = buildEvaluationCriteria(data);

    await createScenarioMutation.mutateAsync({
      body: {
        name: data.name,
        description: data.description,
        thread_id: threadId,
        tool_execution_mode: data.useLiveExecution ? 'live' : undefined,
        evaluation_criteria: evaluationCriteria,
      },
    });
  };

  const handleUpdateEvaluation = async (scenarioId: string, data: CreateEvalFormData) => {
    const evaluationCriteria = buildEvaluationCriteria(data);

    await updateScenarioMutation.mutateAsync({
      scenarioId,
      body: {
        name: data.name,
        description: data.description,
        tool_execution_mode: data.useLiveExecution ? 'live' : undefined,
        evaluation_criteria: evaluationCriteria,
      },
    });
  };

  const handleSuggestEvaluation = async (): Promise<Partial<CreateEvalFormData> | null> => {
    try {
      const suggestion = await suggestScenarioMutation.mutateAsync({
        body: {
          thread_id: threadId,
          max_options: 1,
        },
      });

      return {
        name: suggestion.name,
        description: suggestion.description,
        evaluationCriteria: {
          responseAccuracyExpectation: suggestion.response_accuracy_expectation ?? '',
        },
      };
    } catch (_error) {
      addSnackbar({
        message: 'Could not generate suggestion, but you can still create an evaluation manually',
        variant: 'danger',
      });
      return null;
    }
  };

  const handleRunTest = async (scenario: Scenario, numTrials: number = 1) => {
    const runStartedAt = typeof performance !== 'undefined' ? performance.now() : null;
    const executionMode = getScenarioExecutionMode(scenario);
    try {
      setBatchSummaryOutdated(true);
      const newRun = await createScenarioRunMutation.mutateAsync({
        scenarioId: scenario.scenario_id,
        body: { num_trials: numTrials },
      });
      track(`scenario_${newRun.scenario_id}.run_${newRun.scenario_run_id}.started`, executionMode);

      // Immediately update query cache with the new run data
      queryClient.setQueryData(['scenario-run-latest', scenario.scenario_id], newRun);

      // Set the selected run index to 0 (latest run) when starting a new test
      setSelectedRunIndices((prev) => new Map(prev).set(scenario.scenario_id, 0));

      expandResults(scenario.scenario_id);

      startScenarioPolling(scenario.scenario_id, {
        scenarioName: scenario.name,
        onSuccess: (completedRun) => {
          let trackedDurationMs: number | null = null;

          const trials = completedRun?.trials ?? [];

          if (trials.length > 0) {
            const largestInterval = trials.reduce<number | null>((currentMax, trial) => {
              const startedAt = trial.execution_state?.started_at;
              const finishedAt = trial.execution_state?.finished_at;

              if (!startedAt || !finishedAt) {
                return currentMax;
              }

              const startTimestamp = new Date(startedAt).getTime();
              const endTimestamp = new Date(finishedAt).getTime();

              if (Number.isNaN(startTimestamp) || Number.isNaN(endTimestamp) || endTimestamp < startTimestamp) {
                return currentMax;
              }

              const interval = endTimestamp - startTimestamp;
              if (currentMax === null || interval > currentMax) {
                return interval;
              }
              return currentMax;
            }, null);

            trackedDurationMs = largestInterval;
          }

          if (trackedDurationMs === null && runStartedAt !== null && typeof performance !== 'undefined') {
            trackedDurationMs = Math.max(Math.round(performance.now() - runStartedAt), 0);
          }

          if (trackedDurationMs !== null) {
            track(
              `scenario_${completedRun?.scenario_id}.run_${completedRun?.scenario_run_id}.duration`,
              trackedDurationMs.toString(),
            );
          }
          queryClient.invalidateQueries({ queryKey: ['threads', agentId] });
        },
      });
    } catch {
      addSnackbar({
        message: `Failed to run test for "${scenario.name}"`,
        variant: 'danger',
      });
    }
  };

  const handleRunBatch = async (numTrials: number = 1) => {
    try {
      const batchRun = await createBatchRunMutation.mutateAsync({
        agentId,
        body: { num_trials: numTrials },
      });
      track(`scenario_batch_run_${batchRun.batch_run_id}.started`);

      setLastBatchSummary(buildBatchSummary(batchRun, numTrials));
      setBatchSummaryOutdated(false);
      queryClient.setQueryData(['scenario-batch-run-latest', agentId], batchRun);

      const runStartedAtMap = new Map<string, number | null>();
      (batchRun.scenario_ids ?? []).forEach((scenarioId) => {
        const scenario = scenarioMap.get(scenarioId);
        if (!scenario) {
          return;
        }

        const currentRun = batchRun.trial_statuses?.find((trial) => trial.scenario_id === scenario.scenario_id);

        if (currentRun) {
          track(
            `scenario_${currentRun.scenario_id}.run_${currentRun.scenario_run_id}.started`,
            getScenarioExecutionMode(scenario),
          );
        }

        setSelectedRunIndices((prev) => new Map(prev).set(scenarioId, 0));
        expandResults(scenarioId);

        const runStartedAt = typeof performance !== 'undefined' ? performance.now() : null;
        runStartedAtMap.set(scenarioId, runStartedAt);
        queryClient.invalidateQueries({ queryKey: ['scenario-run-latest', scenarioId] });
        queryClient.invalidateQueries({ queryKey: ['scenario-runs', scenarioId] });
      });

      processedBatchScenarioRunsRef.current.clear();
      initializeBatchScenarioTracking(batchRun.scenario_ids ?? [], runStartedAtMap);
      handleBatchProgress(batchRun);

      const pollingPromise = startBatchPolling(batchRun);
      pollingPromise
        ?.then((result) => {
          if (!result) {
            return;
          }

          if (result.status === 'COMPLETED') {
            addSnackbar({
              message: 'Batch run completed successfully',
              variant: 'success',
            });
          }
        })
        .catch(() => {});
    } catch {
      addSnackbar({
        message: 'Failed to run all tests',
        variant: 'danger',
      });
      setLastBatchSummary(null);
      setBatchSummaryOutdated(false);
    }
  };

  const handleDeleteScenario = async (scenarioId: string) => {
    await deleteScenarioMutation.mutateAsync({
      scenarioId,
    });
  };

  const handleDeleteAllScenarios = async () => {
    if (isDeletingAll) {
      return;
    }

    const scenarioIds = scenarios.map((scenario) => scenario.scenario_id);
    if (scenarioIds.length === 0) {
      return;
    }

    setIsDeletingAll(true);

    try {
      await scenarioIds.reduce<Promise<void>>(async (prevPromise, scenarioId) => {
        await prevPromise;
        return deleteScenarioMutation.mutateAsync({ scenarioId }).then(() => {});
      }, Promise.resolve());

      addSnackbar({
        message: scenarioIds.length === 1 ? 'Deleted 1 evaluation' : `Deleted ${scenarioIds.length} evaluations`,
        variant: 'success',
      });
    } catch (error) {
      addSnackbar({
        message: 'Failed to delete evaluations',
        variant: 'danger',
      });
      throw error;
    } finally {
      setIsDeletingAll(false);
    }
  };

  const handleCancelScenarioRun = useCallback(
    async (scenarioId: string, scenarioRunId: string, options?: { suppressToast?: boolean }): Promise<boolean> => {
      try {
        await cancelScenarioRunMutation.mutateAsync({
          scenarioId,
          scenarioRunId,
        });
        const scenarioKey = scenarioId?.trim() || 'unknown';
        const runKey = scenarioRunId?.trim() || 'unknown';
        track(`scenario_${scenarioKey}.run_${runKey}.canceled`);

        if (!options?.suppressToast) {
          addSnackbar({
            message: 'Test run cancelled successfully',
            variant: 'success',
          });
        }
        return true;
      } catch (error) {
        if (!options?.suppressToast) {
          addSnackbar({
            message: 'Failed to cancel test run',
            variant: 'danger',
          });
        }
        return false;
      }
    },
    [cancelScenarioRunMutation, addSnackbar],
  );

  const handleCancelAllRunning = useCallback(async () => {
    if (isCancelingAll) {
      return;
    }

    const activeBatchRun =
      latestBatchRun && !TERMINAL_BATCH_STATUSES.includes(latestBatchRun.status) ? latestBatchRun : null;

    if (!activeBatchRun) {
      addSnackbar({
        message: 'No running tests to cancel',
        variant: 'danger',
      });
      return;
    }

    setIsCancelingAll(true);

    try {
      const canceledBatch = await cancelBatchRunMutation.mutateAsync({
        agentId,
        batchRunId: activeBatchRun.batch_run_id,
      });
      track(`scenario_batch_run_${activeBatchRun.batch_run_id}.canceled`);

      setLastBatchSummary((prev) =>
        buildBatchSummary(canceledBatch, prev?.batchRunId === canceledBatch.batch_run_id ? prev?.numTrials : undefined),
      );
      setBatchSummaryOutdated(false);
      queryClient.setQueryData(['scenario-batch-run-latest', agentId], canceledBatch);

      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['scenario-run'] }),
        queryClient.invalidateQueries({ queryKey: ['scenario-run-latest'] }),
        queryClient.invalidateQueries({ queryKey: ['scenario-runs'] }),
      ]);

      addSnackbar({
        message: 'Batch run cancelled successfully',
        variant: 'success',
      });
    } catch {
      addSnackbar({
        message: 'Failed to cancel running tests',
        variant: 'danger',
      });
    } finally {
      setIsCancelingAll(false);
    }
  }, [
    evaluations,
    addSnackbar,
    isCancelingAll,
    latestBatchRun,
    cancelBatchRunMutation,
    agentId,
    setLastBatchSummary,
    buildBatchSummary,
    setBatchSummaryOutdated,
    queryClient,
  ]);

  const hasRunbookUpdated = useMemo(() => {
    if (!latestBatchRun?.metadata?.runbook_updated_at || !agent?.runbook_structured?.updated_at) {
      return false;
    }

    const batchRunbookTime = new Date(latestBatchRun.metadata.runbook_updated_at).getTime();
    const currentRunbookTime = new Date(agent.runbook_structured.updated_at).getTime();

    return currentRunbookTime > batchRunbookTime;
  }, [latestBatchRun?.metadata?.runbook_updated_at, agent?.runbook_structured?.updated_at]);

  return {
    // Data
    evaluations,
    scenarios,
    loading,
    isAnyTestRunning,
    isBatchRunning,
    isCancelingAll,
    isDeletingAll,
    hasRunbookUpdated,

    // Mutations
    createScenarioMutation,
    updateScenarioMutation,
    deleteScenarioMutation,
    suggestScenarioMutation,
    cancelScenarioRunMutation,
    exportScenariosMutation,
    importScenariosMutation,

    // Business logic functions
    handleCreateEvaluation,
    handleUpdateEvaluation,
    handleSuggestEvaluation,
    handleRunTest,
    handleRunBatch,
    handleDeleteScenario,
    handleDeleteAllScenarios,
    handleCancelScenarioRun,
    handleCancelAllRunning,
  };
};
