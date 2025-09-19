import { Box, ChatInput, ListSkeleton, SkeletonLoader } from '@sema4ai/components';
import { Chat } from '@sema4ai/spar-ui';
import { createFileRoute, Outlet } from '@tanstack/react-router';
import { useWorkItemQuery } from '@sema4ai/spar-ui/queries';

export const Route = createFileRoute('/tenants/$tenantId/worker/$agentId/$workItemId')({
  component: RouteComponent,
});

function RouteComponent() {
  const { agentId, workItemId } = Route.useParams();
  const { data: workItem } = useWorkItemQuery({ workItemId });

  const threadId = workItem?.thread_id;

  if (!threadId) {
    return (
      <>
        <Box as="section" height="100%" display="flex" flexDirection="column" justifyContent="space-between" p="$20">
          <SkeletonLoader skeleton={ListSkeleton} loading />
          <ChatInput disabled>
            <ChatInput.Field />
            <ChatInput.Actions />
          </ChatInput>
        </Box>
        <Outlet />
      </>
    );
  }

  return (
    <>
      <Chat agentId={agentId} threadId={threadId} />
      <Outlet />
    </>
  );
}
