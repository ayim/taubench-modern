import { Box } from '@sema4ai/components';
import { AgentIcon } from '@sema4ai/layouts';
import { styled } from '@sema4ai/theme';
import { useParams, useRouteContext } from '@tanstack/react-router';
import { AgentContextMenu, sortByCreatedAtDesc } from '@sema4ai/spar-ui';
import { useAgentsQuery } from '@sema4ai/spar-ui/queries';

import { RouterSideNavigationLink } from '~/components/RouterLink';
import { isConversationalAgent } from '~/utils';
import { ADMINISTRATION_ACCESS_PERMISSION } from '~/lib/userPermissions';

const AgentsMenuContainer = styled(Box)`
  border-top: 1px solid ${({ theme }) => theme.colors.border.subtle.color};
  padding-top: ${({ theme }) => theme.space.$12};
  margin-top: ${({ theme }) => theme.space.$12};
`;

export const AgentsMenu = () => {
  const { tenantId } = useParams({ from: '/tenants/$tenantId' });
  const { permissions } = useRouteContext({ from: '/tenants/$tenantId' });
  const { data: agents } = useAgentsQuery({});

  if (!agents) {
    return null;
  }

  const sortedAgents = [...agents].sort(sortByCreatedAtDesc);

  return (
    <AgentsMenuContainer display="flex" flexDirection="column">
      {sortedAgents.map((agent) => {
        if (!agent.id) {
          return null;
        }

        const isConversational = isConversationalAgent(agent);
        const mode = isConversational ? 'conversational' : 'worker';
        const route = isConversational
          ? '/tenants/$tenantId/conversational/$agentId'
          : '/tenants/$tenantId/worker/$agentId';

        return (
          <RouterSideNavigationLink
            icon={<AgentIcon mode={mode} size="s" identifier={agent.id} />}
            key={agent.id}
            to={route}
            params={{ tenantId, agentId: agent.id }}
            action={permissions[ADMINISTRATION_ACCESS_PERMISSION] ? <AgentContextMenu agent={agent} /> : null}
          >
            {agent.name}
          </RouterSideNavigationLink>
        );
      })}
    </AgentsMenuContainer>
  );
};
