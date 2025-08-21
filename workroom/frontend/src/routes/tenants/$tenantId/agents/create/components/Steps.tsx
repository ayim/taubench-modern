import { FC, useEffect, useState } from 'react';
import { Box, Steps as StepsBase, StepStatusType } from '@sema4ai/components';
import { useFormContext } from 'react-hook-form';

import {
  AgentDeploymentFormSchema,
  AgentDeploymentFormSchemaStep1Schema,
  AgentDeploymentFormSchemaStep2Schema,
  AgentDeploymentFormSchemaStep3Schema,
  AgentDeploymentStep,
} from './context';

type Props = {
  activeStep: AgentDeploymentStep;
  withActions: boolean;
  withMcpServers: boolean;
  withTriggers: boolean;
  withDataSources: boolean;
  setWizardStep: (step: AgentDeploymentStep) => void;
};
export const Steps: FC<Props> = ({ activeStep, setWizardStep }) => {
  const [steps, setSteps] = useState<{ step: AgentDeploymentStep; label: string; visited: boolean }[]>([]);
  const {
    formState: { errors },
  } = useFormContext<AgentDeploymentFormSchema>();

  const errorKeys = Object.keys(errors);

  const stepIndex = steps.findIndex((step) => step.step === activeStep);

  const stepsErrors = [
    Object.keys(AgentDeploymentFormSchemaStep1Schema.shape).some((curr) => errorKeys.includes(curr)),
    Object.keys(AgentDeploymentFormSchemaStep2Schema.shape).some((curr) => errorKeys.includes(curr)),
    Object.keys(AgentDeploymentFormSchemaStep3Schema.shape).some((curr) => errorKeys.includes(curr)),
  ];

  // Removed getActionSettingsStepLabel since we have fixed step labels now

  useEffect(() => {
    setSteps([
      {
        step: AgentDeploymentStep.AgentOverview,
        label: 'Review Agent',
        visited: false,
      },
      {
        step: AgentDeploymentStep.AgentSettings,
        label: 'Agent Configuration',
        visited: false,
      },
      {
        step: AgentDeploymentStep.ActionSettings,
        label: 'Configure MCP',
        visited: false,
      },
    ]);
  }, []);

  useEffect(() => {
    setSteps((curr) => curr.map((step, index) => (index === stepIndex ? { ...step, visited: true } : step)));
  }, [stepIndex]);

  return (
    <Box mb="$32">
      <StepsBase activeStep={stepIndex} setActiveStep={(index) => setWizardStep(steps[index].step)}>
        {steps.map((step, index) => {
          const isDisabled = index !== 0 && !steps[index - 1].visited;

          let status: StepStatusType = step.visited ? 'completed' : 'incomplete';

          if (stepsErrors[index]) {
            status = 'error';
          }

          return (
            <StepsBase.Step
              key={step.step}
              disabled={isDisabled}
              disabledTooltip={isDisabled ? `${steps[index - 1].step} first` : undefined}
              status={status}
            >
              {step.label}
            </StepsBase.Step>
          );
        })}
      </StepsBase>
    </Box>
  );
};
