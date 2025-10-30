import { useState, useCallback } from 'react';
import type { CreateEvalFormData } from '../components/CreateEvalDialog';
import type { Scenario } from '../types';

export interface DeleteTarget {
  scenario_id: string;
  name: string;
}

export const useEvalSidebarState = () => {
  const [deleteTarget, setDeleteTarget] = useState<DeleteTarget | null>(null);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [suggestedValues, setSuggestedValues] = useState<Partial<CreateEvalFormData> | undefined>(undefined);
  const [isFetchingSuggestion, setIsFetchingSuggestion] = useState(false);
  const [editingScenario, setEditingScenario] = useState<Scenario | null>(null);

  const [expandedResultsOrder, setExpandedResultsOrder] = useState<string[]>([]);
  const [expandedTrials, setExpandedTrials] = useState<Set<string>>(new Set());
  const [expandedEvaluations, setExpandedEvaluations] = useState<Set<string>>(new Set());

  const expandedResults = new Set(expandedResultsOrder);

  const [selectedTrials, setSelectedTrials] = useState<Map<string, number>>(new Map());
  const [selectedTrialsForAll, setSelectedTrialsForAll] = useState<number>(1);
  const [selectedRunIndices, setSelectedRunIndices] = useState<Map<string, number>>(new Map());

  const toggleResults = (scenarioId: string) => {
    setExpandedResultsOrder((prev) => {
      // If already expanded, collapse it
      if (prev.includes(scenarioId)) {
        return prev.filter(id => id !== scenarioId);
      }
      
      // If expanding and already have 2, remove the oldest (first in array)
      if (prev.length >= 2) {
        return [...prev.slice(1), scenarioId];
      }
      
      // Otherwise just add it
      return [...prev, scenarioId];
    });
  };

  const expandResults = (scenarioId: string) => {
    setExpandedResultsOrder((prev) => {
      // Don't add if already expanded
      if (prev.includes(scenarioId)) {
        return prev;
      }
      
      // If already have 2, remove the oldest
      if (prev.length >= 2) {
        return [...prev.slice(1), scenarioId];
      }
      
      return [...prev, scenarioId];
    });
  };

  const toggleTrialDetails = useCallback((trialKey: string) => {
    setExpandedTrials((prev) => {
      if (prev.has(trialKey)) {
        const next = new Set(prev);
        next.delete(trialKey);
        return next;
      }
      return new Set([...prev, trialKey]);
    });
  }, []);

  const toggleEvaluationDetails = useCallback((evaluationKey: string) => {
    setExpandedEvaluations((prev) => {
      if (prev.has(evaluationKey)) {
        const next = new Set(prev);
        next.delete(evaluationKey);
        return next;
      }
      return new Set([...prev, evaluationKey]);
    });
  }, []);

  const getSelectedTrialsForScenario = (scenarioId: string) => 
    selectedTrials.get(scenarioId) || 1;

  const resetCreateDialogState = () => {
    setCreateDialogOpen(false);
    setSuggestedValues(undefined);
    setEditingScenario(null);
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

  const handleSelectRun = (scenarioId: string, runIndex: number) => {
    setSelectedRunIndices(prev => new Map(prev).set(scenarioId, runIndex));
  };

  return {
    // State values
    deleteTarget,
    createDialogOpen,
    suggestedValues,
    isFetchingSuggestion,
    editingScenario,
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
    setEditingScenario,
    setSelectedTrials,
    setSelectedTrialsForAll,
    setSelectedRunIndices,

    // Helper functions
    toggleResults,
    expandResults,
    toggleTrialDetails,
    toggleEvaluationDetails,
    getSelectedTrialsForScenario,
    resetCreateDialogState,
    handlePreviousRun,
    handleNextRun,
    setRunIndexToLatest,
    handleSelectRun,
  };
};
