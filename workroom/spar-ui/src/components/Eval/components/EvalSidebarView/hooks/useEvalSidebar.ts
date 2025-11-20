import { useEvalSidebarState } from './useEvalSidebarState';
import { useEvalSidebarData } from './useEvalSidebarData';
import { useEvalSidebarActions } from './useEvalSidebarActions';

export interface UseEvalSidebarProps {
  agentId: string;
  threadId: string;
}

export const useEvalSidebar = ({ agentId, threadId }: UseEvalSidebarProps) => {
  const state = useEvalSidebarState();

  const data = useEvalSidebarData({
    agentId,
    threadId,
    selectedRunIndices: state.selectedRunIndices,
    setSelectedRunIndices: state.setSelectedRunIndices,
    expandResults: state.expandResults,
    expandedResults: state.expandedResults,
    setLastBatchSummary: state.setLastBatchSummary,
    setBatchSummaryOutdated: state.setBatchSummaryOutdated,
  });

  const actions = useEvalSidebarActions({
    agentId,
    handleCreateEvaluation: data.handleCreateEvaluation,
    handleUpdateEvaluation: data.handleUpdateEvaluation,
    handleSuggestEvaluation: data.handleSuggestEvaluation,
    handleRunBatch: data.handleRunBatch,
    handleDeleteScenario: data.handleDeleteScenario,
    handleCancelScenarioRun: data.handleCancelScenarioRun,
    exportScenariosMutation: data.exportScenariosMutation,
    importScenariosMutation: data.importScenariosMutation,
    setCreateDialogOpen: state.setCreateDialogOpen,
    setSuggestedValues: state.setSuggestedValues,
    setDeleteTarget: state.setDeleteTarget,
    editingScenario: state.editingScenario,
    setEditingScenario: state.setEditingScenario,
    resetCreateDialogState: state.resetCreateDialogState,
  });

  const isSubmittingEvaluation = state.editingScenario
    ? data.updateScenarioMutation.isPending
    : data.createScenarioMutation.isPending;

  return {
    // State values
    deleteTarget: state.deleteTarget,
    createDialogOpen: state.createDialogOpen,
    suggestedValues: state.suggestedValues,
    isFetchingSuggestion: data.suggestScenarioMutation.isPending,
    expandedResults: state.expandedResults,
    expandedTrials: state.expandedTrials,
    expandedEvaluations: state.expandedEvaluations,
    selectedTrials: state.selectedTrials,
    selectedTrialsForAll: state.selectedTrialsForAll,
    selectedRunIndices: state.selectedRunIndices,
    editingScenario: state.editingScenario,
    lastBatchSummary: state.lastBatchSummary,
    isBatchSummaryOutdated: state.isBatchSummaryOutdated,
    runbookWarningDismissed: state.runbookWarningDismissed,

    // State actions
    setDeleteTarget: state.setDeleteTarget,
    setCreateDialogOpen: state.setCreateDialogOpen,
    setSuggestedValues: state.setSuggestedValues,
    setIsFetchingSuggestion: state.setIsFetchingSuggestion,
    setSelectedTrials: state.setSelectedTrials,
    setSelectedTrialsForAll: state.setSelectedTrialsForAll,
    setSelectedRunIndices: state.setSelectedRunIndices,
    setRunbookWarningDismissed: state.setRunbookWarningDismissed,
    toggleResults: state.toggleResults,
    expandResults: state.expandResults,
    toggleTrialDetails: state.toggleTrialDetails,
    toggleEvaluationDetails: state.toggleEvaluationDetails,
    getSelectedTrialsForScenario: state.getSelectedTrialsForScenario,
    resetCreateDialogState: state.resetCreateDialogState,
    handlePreviousRun: state.handlePreviousRun,
    handleNextRun: state.handleNextRun,
    setRunIndexToLatest: state.setRunIndexToLatest,
    handleSelectRun: state.handleSelectRun,

    // Data
    evaluations: data.evaluations,
    loading: data.loading,
    isAnyTestRunning: data.isAnyTestRunning,
    isCancelingAll: data.isCancelingAll,
    hasRunbookUpdated: data.hasRunbookUpdated,
    createScenarioMutation: data.createScenarioMutation,
    updateScenarioMutation: data.updateScenarioMutation,
    deleteScenarioMutation: data.deleteScenarioMutation,
    suggestScenarioMutation: data.suggestScenarioMutation,
    exportScenariosMutation: data.exportScenariosMutation,
    importScenariosMutation: data.importScenariosMutation,
    isSubmittingEvaluation,

    // Data handlers (business logic)
    handleRunTest: data.handleRunTest,
    handleCreateEvaluation: data.handleCreateEvaluation,
    handleUpdateEvaluation: data.handleUpdateEvaluation,
    handleSuggestEvaluation: data.handleSuggestEvaluation,
    handleDeleteScenario: data.handleDeleteScenario,
    handleCancelAllRunning: data.handleCancelAllRunning,

    // User action handlers
    handleAddEvaluation: actions.handleAddEvaluation,
    handleEditEvaluation: actions.handleEditEvaluation,
    handleSubmitEvaluation: actions.handleSubmitEvaluation,
    handleRunAll: actions.handleRunAll,
    handleDeleteConfirm: actions.handleDeleteConfirm,
    handleViewResults: actions.handleViewResults,
    handleCancelTest: actions.handleCancelTest,
    handleExportScenarios: actions.handleExportScenarios,
    handleImportScenarios: actions.handleImportScenarios,
  };
};
