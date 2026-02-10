import { FC, useState, MouseEvent, useEffect } from 'react';
import { FormProvider, useForm } from 'react-hook-form';
import { Button, Card, Dialog, Form, Grid, Progress, Typography, useSnackbar } from '@sema4ai/components';
import { IconPlus } from '@sema4ai/icons';
import { zodResolver } from '@hookform/resolvers/zod';
import { AgentPackageInspectionResponse } from '~/queries/agentPackageInspection';
import { IconConversationalAgents, IconWorkerAgents } from '@sema4ai/icons/logos';
import { useNavigate, useParams } from '@tanstack/react-router';

import { generateUniqueName } from '~/lib/utils';
import { DEFAULT_NEW_AGENT_RUNBOOK } from '~/lib/constants';
import { useAgentsQuery, useDeployAgentMutation } from '~/queries/agents';
import { useTenantContext } from '~/lib/tenantContext';

import { AgentUploadForm } from './AgentUploadForm';
import { AgentName } from './components/AgentName';
import { CreateAgentFormSchema } from './components/context';
import { LLM } from './components/LLM';

type Props = {
  setAgentPackageUploadData: (data: {
    agentTemplate: NonNullable<AgentPackageInspectionResponse>;
    agentPackage: File;
  }) => void;
};

export const CreateAgentDialog: FC<Props> = ({ setAgentPackageUploadData }) => {
  const { tenantId } = useParams({ from: '/tenants/$tenantId' });
  const [open, setOpen] = useState(false);
  const { features } = useTenantContext();
  const { mutateAsync: deployAgent, isPending: isDeployingAgent } = useDeployAgentMutation({});
  const { addSnackbar } = useSnackbar();
  const navigate = useNavigate();
  const { data: agents, isLoading: isLoadingAgents } = useAgentsQuery({});

  const form = useForm<CreateAgentFormSchema>({
    resolver: zodResolver(CreateAgentFormSchema),
    defaultValues: {
      name: '',
      llmId: '',
      mode: 'conversational',
    },
  });

  useEffect(() => {
    if (agents && open) {
      form.reset({
        name: generateUniqueName(agents.map((agent) => agent.name)),
        llmId: '',
        mode: 'conversational',
      });
    }
  }, [agents, open]);

  const { watch, setValue } = form;
  const { mode } = watch();

  const onSubmit = form.handleSubmit((data) => {
    deployAgent(
      { payload: { ...data, description: '', runbook: DEFAULT_NEW_AGENT_RUNBOOK } },
      {
        onSuccess: (agentId) => {
          addSnackbar({ message: 'Agent deployed successfully', variant: 'success' });
          if (agentId) {
            if (data.mode === 'worker') {
              navigate({
                to: '/tenants/$tenantId/worker/$agentId',
                params: { agentId, tenantId },
              });
            } else {
              navigate({
                to: '/tenants/$tenantId/conversational/$agentId',
                params: { agentId, tenantId },
                search: { threadView: 'chat-details' },
              });
            }
          }
        },
        onError: (error) => {
          addSnackbar({ message: error.message, variant: 'danger' });
        },
      },
    );
  });

  const onModeChange = (value: 'conversational' | 'worker') => (e: MouseEvent<HTMLDivElement>) => {
    e.preventDefault();
    setValue('mode', value);
  };

  if (!features.agentAuthoring.enabled) {
    return null;
  }

  if (isLoadingAgents) {
    return <Progress variant="page" />;
  }

  return (
    <>
      <Button icon={IconPlus} round onClick={() => setOpen(true)}>
        Agent
      </Button>
      <Dialog open={open} onClose={() => setOpen(false)} width={980}>
        <Form onSubmit={onSubmit} busy={isDeployingAgent}>
          <FormProvider {...form}>
            <Dialog.Header>
              <Dialog.Header.Title title="Create new Agent" />
            </Dialog.Header>
            <Dialog.Content>
              <Form.Fieldset>
                <AgentName />
                <LLM />
              </Form.Fieldset>

              <Typography fontWeight="medium" mb="$8">
                Pick the type of Agent you want to create
              </Typography>
              <Grid columns={[1, 1, 2]} gap="$24" pt="$4" pb="$24">
                <Card
                  as="button"
                  title="Conversational Agent"
                  icon={IconConversationalAgents}
                  description="Engage in a conversation with your agent."
                  active={mode === 'conversational'}
                  onClick={onModeChange('conversational')}
                />

                <Card
                  as="button"
                  title="Worker Agent"
                  icon={IconWorkerAgents}
                  description="Automate and manage business processes."
                  active={mode === 'worker'}
                  onClick={onModeChange('worker')}
                />
              </Grid>

              <Typography fontWeight="medium" mb="$8">
                Or, upload an Agent package
              </Typography>
              <AgentUploadForm setAgentPackageUploadData={setAgentPackageUploadData} />
            </Dialog.Content>
            <Dialog.Actions>
              <Button variant="primary" round type="submit" loading={isDeployingAgent}>
                Create
              </Button>
              <Button variant="secondary" round onClick={() => setOpen(false)}>
                Cancel
              </Button>
            </Dialog.Actions>
          </FormProvider>
        </Form>
      </Dialog>
    </>
  );
};
