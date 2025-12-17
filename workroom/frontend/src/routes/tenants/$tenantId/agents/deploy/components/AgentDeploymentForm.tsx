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
import { components } from '@sema4ai/agent-server-interface';

type Props = {
  defaultValues: AgentDeploymentFormSchema;
  agentTemplate: components['schemas']['AgentPackageInspectionResponse'];
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

  const withActions = (agentTemplate.action_packages?.length ?? 0) > 0;
  const withMcpServers = (agentTemplate.mcp_servers?.length ?? 0) > 0;
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
    <Box display="flex" flexDirection="column" gap="$40">
      <Box display="flex" flexDirection="column" gap="$24">
        <Typography variant="display-large">{title}</Typography>
        <Typography variant="body-large-loose">
          Review and configure your agent and quickly get it deployed to the Workspace of your choice so you can share
          it with your team.
        </Typography>
      </Box>
      <Box className="border border-solid bg-white border-[#CDCDCD] rounded-[10px] p-6 flex-grow my-8">
        <FormProvider {...formProps}>
          <Form ref={formRef}>
            {wizardStep !== AgentDeploymentStep.AgentOverview && (
              <Steps
                activeStep={wizardStep}
                withActions={withActions}
                withMcpServers={withMcpServers}
                withDataSources={withDataSources}
                setWizardStep={onWizarStepChange}
              />
            )}

            <Box mb="$40">
              {wizardStep === AgentDeploymentStep.AgentOverview && <AgentOverviewStep agentTemplate={agentTemplate} />}
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
    </Box>
    //     </div>
    //   </div>
    // </div>
  );
};
