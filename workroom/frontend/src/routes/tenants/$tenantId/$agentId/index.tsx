import { exhaustiveCheck } from '@sema4ai/robocloud-shared-utils';
import { createFileRoute, redirect } from '@tanstack/react-router';
import { z } from 'zod';
import { AgentNotFound } from '~/components/AgentNotFound';
import { NotFoundRoute } from '~/components/NotFoundRoute';

// Because the base route can be either /home /workItems /uuid (for agents)
// We want to distinguish a "page not found" from "agent not found"
// We use the UUID check as a way to determine whether the intent was to access an agent
const ERROR_VALUE_IN_PATH_IS_NOT_UUID = 'Invalid UUID';

export const Route = createFileRoute('/tenants/$tenantId/$agentId/')({
  loader: async ({ context: { agentAPIClient }, params: { agentId, tenantId } }) => {
    // This entire logic is to ensure backward compatibility with older URLs in Work Room that did not prefix the agent type in the URL.
    const agentIdValidation = z.string().uuid().safeParse(agentId);

    if (!agentIdValidation.success) {
      throw new Error(ERROR_VALUE_IN_PATH_IS_NOT_UUID);
    }

    const agentResult = await agentAPIClient.agentFetch(tenantId, 'get', '/api/v2/agents/{aid}', {
      params: { path: { aid: agentId } },
    });

    if (!agentResult.success) {
      throw new Error('Agent not found');
    }

    const agentMode = agentResult.data.mode;

    switch (agentMode) {
      case 'worker':
        throw redirect({
          to: '/tenants/$tenantId/worker/$agentId',
          params: { tenantId, agentId },
        });
      case 'conversational':
        throw redirect({
          to: '/tenants/$tenantId/conversational/$agentId',
          params: { tenantId, agentId },
        });
      default:
        exhaustiveCheck(agentMode);
    }
  },
  errorComponent: ({ error }) => {
    if (error.message === ERROR_VALUE_IN_PATH_IS_NOT_UUID) {
      return <NotFoundRoute />;
    }
    return <AgentNotFound />;
  },
});
