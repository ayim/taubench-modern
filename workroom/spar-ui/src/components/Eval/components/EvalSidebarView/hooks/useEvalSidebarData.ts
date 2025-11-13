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
  useExportScenariosMutation,
  useImportScenariosMutation,
  useUpdateScenarioMutation,
} from '../../../../../queries/evals';
import type { ScenarioBatchRun } from '../../../../../queries/evals';
import { useSparUIContext } from '../../../../../api/context';
import { sortByCreatedAtDesc } from '../../../../../lib/utils';
import type { CreateEvalFormData } from '../components/CreateEvalDialog';
import type { BatchSummary, EvaluationItem, ScenarioRun, Scenario } from '../types';
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

  const deleteScenarioMutation = useDeleteScenarioMutation({});
  const createScenarioRunMutation = useCreateScenarioRunMutation({});
  const createBatchRunMutation = useCreateBatchRunMutation({});
  const createScenarioMutation = useCreateScenarioMutation({});
  const updateScenarioMutation = useUpdateScenarioMutation({});
  const suggestScenarioMutation = useSuggestScenarioMutation({});
  const cancelScenarioRunMutation = useCancelScenarioRunMutation({});
  const exportScenariosMutation = useExportScenariosMutation({});
  const importScenariosMutation = useImportScenariosMutation({});
  const { pollForCompletion } = usePollScenarioRun();
  const { pollBatchRun } = usePollBatchRun();

  const { data: scenarios = [], isLoading: scenariosLoading } = useListScenariosQuery({
    agentId,
  });
  const { data: latestBatchRun } = useLatestBatchRunQuery({ agentId });
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

    return {
      batchRunId: batchRun.batch_run_id,
      createdAt: batchRun.created_at,
      status: batchRun.status,
      statistics: batchRun.statistics,
      numTrials: inferredNumTrials,
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
      if (prev && prev.batchRunId === latestBatchRun.batch_run_id) {
        return buildBatchSummary(latestBatchRun, prev.numTrials);
      }
      return buildBatchSummary(latestBatchRun);
    });
    setBatchSummaryOutdated(false);
  }, [latestBatchRun, setLastBatchSummary, buildBatchSummary, setBatchSummaryOutdated]);

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

  // Track which scenarios we've auto-expanded to avoid expanding on every render
  const autoExpandedRef = useRef<Set<string>>(new Set());

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

  const monitorScenarioRun = useCallback(
    (scenario: Scenario, runStartedAt: number | null) => {
      pollForCompletion(scenario.scenario_id)
        .then((completedRun) => {
          if (!completedRun) {
            return;
          }

          let trackedDurationMs: number | null = null;
          const trials = completedRun.trials ?? [];

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
            track(`evals_execution.duration`, trackedDurationMs.toString());
          }
          queryClient.invalidateQueries({ queryKey: ['threads', agentId] });
        })
        .catch(() => {});
    },
    [agentId, pollForCompletion, queryClient, track],
  );

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
      track(`evals_execution.started`, executionMode);

      // Immediately update query cache with the new run data
      queryClient.setQueryData(['scenario-run-latest', scenario.scenario_id], newRun);

      // Set the selected run index to 0 (latest run) when starting a new test
      setSelectedRunIndices((prev) => new Map(prev).set(scenario.scenario_id, 0));

      expandResults(scenario.scenario_id);

      monitorScenarioRun(scenario, runStartedAt);
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

      setLastBatchSummary(buildBatchSummary(batchRun, numTrials));
      setBatchSummaryOutdated(false);
      queryClient.setQueryData(['scenario-batch-run-latest', agentId], batchRun);

      (batchRun.scenario_ids ?? []).forEach((scenarioId) => {
        const scenario = scenarioMap.get(scenarioId);
        if (!scenario) {
          return;
        }

        track(`evals_execution.started`, getScenarioExecutionMode(scenario));

        setSelectedRunIndices((prev) => new Map(prev).set(scenarioId, 0));
        expandResults(scenarioId);

        const runStartedAt = typeof performance !== 'undefined' ? performance.now() : null;
        monitorScenarioRun(scenario, runStartedAt);
      });

      pollBatchRun({ agentId, batchRunId: batchRun.batch_run_id })
        .then((result) => {
          if (!result) {
            return;
          }

          setLastBatchSummary((prev) =>
            buildBatchSummary(result, prev?.batchRunId === result.batch_run_id ? prev?.numTrials : numTrials),
          );
          setBatchSummaryOutdated(false);
          queryClient.setQueryData(['scenario-batch-run-latest', agentId], result);

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

  const handleCancelScenarioRun = useCallback(
    async (scenarioId: string, scenarioRunId: string, options?: { suppressToast?: boolean }): Promise<boolean> => {
      try {
        await cancelScenarioRunMutation.mutateAsync({
          scenarioId,
          scenarioRunId,
        });

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

    const targets = evaluations
      .filter(({ isRunning, latestRun }) => isRunning && Boolean(latestRun?.scenario_run_id))
      .map(({ scenario, latestRun }) => ({
        scenarioId: scenario.scenario_id,
        scenarioRunId: latestRun?.scenario_run_id as string,
      }));

    if (targets.length === 0) {
      addSnackbar({
        message: 'No running tests to cancel',
        variant: 'danger',
      });
      return;
    }

    setIsCancelingAll(true);
    try {
      const results = await Promise.all(
        targets.map(({ scenarioId, scenarioRunId }) =>
          handleCancelScenarioRun(scenarioId, scenarioRunId, { suppressToast: true }),
        ),
      );
      const successCount = results.filter(Boolean).length;

      if (successCount === targets.length) {
        addSnackbar({
          message: 'Cancelled all running tests',
          variant: 'success',
        });
      } else if (successCount === 0) {
        addSnackbar({
          message: 'Failed to cancel running tests',
          variant: 'danger',
        });
      } else {
        addSnackbar({
          message: 'Some tests failed to cancel',
          variant: 'danger',
        });
      }
    } finally {
      setIsCancelingAll(false);
    }
  }, [evaluations, handleCancelScenarioRun, addSnackbar, isCancelingAll]);

  return {
    // Data
    evaluations,
    scenarios,
    loading,
    isAnyTestRunning,
    isCancelingAll,

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
    handleCancelScenarioRun,
    handleCancelAllRunning,
  };
};
