import { Box, ChatInput, ListSkeleton, SkeletonLoader } from '@sema4ai/components';
import { Chat } from '@sema4ai/spar-ui';
import { createFileRoute } from '@tanstack/react-router';
import { useWorkItemQuery } from '~/queries/workItems';

import { Sidebar } from '~/components/Sidebar';

export const Route = createFileRoute('/tenants/$tenantId/worker/$agentId/$workItemId')({
  component: RouteComponent,
});

function RouteComponent() {
  const { agentId, tenantId, workItemId } = Route.useParams();
  const { data: workItem } = useWorkItemQuery({ tenantId, workItemId });

  const threadId = workItem?.thread_id;

  if (!threadId) {
    return (
      <Sidebar name="workitems-chat">
        <Box height="100%" display="flex" flexDirection="column" justifyContent="space-between" p="$20">
          <SkeletonLoader skeleton={ListSkeleton} loading />
          <ChatInput disabled>
            <ChatInput.Field />
            <ChatInput.Actions />
          </ChatInput>
        </Box>
      </Sidebar>
    );
  }

  return (
    <Sidebar name="workitems-chat">
      <Chat agentId={agentId} threadId={threadId} />
    </Sidebar>
  );
}
