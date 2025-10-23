import { useSnackbar } from '@sema4ai/components';
import type { UseMutationResult } from '@tanstack/react-query';
import { useNavigate } from '../../../../../hooks';
import type { CreateEvalFormData } from '../components/CreateEvalDialog';
import type { DeleteTarget } from './useEvalSidebarState';
import type { EvaluationItem, Scenario } from '../types';

export interface UseEvalSidebarActionsProps {
  agentId: string;
  evaluations: EvaluationItem[];
  handleCreateEvaluation: (data: CreateEvalFormData) => Promise<void>;
  handleSuggestEvaluation: () => Promise<Partial<CreateEvalFormData> | null>;
  handleRunTest: (scenario: Scenario, numTrials: number) => Promise<void>;
  handleDeleteScenario: (scenarioId: string) => Promise<void>;
  handleCancelScenarioRun: (scenarioId: string, scenarioRunId: string) => Promise<void>;
  exportScenariosMutation: UseMutationResult<{ blob: Blob; filename: string }, unknown, { agentId: string }, unknown>;
  setCreateDialogOpen: (open: boolean) => void;
  setSuggestedValues: (values: Partial<CreateEvalFormData> | undefined) => void;
  setIsFetchingSuggestion: (fetching: boolean) => void;
  setDeleteTarget: (target: DeleteTarget | null) => void;
  resetCreateDialogState: () => void;
}

export const useEvalSidebarActions = ({
  agentId,
  evaluations,
  handleCreateEvaluation,
  handleSuggestEvaluation,
  handleRunTest,
  handleDeleteScenario,
  handleCancelScenarioRun,
  exportScenariosMutation,
  setCreateDialogOpen,
  setSuggestedValues,
  setIsFetchingSuggestion,
  setDeleteTarget,
  resetCreateDialogState,
}: UseEvalSidebarActionsProps) => {
  const { addSnackbar } = useSnackbar();
  const navigate = useNavigate();

  const handleAddEvaluation = async () => {
    setCreateDialogOpen(true);
    setIsFetchingSuggestion(true);
    setSuggestedValues(undefined);

    const suggestion = await handleSuggestEvaluation();
    setSuggestedValues(suggestion || undefined);
    setIsFetchingSuggestion(false);
  };

  const handleCreateEvaluationWithCleanup = async (data: CreateEvalFormData) => {
    await handleCreateEvaluation(data);
    resetCreateDialogState();
  };

  const handleRunAll = (numTrials: number = 1) => {
    evaluations.forEach(({ scenario }) => handleRunTest(scenario, numTrials));
  };

  const handleDeleteConfirm = async (deleteTarget: DeleteTarget | null) => {
    if (!deleteTarget) return;

    await handleDeleteScenario(deleteTarget.scenario_id);
    setDeleteTarget(null);
  };

  const handleViewResults = (trial: { threadId: string }) => {
    if (trial.threadId) {
      navigate({
        to: '/thread/$agentId/$threadId',
        params: {
          agentId,
          threadId: trial.threadId,
        },
      });
    }
  };

  const handleCancelTest = (scenario: Scenario, currentRun: EvaluationItem['currentRun']) => {
    return async () => {
      if (!currentRun?.scenario_run_id) {
        addSnackbar({
          message: 'No active test run to cancel',
          variant: 'danger',
        });
        return;
      }

      await handleCancelScenarioRun(scenario.scenario_id, currentRun.scenario_run_id);
    };
  };

  const handleExportScenarios = async () => {
    try {
      const { blob, filename } = await exportScenariosMutation.mutateAsync({ agentId });

      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = filename;
      document.body.appendChild(anchor);
      anchor.click();
      URL.revokeObjectURL(url);
      anchor.remove();

      addSnackbar({
        message: 'Scenarios exported successfully',
        variant: 'success',
      });
    } catch (error) {
      addSnackbar({
        message: 'Failed to export scenarios',
        variant: 'danger',
      });
    }
  };

  return {
    handleAddEvaluation,
    handleCreateEvaluationWithCleanup,
    handleRunAll,
    handleDeleteConfirm,
    handleViewResults,
    handleCancelTest,
    handleExportScenarios,
  };
};
