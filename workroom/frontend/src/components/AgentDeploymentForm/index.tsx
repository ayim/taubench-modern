import { FC, useRef } from 'react';
import { Box, Button, Form, Link, Typography, useSnackbar } from '@sema4ai/components';
import { styled } from '@sema4ai/theme';
import { FormProvider, useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useNavigate, useParams } from '@tanstack/react-router';

import { ActionSticky } from '~/components/form/StickyActions';
import { Accordion } from '~/components/Accordion';
import { EXTERNAL_LINKS } from '../../lib/constants';
import { useAgentsQuery, useDeployAgentFromPackageMutation, useDeployAgentMutation } from '~/queries/agents';
import { AgentPackageInspectionResponse } from '~/queries/agentPackageInspection';
import { buildAgentDeploymentSchema, AgentDeploymentFormSchema, getDefaultValues } from './context';

import { AgentName } from './components/AgentName';
import { LLM } from './components/LLM';
import { MCPServers } from './components/MCPServers';
import { ActionPackages } from './components/ActionPackages';
import { AgentDescription } from './components/AgentDescription';
import { Runbook } from './components/Runbook';

type Props = {
  agentTemplate: NonNullable<AgentPackageInspectionResponse>;
  agentPackage?: File;
  onCancel: () => void;
  runbook?: string;
};

const Container = styled.div`
  position: relative;
  height: 100%;
`;

export const AgentDeploymentForm: FC<Props> = ({ agentTemplate, agentPackage, runbook, onCancel }) => {
  const formRef = useRef<HTMLFormElement>(null);
  const { data: allAgents = [] } = useAgentsQuery({});
  const { mutateAsync: deployAgentFromPackage, isPending: isDeployingAgentFromPackage } =
    useDeployAgentFromPackageMutation({});
  const { mutateAsync: deployAgent, isPending: isDeployingAgent } = useDeployAgentMutation({});
  const { addSnackbar } = useSnackbar();
  const navigate = useNavigate();
  const { tenantId } = useParams({ from: '/tenants/$tenantId' });

  const formProps = useForm<AgentDeploymentFormSchema>({
    mode: 'onChange',
    defaultValues: getDefaultValues(agentTemplate, runbook),
    shouldUnregister: false,
    resolver: zodResolver(buildAgentDeploymentSchema({ existingAgentNames: allAgents.map((agent) => agent.name) })),
  });

  const { handleSubmit } = formProps;

  const onDeploy = handleSubmit(async (payload) => {
    if (agentPackage) {
      deployAgentFromPackage(
        { agentTemplate, agentPackage, payload },
        {
          onSuccess: (data) => {
            addSnackbar({ message: 'Agent deployed successfully', variant: 'success' });
            if (data.agent_id) {
              if (payload.mode === 'worker') {
                navigate({
                  to: '/tenants/$tenantId/conversational/$agentId',
                  params: { agentId: data.agent_id, tenantId },
                });
              } else {
                navigate({ to: '/tenants/$tenantId/worker/$agentId', params: { agentId: data.agent_id, tenantId } });
              }
            }
          },
          onError: (error) => {
            addSnackbar({ message: error.message, variant: 'danger' });
          },
        },
      );
    } else {
      deployAgent(
        { payload },
        {
          onSuccess: (agentId) => {
            addSnackbar({ message: 'Agent deployed successfully', variant: 'success' });
            if (agentId) {
              if (payload.mode === 'worker') {
                navigate({
                  to: '/tenants/$tenantId/conversational/$agentId',
                  params: { agentId, tenantId },
                });
              } else {
                navigate({ to: '/tenants/$tenantId/worker/$agentId', params: { agentId, tenantId } });
              }
            }
          },
          onError: (error) => {
            addSnackbar({ message: error.message, variant: 'danger' });
          },
        },
      );
    }
  });

  const isPending = isDeployingAgentFromPackage || isDeployingAgent;

  return (
    <Container>
      <FormProvider {...formProps}>
        <Form ref={formRef} onSubmit={onDeploy} busy={isPending}>
          <Box display="flex" flexDirection="column" gap="$8" mb="$40">
            <Typography variant="display-medium">Deploy Agent</Typography>
            <Typography variant="body-large-loose" color="content.subtle">
              You&apos;re about to deploy this agent. Review its configuration and provide the required settings and
              secrets so it&apos;s ready to be used.{' '}
              <Link href={EXTERNAL_LINKS.AGENT_DEPLOYMENT_GUIDE} target="_blank" rel="noopener">
                Deployment Guide
              </Link>
            </Typography>
          </Box>

          <Box display="flex" flexDirection="column" gap="$20">
            <AgentName agentTemplate={agentTemplate} />

            <Runbook />

            <LLM agentTemplate={agentTemplate} />

            <Box display="flex" flexDirection="column" gap="$4" mt="$20">
              <Typography variant="display-small" fontWeight="bold">
                Actions & MCP servers
              </Typography>
              <Typography>
                Provide the credentials and configuration required for actions and MCP servers so the agent can
                successfully execute tool calls.
              </Typography>
            </Box>

            <ActionPackages agentTemplate={agentTemplate} />
            <MCPServers agentTemplate={agentTemplate} />

            <Box mt="$20">
              <Accordion
                title="Advanced"
                description="Optional agent settings such as description, feedback recipients, and other preferences."
              >
                <AgentDescription agentTemplate={agentTemplate} />
              </Accordion>
            </Box>
          </Box>

          <ActionSticky>
            <Button type="submit" round loading={isPending}>
              Deploy Agent
            </Button>
            <Button type="button" variant="secondary" round onClick={onCancel} loading={isPending}>
              Cancel
            </Button>
          </ActionSticky>
        </Form>
      </FormProvider>
    </Container>
  );
};
