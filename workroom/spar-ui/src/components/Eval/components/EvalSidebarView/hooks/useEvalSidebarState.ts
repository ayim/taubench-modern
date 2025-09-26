import { useState } from 'react';
import type { CreateEvalFormData } from '../components/CreateEvalDialog';

export interface DeleteTarget {
  scenario_id: string;
  name: string;
}

export const useEvalSidebarState = () => {
  const [deleteTarget, setDeleteTarget] = useState<DeleteTarget | null>(null);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [suggestedValues, setSuggestedValues] = useState<Partial<CreateEvalFormData> | undefined>(undefined);
  const [isFetchingSuggestion, setIsFetchingSuggestion] = useState(false);

  const [expandedResults, setExpandedResults] = useState<Set<string>>(new Set());
  const [expandedTrials, setExpandedTrials] = useState<Set<string>>(new Set());
  const [expandedEvaluations, setExpandedEvaluations] = useState<Set<string>>(new Set());

  const [selectedTrials, setSelectedTrials] = useState<Map<string, number>>(new Map());
  const [selectedTrialsForAll, setSelectedTrialsForAll] = useState<number>(1);
  const [selectedRunIndices, setSelectedRunIndices] = useState<Map<string, number>>(new Map());

  const toggleResults = (scenarioId: string) => {
    setExpandedResults((prev) => {
      if (prev.has(scenarioId)) {
        const next = new Set(prev);
        next.delete(scenarioId);
        return next;
      }
      return new Set([...prev, scenarioId]);
    });
  };

  const toggleTrialDetails = (trialKey: string) => {
    setExpandedTrials((prev) => {
      if (prev.has(trialKey)) {
        const next = new Set(prev);
        next.delete(trialKey);
        return next;
      }
      return new Set([...prev, trialKey]);
    });
  };

  const toggleEvaluationDetails = (evaluationKey: string) => {
    setExpandedEvaluations((prev) => {
      if (prev.has(evaluationKey)) {
        const next = new Set(prev);
        next.delete(evaluationKey);
        return next;
      }
      return new Set([...prev, evaluationKey]);
    });
  };

  const getSelectedTrialsForScenario = (scenarioId: string) => 
    selectedTrials.get(scenarioId) || 1;

  const resetCreateDialogState = () => {
    setCreateDialogOpen(false);
    setSuggestedValues(undefined);
    setIsFetchingSuggestion(false);
  };

  const handlePreviousRun = (scenarioId: string) => {
    const currentIndex = selectedRunIndices.get(scenarioId) ?? 0;
    if (currentIndex > 0) {
      const newIndex = currentIndex - 1;
      setSelectedRunIndices(prev => new Map(prev).set(scenarioId, newIndex));
    }
  };

  const handleNextRun = (scenarioId: string, totalRuns: number) => {
    const currentIndex = selectedRunIndices.get(scenarioId) ?? 0;
    if (currentIndex < totalRuns - 1) {
      const newIndex = currentIndex + 1;
      setSelectedRunIndices(prev => new Map(prev).set(scenarioId, newIndex));
    }
  };

  const setRunIndexToLatest = (scenarioId: string) => {
    setSelectedRunIndices(prev => new Map(prev).set(scenarioId, 0));
  };

  return {
    // State values
    deleteTarget,
    createDialogOpen,
    suggestedValues,
    isFetchingSuggestion,
    expandedResults,
    expandedTrials,
    expandedEvaluations,
    selectedTrials,
    selectedTrialsForAll,
    selectedRunIndices,

    // State setters
    setDeleteTarget,
    setCreateDialogOpen,
    setSuggestedValues,
    setIsFetchingSuggestion,
    setSelectedTrials,
    setSelectedTrialsForAll,
    setSelectedRunIndices,

    // Helper functions
    toggleResults,
    toggleTrialDetails,
    toggleEvaluationDetails,
    getSelectedTrialsForScenario,
    resetCreateDialogState,
    handlePreviousRun,
    handleNextRun,
    setRunIndexToLatest,
  };
};
