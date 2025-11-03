import { useMemo, useEffect, useRef } from 'react';
import { useQueries, useQueryClient } from '@tanstack/react-query';
import { useSnackbar } from '@sema4ai/components';
import type { components } from '@sema4ai/agent-server-interface';
import {
  latestScenarioRunQueryOptions,
  scenarioRunsQueryOptions,
  scenarioRunQueryOptions,
  useCreateScenarioMutation,
  useCreateScenarioRunMutation,
  useDeleteScenarioMutation,
  useListScenariosQuery,
  usePollScenarioRun,
  useSuggestScenarioMutation,
  useCancelScenarioRunMutation,
  useExportScenariosMutation,
  useImportScenariosMutation,
  useUpdateScenarioMutation,
} from '../../../../../queries/evals';
import { useSparUIContext } from '../../../../../api/context';
import { sortByCreatedAtDesc } from '../../../../../lib/utils';
import type { CreateEvalFormData } from '../components/CreateEvalDialog';
import type { EvaluationItem, ScenarioRun, Scenario } from '../types';

export interface UseEvalSidebarDataProps {
  agentId: string;
  threadId: string;
  selectedRunIndices: Map<string, number>;
  setSelectedRunIndices: (value: Map<string, number> | ((prev: Map<string, number>) => Map<string, number>)) => void;
  expandResults: (scenarioId: string) => void;
  expandedResults: Set<string>;
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
}: UseEvalSidebarDataProps) => {
  const { sparAPIClient } = useSparUIContext();
  const queryClient = useQueryClient();
  const { addSnackbar } = useSnackbar();

  const deleteScenarioMutation = useDeleteScenarioMutation({});
  const createScenarioRunMutation = useCreateScenarioRunMutation({});
  const createScenarioMutation = useCreateScenarioMutation({});
  const updateScenarioMutation = useUpdateScenarioMutation({});
  const suggestScenarioMutation = useSuggestScenarioMutation({});
  const cancelScenarioRunMutation = useCancelScenarioRunMutation({});
  const exportScenariosMutation = useExportScenariosMutation({});
  const importScenariosMutation = useImportScenariosMutation({});
  const { pollForCompletion } = usePollScenarioRun();

  const { data: scenarios = [], isLoading: scenariosLoading } = useListScenariosQuery({
    agentId,
  });

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
    try {
      const newRun = await createScenarioRunMutation.mutateAsync({
        scenarioId: scenario.scenario_id,
        body: { num_trials: numTrials },
      });

      // Immediately update query cache with the new run data
      queryClient.setQueryData(['scenario-run-latest', scenario.scenario_id], newRun);

      // Set the selected run index to 0 (latest run) when starting a new test
      setSelectedRunIndices((prev) => new Map(prev).set(scenario.scenario_id, 0));

      expandResults(scenario.scenario_id);

      pollForCompletion(scenario.scenario_id).then(() => {
        queryClient.invalidateQueries({ queryKey: ['threads', agentId] });
      });
    } catch {
      addSnackbar({
        message: `Failed to run test for "${scenario.name}"`,
        variant: 'danger',
      });
    }
  };

  const handleDeleteScenario = async (scenarioId: string) => {
    await deleteScenarioMutation.mutateAsync({
      scenarioId,
    });
  };

  const handleCancelScenarioRun = async (scenarioId: string, scenarioRunId: string) => {
    try {
      await cancelScenarioRunMutation.mutateAsync({
        scenarioId,
        scenarioRunId,
      });

      addSnackbar({
        message: 'Test run cancelled successfully',
        variant: 'success',
      });
    } catch (error) {
      addSnackbar({
        message: 'Failed to cancel test run',
        variant: 'danger',
      });
    }
  };

  return {
    // Data
    evaluations,
    scenarios,
    loading,
    isAnyTestRunning,

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
    handleDeleteScenario,
    handleCancelScenarioRun,
  };
};
