import { createFileRoute, redirect } from '@tanstack/react-router';

export const Route = createFileRoute('/tenants/$tenantId/worker/$agentId/$workItemId/')({
  loader: async ({ context: { agentAPIClient }, params: { agentId, tenantId, workItemId } }) => {
    /**
     * If workItem has threadId, redirecting to it
     */
    const workItemResponse = await agentAPIClient.agentFetch(tenantId, 'get', '/api/v2/work-items/{work_item_id}', {
      params: {
        path: {
          work_item_id: workItemId,
        },
      },
    });

    if (!workItemResponse.success) {
      throw redirect({
        to: '/tenants/$tenantId/worker/$agentId',
        params: { tenantId, agentId },
      });
    }

    const threadId = workItemResponse.data.thread_id;

    if (threadId) {
      throw redirect({
        to: '/tenants/$tenantId/worker/$agentId/$workItemId/$threadId',
        params: {
          agentId,
          tenantId,
          threadId,
          workItemId,
        },
      });
    }
  },
});
