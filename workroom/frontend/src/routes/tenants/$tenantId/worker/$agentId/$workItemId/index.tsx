import { Box, Progress } from '@sema4ai/components';
import { Chat } from '@sema4ai/spar-ui';
import { styled } from '@sema4ai/theme';
import { createFileRoute } from '@tanstack/react-router';
import { getWorkItemQueryOptions } from '~/queries/workItems';
import { WorkItemsList } from '../components/WorkItemsList';

export const Route = createFileRoute('/tenants/$tenantId/worker/$agentId/$workItemId/')({
  loader: async ({ params, context: { agentAPIClient, queryClient } }) => {
    const { workItemId, tenantId, agentId } = params;

    const { thread_id } = await queryClient.ensureQueryData(
      getWorkItemQueryOptions({
        tenantId,
        agentAPIClient,
        workItemId,
      }),
    );

    return {
      agentId,
      threadId: thread_id,
    };
  },
  component: RouteComponent,
});

const Container = styled.section`
  display: grid;
  grid-template-rows: 1fr auto;
  height: calc(100vh - ${({ theme }) => theme.sizes.$64});
`;

function RouteComponent() {
  const { agentId, threadId } = Route.useLoaderData();

  if (!threadId) {
    return (
      <Box as="section" display="flex" justifyContent="center" alignItems="center">
        <Progress />
      </Box>
    );
  }

  return (
    <>
      <WorkItemsList />
      <Container>
        <Chat agentId={agentId} threadId={threadId} />;
      </Container>
    </>
  );
}
