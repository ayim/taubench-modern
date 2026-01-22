import { FC, useRef } from 'react';
import { Box, Button, Form, Link, Typography, useSnackbar } from '@sema4ai/components';
import { styled } from '@sema4ai/theme';
import { FormProvider, useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';

import { ActionSticky } from '../../common/form/StickyActions';
import { Accordion } from '../../common/Accordion';
import { EXTERNAL_LINKS } from '../../lib/constants';
import { AgentPackageInspectionResponse, useAgentsQuery, useDeployAgentFromPackageMutation } from '../../queries';
import { buildAgentDeploymentSchema, AgentDeploymentFormSchema, getDefaultValues } from './context';
import { useNavigate } from '../../hooks/useNavigate';

import { AgentName } from './components/AgentName';
import { LLM } from './components/LLM';
import { MCPServers } from './components/MCPServers';
import { ActionPackages } from './components/ActionPackages';
import { AgentDescription } from './components/AgentDescription';

type Props = {
  agentTemplate: NonNullable<AgentPackageInspectionResponse>;
  agentPackage: File;
  onCancel: () => void;
};

const Container = styled.div`
  position: relative;
  height: 100%;
`;

export const AgentDeploymentForm: FC<Props> = ({ agentTemplate, agentPackage, onCancel }) => {
  const formRef = useRef<HTMLFormElement>(null);
  const { data: allAgents = [] } = useAgentsQuery({});
  const { mutateAsync: deployAgentFromPackage, isPending } = useDeployAgentFromPackageMutation({});
  const { addSnackbar } = useSnackbar();
  const navigate = useNavigate();

  const formProps = useForm<AgentDeploymentFormSchema>({
    mode: 'onChange',
    defaultValues: getDefaultValues(agentTemplate),
    shouldUnregister: false,
    resolver: zodResolver(buildAgentDeploymentSchema({ existingAgentNames: allAgents.map((agent) => agent.name) })),
  });

  const { handleSubmit } = formProps;

  const onDeploy = handleSubmit(async (payload) => {
    deployAgentFromPackage(
      { agentTemplate, agentPackage, payload },
      {
        onSuccess: (data) => {
          addSnackbar({ message: 'Agent deployed successfully', variant: 'success' });
          if (data.agent_id) {
            navigate({ to: '/thread/$agentId', params: { agentId: data.agent_id } });
          }
        },
        onError: (error) => {
          addSnackbar({ message: error.message, variant: 'danger' });
        },
      },
    );
  });

  const containsActions =
    (agentTemplate.action_packages ?? []).length > 0 || (agentTemplate.mcp_servers ?? []).length > 0;

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

            <LLM agentTemplate={agentTemplate} />

            {containsActions && (
              <Box display="flex" flexDirection="column" gap="$4" mt="$20">
                <Typography variant="display-small" fontWeight="bold">
                  Actions & MCP servers
                </Typography>
                <Typography>
                  Provide the credentials and configuration required for actions and MCP servers so the agent can
                  successfully execute tool calls.
                </Typography>
              </Box>
            )}

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
