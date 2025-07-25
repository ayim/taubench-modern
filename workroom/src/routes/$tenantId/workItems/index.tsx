import { Box } from '@sema4ai/components';
import { createFileRoute } from '@tanstack/react-router';
import { listWorkItemsQueryOptions } from '~/queries/workItems';
import WorkItemsTable from './components/WorkItemsTable';

export const Route = createFileRoute('/$tenantId/workItems/')({
  loader: async ({ context: { queryClient, agentAPIClient }, params: { tenantId } }) => {
    const workItems = await queryClient.ensureQueryData(
      listWorkItemsQueryOptions({
        agentAPIClient,
        tenantId,
      }),
    );
    return { workItems: workItems as any };
  },
  component: WorkItems,
});

function WorkItems() {
  return (
    <div className="h-full overflow-hidden">
      <div className="mx-12 my-5">
        <div className="flex flex-col h-full overflow-auto">
          <Box className="border border-solid bg-white border-[#CDCDCD] rounded-[10px] p-4 flex-grow mb-8">
            <Box className="mt-2">
              <Box className="flex justify-between flex-row gap-2 mb-4">
                <h1 className="text-lg font-bold">Work Items</h1>
              </Box>
              <WorkItemsTable />
            </Box>
          </Box>
        </div>
      </div>
    </div>
  );
}
