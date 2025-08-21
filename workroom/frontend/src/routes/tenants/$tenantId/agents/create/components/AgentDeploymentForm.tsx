import { FC, useEffect, useRef, useState } from 'react';
import { Box, Button, Form, Link, Typography } from '@sema4ai/components';
import { IconArrowUpRight, IconQuestionMarkCircle } from '@sema4ai/icons';
import { FormProvider, useForm } from 'react-hook-form';

import { AgentDeploymentFormSchema, AgentDeploymentStep } from './context';
import { Steps } from './Steps';
import { WizardStep1 } from './WizardStep1';
import { WizardStep2 } from './WizardStep2';
import { WizardStep3 } from './WizardStep3';
import { WizardStep4 } from './WizardStep4';
import { WizardStep5 } from './WizardStep5';
import { StepNavigation } from './StepNavigation';

// Mock agent template type
type MockAgentTemplate = {
  id: string;
  name: string;
  description: string;
  metadata: { mode: 'worker' | 'conversational' };
  actions: Array<{ id: string; name: string }>;
  mcpServers: Array<{
    config: {
      name: string;
      url: string;
      transport: 'sse' | 'streamable-http';
      headers: unknown;
    };
  }>;
  dataSources: Array<{
    id: string;
    engine: string;
    name: string;
  }>;
};

type Props = {
  defaultValues: AgentDeploymentFormSchema;
  agentTemplate: MockAgentTemplate;
  onSubmit: (payload: AgentDeploymentFormSchema) => void;
  isPending: boolean;
  title: string;
};

export const AgentDeploymentForm: FC<Props> = ({ agentTemplate, onSubmit, isPending, defaultValues, title }) => {
  const [wizardStep, setWizardStep] = useState<AgentDeploymentStep>(AgentDeploymentStep.AgentOverview);
  const [formValues, setFormValues] = useState<AgentDeploymentFormSchema>(defaultValues);
  const formRef = useRef<HTMLFormElement>(null);

  const [nameErrorMessage, setNameErrorMessage] = useState<string | undefined>(undefined);

  const dataSources = agentTemplate.dataSources ?? [];
  const mcpServers = agentTemplate.mcpServers.map((mcpServer) => mcpServer.config);

  const withTriggers = agentTemplate.metadata.mode === 'worker';
  const withActions = agentTemplate.actions.length > 0;
  const withMcpServers = mcpServers.length > 0;
  const withDataSources = dataSources.length > 0;

  // For the new 3-step flow: Review → Agent Configuration → Configure MCP
  const isFinalStep = wizardStep === AgentDeploymentStep.ActionSettings;
  const isFirstStep = wizardStep === AgentDeploymentStep.AgentOverview;

  const formProps = useForm<AgentDeploymentFormSchema>({
    mode: 'onChange',
    defaultValues,
  });

  const { trigger, handleSubmit, reset } = formProps;

  useEffect(() => {
    setFormValues(defaultValues);
    reset(defaultValues);
  }, [defaultValues, reset]);

  // Mock agent deployments for name validation (unused for now)
  // const agentDeployments: Array<{ id: string; name: string }> = [];

  const onStepSubmit = handleSubmit(async (payload, e) => {
    // hotfix for `react-hook-forms` nested forms (Create new Secret, LLM...) triggering submit event to all parent forms
    if (e?.target !== formRef.current) {
      return;
    }

    const updatedFormValues = { ...formValues, ...payload };

    setFormValues(updatedFormValues);

    if (isFinalStep) {
      onSubmit(updatedFormValues);
    } else {
      // New 3-step navigation flow
      switch (wizardStep) {
        case AgentDeploymentStep.AgentOverview:
          onWizarStepChange(AgentDeploymentStep.AgentSettings);
          break;
        case AgentDeploymentStep.AgentSettings:
          onWizarStepChange(AgentDeploymentStep.ActionSettings);
          break;
        // @ts-expect-error - ActionSettings is valid but TypeScript is confused
        case AgentDeploymentStep.ActionSettings:
          break;
        case AgentDeploymentStep.Triggers:
        case AgentDeploymentStep.DataSources:
          break;
        default:
          break;
      }
    }
  });

  const onWizarStepChange = async (nextStep: AgentDeploymentStep) => {
    if (wizardStep === AgentDeploymentStep.AgentSettings) {
      // Mock name validation
      setNameErrorMessage(undefined);
    }

    const formValid = await trigger();

    // Allow navigating from Document intelligence to allow to change Workspace
    if (formValid || wizardStep === AgentDeploymentStep.Triggers) {
      setWizardStep(nextStep);
    }
  };

  const onBack = () => {
    switch (wizardStep) {
      case AgentDeploymentStep.AgentSettings:
        setWizardStep(AgentDeploymentStep.AgentOverview);
        break;
      case AgentDeploymentStep.ActionSettings:
        setWizardStep(AgentDeploymentStep.AgentSettings);
        break;
      default:
        // Already on first step or invalid step
        break;
    }
  };

  // const isUpdatingDeployment = false; // Unused for now
  return (
    <div className="h-full overflow-x-hidden">
      <div className="mx-12 my-10">
        <div className="flex flex-col h-full overflow-auto">
          {/* Header matching Agents page */}
          <header className="text-center">
            <div className="flex items-center justify-center gap-2 !mb-2 h-11">
              <img src="svg/IconAgentsPage.svg" className="h-full" />
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
              <Form ref={formRef} onSubmit={onStepSubmit}>
                <Steps
                  activeStep={wizardStep}
                  withActions={withActions}
                  withMcpServers={withMcpServers}
                  withTriggers={withTriggers}
                  withDataSources={withDataSources}
                  setWizardStep={onWizarStepChange}
                />

                <Box mb="$40">
                  {wizardStep === AgentDeploymentStep.AgentOverview && <WizardStep1 agentTemplate={agentTemplate} />}
                  {wizardStep === AgentDeploymentStep.AgentSettings && <WizardStep2 errorMessage={nameErrorMessage} />}
                  {wizardStep === AgentDeploymentStep.ActionSettings && <WizardStep3 mcpServers={mcpServers} />}
                  {wizardStep === AgentDeploymentStep.Triggers && <WizardStep4 />}
                  {wizardStep === AgentDeploymentStep.DataSources && (
                    <WizardStep5 agentTemplateDataSources={dataSources} />
                  )}
                </Box>

                <Box mb="$40">
                  <Button.Group align="right">
                    <StepNavigation
                      isPending={isPending}
                      isFinalStep={isFinalStep}
                      isFirstStep={isFirstStep}
                      onBack={onBack}
                    />
                  </Button.Group>
                </Box>
              </Form>
            </FormProvider>

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
          </Box>
        </div>
      </div>
    </div>
  );
};
