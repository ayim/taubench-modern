import { useSnackbar } from '@sema4ai/components';
import type { UseMutationResult } from '@tanstack/react-query';
import { useNavigate, useParams } from '@tanstack/react-router';
import type { CreateEvalFormData } from '../components/CreateEvalDialog';
import type { DeleteTarget } from './useEvalSidebarState';
import type { Scenario, ScenarioRun } from '../types';

export interface UseEvalSidebarActionsProps {
  agentId: string;
  handleCreateEvaluation: (data: CreateEvalFormData) => Promise<void>;
  handleUpdateEvaluation: (scenarioId: string, data: CreateEvalFormData) => Promise<void>;
  handleSuggestEvaluation: () => Promise<Partial<CreateEvalFormData> | null>;
  handleRunBatch: (numTrials: number) => Promise<void>;
  handleDeleteScenario: (scenarioId: string) => Promise<void>;
  handleDeleteAllScenarios: () => Promise<void>;
  handleCancelScenarioRun: (
    scenarioId: string,
    scenarioRunId: string,
    options?: { suppressToast?: boolean },
  ) => Promise<boolean>;
  exportScenariosMutation: UseMutationResult<{ blob: Blob; filename: string }, unknown, { agentId: string }, unknown>;
  importScenariosMutation: UseMutationResult<Scenario[], unknown, { agentId: string; file: File }, unknown>;
  setCreateDialogOpen: (open: boolean) => void;
  setSuggestedValues: (values: Partial<CreateEvalFormData> | undefined) => void;
  setDeleteTarget: (target: DeleteTarget | null) => void;
  setDeleteAllDialogOpen: (open: boolean) => void;
  editingScenario: Scenario | null;
  setEditingScenario: (scenario: Scenario | null) => void;
  resetCreateDialogState: () => void;
}

export const useEvalSidebarActions = ({
  agentId,
  handleCreateEvaluation,
  handleUpdateEvaluation,
  handleSuggestEvaluation,
  handleRunBatch,
  handleDeleteScenario,
  handleDeleteAllScenarios,
  handleCancelScenarioRun,
  exportScenariosMutation,
  importScenariosMutation,
  setCreateDialogOpen,
  setSuggestedValues,
  setDeleteTarget,
  setDeleteAllDialogOpen,
  editingScenario,
  setEditingScenario,
  resetCreateDialogState,
}: UseEvalSidebarActionsProps) => {
  const { addSnackbar } = useSnackbar();
  const navigate = useNavigate();
  const { tenantId } = useParams({ from: '/tenants/$tenantId' });

  const isRecord = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null;

  const mapScenarioToFormValues = (scenario: Scenario): Partial<CreateEvalFormData> => {
    const metadata = isRecord(scenario.metadata) ? scenario.metadata : {};
    const driftPolicy = isRecord(metadata.drift_policy) ? metadata.drift_policy : {};
    const evaluationKinds = isRecord(metadata.evaluations) ? metadata.evaluations : {};
    const responseAccuracy = isRecord(evaluationKinds.response_accuracy) ? evaluationKinds.response_accuracy : {};

    const expectation = typeof responseAccuracy.expectation === 'string' ? responseAccuracy.expectation : '';
    const toolExecutionMode =
      typeof driftPolicy.tool_execution_mode === 'string' ? driftPolicy.tool_execution_mode : null;

    return {
      name: scenario.name,
      description: scenario.description,
      useLiveExecution: toolExecutionMode === 'live',
      evaluationCriteria: {
        responseAccuracyExpectation: expectation,
      },
    };
  };

  const handleAddEvaluation = async () => {
    setSuggestedValues(undefined);
    setEditingScenario(null);

    const suggestion = await handleSuggestEvaluation();
    setSuggestedValues(suggestion || undefined);
    setCreateDialogOpen(true);
  };

  const handleEditEvaluation = (scenario: Scenario) => {
    setEditingScenario(scenario);
    setSuggestedValues(mapScenarioToFormValues(scenario));
    setCreateDialogOpen(true);
  };

  const handleSubmitEvaluation = async (data: CreateEvalFormData) => {
    if (editingScenario) {
      await handleUpdateEvaluation(editingScenario.scenario_id, data);
    } else {
      await handleCreateEvaluation(data);
    }
    resetCreateDialogState();
  };

  const handleRunAll = (numTrials: number = 1) => handleRunBatch(numTrials);

  const handleDeleteConfirm = async (deleteTarget: DeleteTarget | null) => {
    if (!deleteTarget) return;

    await handleDeleteScenario(deleteTarget.scenario_id);
    setDeleteTarget(null);
  };

  const handleViewResults = (trial: { threadId: string; scenarioId: string; scenarioRunId: string }) => {
    if (trial.threadId) {
      // Navigate to evaluations route to keep eval sidebar open
      navigate({
        to: '/tenants/$tenantId/conversational/$agentId/$threadId/evaluations',
        params: {
          tenantId,
          agentId,
          threadId: trial.threadId,
        },
      });
    }
  };

  const handleCancelTest = (scenario: Scenario, currentRun: ScenarioRun | null) => {
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
        message: 'Evaluations exported successfully',
        variant: 'success',
      });
    } catch (error) {
      addSnackbar({
        message: 'Failed to export evaluations',
        variant: 'danger',
      });
    }
  };

  const handleImportScenarios = async (file: File) => {
    try {
      const scenarios = await importScenariosMutation.mutateAsync({ agentId, file });
      const importedCount = scenarios.length;

      addSnackbar({
        message:
          importedCount > 0
            ? `Imported ${importedCount} evaluation${importedCount === 1 ? '' : 's'} successfully`
            : 'Imported evaluations successfully',
        variant: 'success',
      });
    } catch (error) {
      addSnackbar({
        message: 'Failed to import evaluations',
        variant: 'danger',
      });
    }
  };

  return {
    handleAddEvaluation,
    handleEditEvaluation,
    handleSubmitEvaluation,
    handleRunAll,
    handleDeleteConfirm,
    handleViewResults,
    handleCancelTest,
    handleExportScenarios,
    handleImportScenarios,
    handleDeleteAllConfirm: async () => {
      try {
        await handleDeleteAllScenarios();
        setDeleteAllDialogOpen(false);
      } catch {
        // Error handled in data layer, keep dialog open for retry.
      }
    },
  };
};
