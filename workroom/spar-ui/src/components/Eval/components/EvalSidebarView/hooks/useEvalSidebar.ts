import { useEvalSidebarState } from './useEvalSidebarState';
import { useEvalSidebarData } from './useEvalSidebarData';
import { useEvalSidebarActions } from './useEvalSidebarActions';

export interface UseEvalSidebarProps {
  agentId: string;
  threadId: string;
  onDownloadJSON: (data: unknown, options: { filename: string; addTimestamp?: boolean }) => void;
}

export const useEvalSidebar = ({ agentId, threadId, onDownloadJSON }: UseEvalSidebarProps) => {
  const state = useEvalSidebarState();
  
  const data = useEvalSidebarData({
    agentId,
    threadId,
    selectedRunIndices: state.selectedRunIndices,
    setSelectedRunIndices: state.setSelectedRunIndices,
    expandResults: state.expandResults,
    expandedResults: state.expandedResults,
  });

  const actions = useEvalSidebarActions({
    agentId,
    evaluations: data.evaluations,
    onDownloadJSON,
    handleCreateEvaluation: data.handleCreateEvaluation,
    handleSuggestEvaluation: data.handleSuggestEvaluation,
    handleRunTest: data.handleRunTest,
    handleDeleteScenario: data.handleDeleteScenario,
    handleCancelScenarioRun: data.handleCancelScenarioRun,
    setCreateDialogOpen: state.setCreateDialogOpen,
    setSuggestedValues: state.setSuggestedValues,
    setIsFetchingSuggestion: state.setIsFetchingSuggestion,
    setDeleteTarget: state.setDeleteTarget,
    resetCreateDialogState: state.resetCreateDialogState,
  });

  return {
    // State values
    deleteTarget: state.deleteTarget,
    createDialogOpen: state.createDialogOpen,
    suggestedValues: state.suggestedValues,
    isFetchingSuggestion: state.isFetchingSuggestion,
    expandedResults: state.expandedResults,
    expandedTrials: state.expandedTrials,
    expandedEvaluations: state.expandedEvaluations,
    selectedTrials: state.selectedTrials,
    selectedTrialsForAll: state.selectedTrialsForAll,
    selectedRunIndices: state.selectedRunIndices,

    // State actions
    setDeleteTarget: state.setDeleteTarget,
    setCreateDialogOpen: state.setCreateDialogOpen,
    setSuggestedValues: state.setSuggestedValues,
    setIsFetchingSuggestion: state.setIsFetchingSuggestion,
    setSelectedTrials: state.setSelectedTrials,
    setSelectedTrialsForAll: state.setSelectedTrialsForAll,
    setSelectedRunIndices: state.setSelectedRunIndices,
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
    createScenarioMutation: data.createScenarioMutation,
    deleteScenarioMutation: data.deleteScenarioMutation,

    // Data handlers (business logic)
    handleRunTest: data.handleRunTest,
    handleCreateEvaluation: data.handleCreateEvaluation,
    handleSuggestEvaluation: data.handleSuggestEvaluation,
    handleDeleteScenario: data.handleDeleteScenario,

    // User action handlers
    handleAddEvaluation: actions.handleAddEvaluation,
    handleCreateEvaluationWithCleanup: actions.handleCreateEvaluationWithCleanup,
    handleRunAll: actions.handleRunAll,
    handleDeleteConfirm: actions.handleDeleteConfirm,
    handleDownloadScenario: actions.handleDownloadScenario,
    handleViewResults: actions.handleViewResults,
    handleCancelTest: actions.handleCancelTest,
  };
};
