import { createFileRoute, redirect } from '@tanstack/react-router';
import { getPreferenceKey, getUserPreferenceId, removeUserPreferenceId } from '~/utils';

export const Route = createFileRoute('/tenants/$tenantId/worker/$agentId/')({
  loader: async ({ context: { agentAPIClient }, params: { agentId, tenantId } }) => {
    const agentResult = await agentAPIClient.agentFetch(tenantId, 'get', '/api/v2/agents/{aid}', {
      params: { path: { aid: agentId } },
    });

    if (!agentResult.success) {
      throw redirect({
        to: '/tenants/$tenantId/home',
        params: { tenantId },
      });
    }

    /**
     * 1. Redirect to user preferred workItem, if it exists
     */
    const prefearedWorkItemId = getUserPreferenceId(getPreferenceKey({ agentId }));
    if (prefearedWorkItemId) {
      let workItemExists = false;

      try {
        const thread = await agentAPIClient.agentFetch(tenantId, 'get', '/api/v2/work-items/{work_item_id}', {
          params: { path: { work_item_id: prefearedWorkItemId } },
          silent: true,
        });

        workItemExists = !!thread;
      } catch (e) {
        console.error('Failed redirecting to preferred workitem', e);
        removeUserPreferenceId(getPreferenceKey({ agentId }));
      }

      if (workItemExists) {
        throw redirect({
          to: '/tenants/$tenantId/worker/$agentId/$workItemId',
          params: {
            tenantId,
            agentId,
            workItemId: prefearedWorkItemId,
          },
        });
      }
    }

    /**
     * 2. If no prefered workItem set, redirect to the first workItem in list
     */
    const workItemsResponse = await agentAPIClient.agentFetch(tenantId, 'get', '/api/v2/work-items/', {
      params: {
        query: {
          limit: 1,
          agent_id: agentId,
        },
      },
    });

    if (!workItemsResponse.success) {
      throw redirect({
        to: '/tenants/$tenantId/worker/$agentId',
        params: { tenantId, agentId },
      });
    }
    const firstWorkItem = workItemsResponse.data.records[0];

    if (firstWorkItem) {
      const threadId = firstWorkItem.thread_id;
      if (threadId) {
        throw redirect({
          to: '/tenants/$tenantId/worker/$agentId/$workItemId/$threadId',
          params: {
            agentId,
            tenantId,
            threadId,
            workItemId: firstWorkItem.work_item_id,
          },
        });
      } else {
        throw redirect({
          to: '/tenants/$tenantId/worker/$agentId/$workItemId',
          params: {
            agentId,
            tenantId,
            workItemId: firstWorkItem.work_item_id,
          },
        });
      }
    }
  },
});
