import { createFileRoute } from '@tanstack/react-router';
import { Box, Tabs, Typography } from '@sema4ai/components';
import { useState, useCallback, useMemo } from 'react';
import ConversationalAgentsTable from './components/ConversationalAgentsTable';
import WorkerAgentsTable from './components/WorkerAgentsTable';
import { getListAgentsQueryOptions } from '~/queries/agents';
import { isConversationalAgent, isWorkerAgent } from '~/utils';

export const Route = createFileRoute('/$tenantId/agents/')({
  loader: async ({ context: { queryClient, agentAPIClient }, params: { tenantId } }) => {
    const agents = await queryClient.ensureQueryData(
      getListAgentsQueryOptions({
        agentAPIClient,
        tenantId,
      }),
    );
    return { agents };
  },
  component: Agent,
});

function Agent() {
  const { agents } = Route.useLoaderData();
  const { agentAPIClient } = Route.useRouteContext();
  const conversationalAgents = useMemo(() => agents.filter((agent) => isConversationalAgent(agent)), [agents]);
  const workerAgents = useMemo(() => agents.filter((agent) => isWorkerAgent(agent)), [agents]);

  const [tabIndex, setTabindex] = useState<number>(0);

  const handleTabChange = useCallback((index: number) => {
    setTabindex(index);
  }, []);

  return (
    <div className="h-full overflow-x-hidden">
      <div className="mx-12 my-10">
        <div className="flex flex-col h-full overflow-auto">
          <header className="text-center">
            <div className="flex items-center justify-center gap-2 !mb-2 h-11">
              <img src="/svg/IconAgentsPage.svg" className="h-full" />
              <Typography
                lineHeight="29px"
                fontFamily="Heldane Display"
                fontWeight="500"
                as="h1"
                className="text-[2.5rem] "
              >
                Agents
              </Typography>
            </div>

            <p className="text-sm">Browse and select which Agent you would like to work with below.</p>
          </header>

          <Box className="border border-solid bg-white border-[#CDCDCD] rounded-[10px] p-4 flex-grow my-8">
            <Box className="mt-2">
              <Tabs className="document-tabs" activeTab={tabIndex} setActiveTab={handleTabChange}>
                <Tabs.Tab>Conversational Agents</Tabs.Tab>
                <Tabs.Tab>Worker Agents</Tabs.Tab>
              </Tabs>
              {tabIndex === 0 && <ConversationalAgentsTable agents={conversationalAgents} />}
              {tabIndex === 1 && <WorkerAgentsTable agents={workerAgents} agentAPIClient={agentAPIClient} />}
            </Box>
          </Box>
        </div>
      </div>
    </div>
  );
}

export default Agent;
