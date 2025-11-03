import { FC } from 'react';
import { Box, Steps } from '@sema4ai/components';
import { IconNotebook, IconDatabase, IconPlay } from '@sema4ai/icons';
import { StepType } from '../types';

export interface StepHeaderProps {
  currentStep: StepType;
  availableSteps: Array<{
    id: StepType;
    textTop: string | null;
    textBottom: string | null;
    icon: typeof IconNotebook | typeof IconDatabase | typeof IconPlay;
  }>;
}

export const StepHeader: FC<StepHeaderProps> = ({ currentStep, availableSteps }) => {
  const currentStepIndex = availableSteps.findIndex((step) => step.id === currentStep);

  return (
    <Steps
      activeStep={currentStepIndex}
      size="large"
      setActiveStep={() => {}} // No-op function to disable clicks
      style={{ pointerEvents: 'none' }} // Disable all mouse interactions
    >
      {availableSteps.map((step, index) => {
        let status: 'completed' | undefined;

        // Determine step status based on position
        if (index < currentStepIndex) {
          status = 'completed';
        }
        // Note: Current step is handled by activeStep prop on Steps component
        const isActive = currentStep === step.id;
        const isCompleted = index < currentStepIndex;

        return (
          <Steps.Step
            key={step.id}
            status={status}
            stepIcon={step.icon}
            data-step="true"
            data-active={isActive}
            data-completed={isCompleted}
            className="docintel-step-icon"
            style={{ pointerEvents: 'none' }}
          >
            <Box display="flex" flexDirection="column" gap="$4" style={{ fontSize: '12px' }}>
              <Box>{step.textTop}</Box>
              <Box>{step.textBottom}</Box>
            </Box>
          </Steps.Step>
        );
      })}
    </Steps>
  );
};
