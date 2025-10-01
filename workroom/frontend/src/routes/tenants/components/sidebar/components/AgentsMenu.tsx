import { Box, Typography } from '@sema4ai/components';
import { AgentIcon } from '@sema4ai/layouts';
import { styled } from '@sema4ai/theme';
import { useParams } from '@tanstack/react-router';
import { AgentContextMenu } from '@sema4ai/spar-ui';
import { useAgentsQuery } from '@sema4ai/spar-ui/queries';

import { RouterSideNavigationLink } from '~/components/RouterLink';
import { isConversationalAgent, isWorkerAgent } from '~/utils';

const Placeholder = styled(Typography)`
  border: 1px dashed ${({ theme }) => theme.colors.border.primary.color};
  padding: ${({ theme }) => theme.space.$12};
  border-radius: ${({ theme }) => theme.radii.$8};
`;

export const AgentsMenu = () => {
  const { tenantId } = useParams({ from: '/tenants/$tenantId' });
  const { data: agents } = useAgentsQuery({});

  if (!agents) {
    return null;
  }

  const conversationalAgents = agents.filter(isConversationalAgent);
  const workerAgents = agents.filter(isWorkerAgent);

  return (
    <Box display="flex" flexDirection="column" pt="$8">
      <Box mb="$8">
        <Typography variant="body-small" fontWeight="bold">
          Conversational Agents
        </Typography>
      </Box>

      {agents.length === 0 && (
        <Placeholder variant="body-small" color="content.subtle.light" textAlign="center">
          Add your favorite agents that you use often.
        </Placeholder>
      )}

      {conversationalAgents.map((agent) => {
        return (
          agent.id && (
            <RouterSideNavigationLink
              icon={<AgentIcon mode="conversational" size="s" />}
              key={agent.id}
              to="/tenants/$tenantId/conversational/$agentId"
              params={{ tenantId, agentId: agent.id }}
              action={<AgentContextMenu agent={agent} />}
            >
              {agent.name}
            </RouterSideNavigationLink>
          )
        );
      })}

      {workerAgents.length ? (
        <Box mt="$16" mb="$8">
          <Typography variant="body-small" fontWeight="bold">
            Worker Agents
          </Typography>
        </Box>
      ) : undefined}

      {workerAgents.map((agent) => {
        return (
          agent.id && (
            <RouterSideNavigationLink
              icon={<AgentIcon mode="worker" size="s" />}
              key={agent.id}
              to="/tenants/$tenantId/worker/$agentId"
              params={{ tenantId, agentId: agent.id }}
              action={<AgentContextMenu agent={agent} />}
            >
              {agent.name}
            </RouterSideNavigationLink>
          )
        );
      })}
    </Box>
  );
};
