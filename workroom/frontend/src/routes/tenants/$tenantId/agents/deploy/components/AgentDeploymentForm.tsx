import { FC, useRef, useState } from 'react';
import { Box, Button, Form, Link, Typography } from '@sema4ai/components';
import { IconArrowUpRight, IconQuestionMarkCircle } from '@sema4ai/icons';
import { FormProvider, useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { buildAgentDeploymentSchema } from './context';

import { AgentDeploymentFormSchema, AgentDeploymentStep } from './context';
import { Steps } from './Steps';
import { StepNavigation } from './StepNavigation';
import { AgentConfigurationStep } from './AgentConfigurationStep';
import { AgentOverviewStep } from './AgentOverviewStep';
import { McpConfigurationStep } from './McpConfigurationStep';
import { AgentPackageResponse } from './AgentUploadForm';

type Props = {
  defaultValues: AgentDeploymentFormSchema;
  agentTemplate: AgentPackageResponse['agentTemplate'];
  onSubmit: (payload: AgentDeploymentFormSchema) => void;
  isPending: boolean;
  title: string;
  existingAgentNames: string[];
};

export const AgentDeploymentForm: FC<Props> = ({
  agentTemplate,
  onSubmit,
  isPending,
  defaultValues,
  title,
  existingAgentNames,
}) => {
  const [wizardStep, setWizardStep] = useState<AgentDeploymentStep>(AgentDeploymentStep.AgentOverview);
  const formRef = useRef<HTMLFormElement>(null);

  const withActions = agentTemplate.actions.length > 0;
  const withMcpServers = agentTemplate.mcpServers.length > 0;
  const withDataSources = false;

  const isFinalStep = wizardStep === AgentDeploymentStep.ActionSettings;
  const isFirstStep = wizardStep === AgentDeploymentStep.AgentOverview;

  const formProps = useForm<AgentDeploymentFormSchema>({
    mode: 'onChange',
    defaultValues,
    shouldUnregister: false,
    resolver: zodResolver(buildAgentDeploymentSchema({ existingAgentNames })),
  });

  const { trigger, handleSubmit } = formProps;

  const onDeploy = handleSubmit(async (payload) => {
    onSubmit(payload);
  });

  const handleNext = async () => {
    switch (wizardStep) {
      case AgentDeploymentStep.AgentOverview:
        setWizardStep(AgentDeploymentStep.AgentSettings);
        return;

      case AgentDeploymentStep.AgentSettings: {
        const isFormValid = await trigger();
        if (!isFormValid) {
          return;
        }
        setWizardStep(AgentDeploymentStep.ActionSettings);
        return;
      }
      case AgentDeploymentStep.ActionSettings:
        return;
      default:
        wizardStep satisfies never;
        break;
    }
  };

  const onWizarStepChange = async (nextStep: AgentDeploymentStep) => {
    setWizardStep(nextStep);
  };

  const onBack = () => {
    switch (wizardStep) {
      case AgentDeploymentStep.AgentSettings:
        setWizardStep(AgentDeploymentStep.AgentOverview);
        break;
      case AgentDeploymentStep.ActionSettings:
        setWizardStep(AgentDeploymentStep.AgentSettings);
        break;
      case AgentDeploymentStep.AgentOverview:
        break;
      default:
        wizardStep satisfies never;
        break;
    }
  };

  return (
    <div className="h-full overflow-x-hidden">
      <div className="mx-12 my-10">
        <div className="flex flex-col h-full overflow-auto">
          {/* Header matching Agents page */}
          <header className="text-center">
            <div className="flex items-center justify-center gap-2 !mb-2 h-11">
              <img src="/svg/IconAgentsPage.svg" className="h-full" />
              <Typography
                lineHeight="29px"
                fontFamily="Heldane Display"
                fontWeight="500"
                as="h1"
                className="text-[2.5rem]"
              >
                {title}
              </Typography>
            </div>
            <p className="text-sm">
              Review and configure your agent and quickly get it deployed to the Workspace of your choice so you can
              share it with your team.
            </p>
          </header>

          <Box className="border border-solid bg-white border-[#CDCDCD] rounded-[10px] p-6 flex-grow my-8">
            <FormProvider {...formProps}>
              <Form ref={formRef}>
                <Steps
                  activeStep={wizardStep}
                  withActions={withActions}
                  withMcpServers={withMcpServers}
                  withDataSources={withDataSources}
                  setWizardStep={onWizarStepChange}
                />

                <Box mb="$40">
                  {wizardStep === AgentDeploymentStep.AgentOverview && (
                    <AgentOverviewStep agentTemplate={agentTemplate} />
                  )}
                  {wizardStep === AgentDeploymentStep.AgentSettings && (
                    <AgentConfigurationStep agentTemplate={agentTemplate} />
                  )}
                  {wizardStep === AgentDeploymentStep.ActionSettings && <McpConfigurationStep />}
                </Box>

                <Box mb="$40">
                  <Button.Group align="right">
                    <StepNavigation
                      isPending={isPending}
                      isFinalStep={isFinalStep}
                      isFirstStep={isFirstStep}
                      onBack={onBack}
                      onNext={handleNext}
                      onDeploy={onDeploy}
                    />
                  </Button.Group>
                </Box>
              </Form>
            </FormProvider>

            {false && (
              <Link
                icon={IconQuestionMarkCircle}
                iconAfter={IconArrowUpRight}
                target="_blank"
                href="#"
                rel="noopener"
                variant="secondary"
              >
                Deployment guide
              </Link>
            )}
          </Box>
        </div>
      </div>
    </div>
  );
};
