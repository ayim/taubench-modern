import { useReducer, useCallback } from 'react';
import type { StepType } from '../types';

// Step management state
interface StepState {
  currentStep: StepType;
  completedSteps: StepType[];
}

// Step management actions
type StepAction =
  | { type: 'SET_STEP'; step: StepType }
  | { type: 'COMPLETE_STEP'; step: StepType }
  | { type: 'RESET_STEPS' }
  | { type: 'GO_TO_NEXT_STEP' }
  | { type: 'GO_TO_PREVIOUS_STEP' };

// Step reducer
const stepReducer = (state: StepState, action: StepAction): StepState => {
  switch (action.type) {
    case 'SET_STEP':
      return {
        ...state,
        currentStep: action.step,
      };

    case 'COMPLETE_STEP':
      return {
        ...state,
        completedSteps: state.completedSteps.includes(action.step)
          ? state.completedSteps
          : [...state.completedSteps, action.step],
      };

    case 'RESET_STEPS':
      return {
        currentStep: 'document_layout',
        completedSteps: [],
      };

    case 'GO_TO_NEXT_STEP': {
      const stepOrder: StepType[] = ['document_layout', 'data_model', 'data_quality'];
      const currentIndex = stepOrder.indexOf(state.currentStep);
      const nextIndex = Math.min(currentIndex + 1, stepOrder.length - 1);
      return {
        ...state,
        currentStep: stepOrder[nextIndex],
      };
    }

    case 'GO_TO_PREVIOUS_STEP': {
      const stepOrder: StepType[] = ['document_layout', 'data_model', 'data_quality'];
      const currentIndex = stepOrder.indexOf(state.currentStep);
      const prevIndex = Math.max(currentIndex - 1, 0);
      return {
        ...state,
        currentStep: stepOrder[prevIndex],
      };
    }

    default:
      return state;
  }
};

// Initial step state
const initialStepState: StepState = {
  currentStep: 'document_layout',
  completedSteps: [],
};

// Custom hook for step management
export const useStepManagement = () => {
  const [stepState, dispatch] = useReducer(stepReducer, initialStepState);

  // Action creators
  const setCurrentStep = useCallback((step: StepType) => {
    dispatch({ type: 'SET_STEP', step });
  }, []);

  const completeStep = useCallback((step: StepType) => {
    dispatch({ type: 'COMPLETE_STEP', step });
  }, []);

  const resetSteps = useCallback(() => {
    dispatch({ type: 'RESET_STEPS' });
  }, []);

  const goToNextStep = useCallback(() => {
    dispatch({ type: 'GO_TO_NEXT_STEP' });
  }, []);

  const goToPreviousStep = useCallback(() => {
    dispatch({ type: 'GO_TO_PREVIOUS_STEP' });
  }, []);

  // Helper functions
  const isStepCompleted = useCallback(
    (step: StepType) => {
      return stepState.completedSteps.includes(step);
    },
    [stepState.completedSteps],
  );

  const canGoToNextStep = useCallback(() => {
    const stepOrder: StepType[] = ['document_layout', 'data_model', 'data_quality'];
    const currentIndex = stepOrder.indexOf(stepState.currentStep);
    return currentIndex < stepOrder.length - 1;
  }, [stepState.currentStep]);

  const canGoToPreviousStep = useCallback(() => {
    const stepOrder: StepType[] = ['document_layout', 'data_model', 'data_quality'];
    const currentIndex = stepOrder.indexOf(stepState.currentStep);
    return currentIndex > 0;
  }, [stepState.currentStep]);

  return {
    // State
    currentStep: stepState.currentStep,
    completedSteps: stepState.completedSteps,

    // Actions
    setCurrentStep,
    completeStep,
    resetSteps,
    goToNextStep,
    goToPreviousStep,

    // Helpers
    isStepCompleted,
    canGoToNextStep,
    canGoToPreviousStep,
  };
};
