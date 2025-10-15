import { useCallback } from 'react';
import { IconNotebook, IconDatabase, IconPlay } from '@sema4ai/icons';
import { StepType } from '../types';
import { useStepManagement } from './useStepManagement';

interface StepConfig {
  id: StepType;
  textTop: string;
  textBottom: string;
  icon: typeof IconNotebook | typeof IconDatabase | typeof IconPlay;
}

export const useStepNavigation = (flowType: string) => {
  const { currentStep, setCurrentStep } = useStepManagement();

  const stepConfigs: StepConfig[] = [
    {
      id: 'document_layout' as StepType,
      textTop: 'Fields and',
      textBottom: 'Tables',
      icon: IconNotebook,
    },
    {
      id: 'data_model' as StepType,
      textTop: 'Data',
      textBottom: 'Model',
      icon: IconDatabase,
    },
    {
      id: 'data_quality' as StepType,
      textTop: 'Data',
      textBottom: 'Quality',
      icon: IconPlay,
    },
  ];

  // Filter steps based on flow type
  const getAvailableSteps = useCallback(() => {
    const isCreateDocLayoutFlow = flowType === 'create_doc_layout_from_existing_data_model';

    if (isCreateDocLayoutFlow) {
      // Hide Data Model step - only Document Layout and Data Quality
      return stepConfigs.filter((step) => step.id !== 'data_model');
    }
    return stepConfigs;
  }, [flowType]);

  const availableSteps = getAvailableSteps();
  const currentStepIndex = availableSteps.findIndex((step) => step.id === currentStep);
  const isLastStep = currentStepIndex === availableSteps.length - 1;

  const goToNextStep = useCallback(() => {
    if (!isLastStep) {
      const nextStep = availableSteps[currentStepIndex + 1];
      setCurrentStep(nextStep.id);
    }
  }, [isLastStep, currentStepIndex, availableSteps, setCurrentStep]);

  const goToPreviousStep = useCallback(() => {
    if (currentStepIndex > 0) {
      const previousStep = availableSteps[currentStepIndex - 1];
      setCurrentStep(previousStep.id);
    }
  }, [currentStepIndex, availableSteps, setCurrentStep]);

  return {
    currentStep,
    availableSteps,
    currentStepIndex,
    isLastStep,
    goToNextStep,
    goToPreviousStep,
  };
};
