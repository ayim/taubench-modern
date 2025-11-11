import { Box, Typography } from '@sema4ai/components';
import { AgentIcon } from '@sema4ai/layouts';
import { useParams, useRouteContext } from '@tanstack/react-router';
import { AgentContextMenu, sortByCreatedAtDesc } from '@sema4ai/spar-ui';
import { useAgentsQuery } from '@sema4ai/spar-ui/queries';

import { RouterSideNavigationLink } from '~/components/RouterLink';
import { isConversationalAgent, isWorkerAgent } from '~/utils';
import { ADMINISTRATION_ACCESS_PERMISSION } from '~/lib/userPermissions';

export const AgentsMenu = () => {
  const { tenantId } = useParams({ from: '/tenants/$tenantId' });
  const { permissions } = useRouteContext({ from: '/tenants/$tenantId' });
  const { data: agents } = useAgentsQuery({});

  if (!agents) {
    return null;
  }

  const conversationalAgents = agents.filter(isConversationalAgent).sort(sortByCreatedAtDesc);

  const workerAgents = agents.filter(isWorkerAgent).sort(sortByCreatedAtDesc);

  return (
    <Box display="flex" flexDirection="column" pt="$8">
      <Box mb="$8">
        <Typography variant="body-small" fontWeight="bold">
          Conversational Agents
        </Typography>
      </Box>

      {conversationalAgents.map((agent) => {
        return (
          agent.id && (
            <RouterSideNavigationLink
              icon={<AgentIcon mode="conversational" size="s" identifier={agent.id || ''} />}
              key={agent.id}
              to="/tenants/$tenantId/conversational/$agentId"
              params={{ tenantId, agentId: agent.id }}
              action={permissions[ADMINISTRATION_ACCESS_PERMISSION] ? <AgentContextMenu agent={agent} /> : null}
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
              icon={<AgentIcon mode="worker" size="s" identifier={agent.id || ''} />}
              key={agent.id}
              to="/tenants/$tenantId/worker/$agentId"
              params={{ tenantId, agentId: agent.id }}
              action={permissions[ADMINISTRATION_ACCESS_PERMISSION] ? <AgentContextMenu agent={agent} /> : null}
            >
              {agent.name}
            </RouterSideNavigationLink>
          )
        );
      })}
    </Box>
  );
};
