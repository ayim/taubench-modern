import { Button, Input, Typography } from '@sema4ai/components';
import { IconArrowRight, IconSearch } from '@sema4ai/icons';
import { createFileRoute, useNavigate, useParams } from '@tanstack/react-router';
import { FC, useState, ChangeEvent, useEffect, useMemo } from 'react';
import { getListAgentsQueryOptions } from '~/queries/agents';
import { Agent } from '~/types';
import { isConversationalAgent, isWorkerAgent } from '~/utils';

const AgentCard: FC<{ agent: Agent }> = ({ agent: { id, name, description, action_packages, version } }) => {
  const actionPackageCount = action_packages?.length ?? 0;
  const { tenantId } = useParams({ from: '/$tenantId' });
  const navigate = useNavigate();
  return (
    <div className="flex flex-col justify-between p-4 pb-3 rounded-xl hover:shadow-md border border-solid border-gray-200 overflow-hidden text-sm h-full bg-white min-h-[150px] select-none">
      <div>
        <div className="flex flex-row justify-between">
          <h3 className="font-bold text-base">{name}</h3>
        </div>
        <p className="text-gray-600 line-clamp-4 mt-2">{description}</p>
      </div>
      <div className="flex items-center justify-between text-xs mt-4 h-8 gap-2">
        <div className="flex items-center text-xs gap-1">
          <div>
            <span className="text-gray-500">{`${actionPackageCount} ${
              actionPackageCount === 1 ? 'action package' : 'action packages'
            }`}</span>
            {version && <span className="text-gray-500 ml-2">Version {version}</span>}
          </div>
        </div>
        <div className="flex items-center gap-1">
          <Button
            size="small"
            round
            onClick={
              () => navigate({ to: '/$tenantId/$agentId', params: { tenantId, agentId: id ?? '' } }) // TODO: v2 integration, remove this nullish coalescing
            }
            iconAfter={IconArrowRight}
          >
            Chat
          </Button>
        </div>
      </div>
    </div>
  );
};

export const Route = createFileRoute('/$tenantId/home/')({
  loader: async ({ context: { queryClient, agentAPIClient }, params: { tenantId } }) => {
    const agents = await queryClient.ensureQueryData(
      getListAgentsQueryOptions({
        agentAPIClient,
        tenantId,
      }),
    );
    return { agents };
  },
  component: HomePage,
});

function HomePage() {
  const { agents } = Route.useLoaderData();
  const [myAgents, setMyAgents] = useState<Agent[]>(agents ?? []);
  const [searchText, setSearchText] = useState<string>('');
  useEffect(() => {
    if (searchText === '') {
      setMyAgents(agents);
    } else {
      setMyAgents(
        agents.filter(
          (agent) =>
            agent.name.toLowerCase().includes(searchText.toLowerCase()) ||
            agent.description.toLowerCase().includes(searchText.toLowerCase()),
        ),
      );
    }
  }, [searchText, agents]);
  const conversationalAgents = useMemo(() => myAgents.filter((agent) => isConversationalAgent(agent)), [myAgents]);
  const workerAgents = useMemo(() => myAgents.filter((agent) => isWorkerAgent(agent)), [myAgents]);
  return (
    <div className="h-full overflow-x-hidden">
      <div className="mx-12 my-10">
        <div className="flex flex-col h-full overflow-auto">
          <div className="flex items-center my-auto relative px-2 py-8">
            <div className="w-full mx-auto">
              <div className="flex flex-col items-center mx-auto w-fit">
                <img src="/svg/IconWorkroom.svg" className="h-16 mb-3" />
                <Typography
                  lineHeight="29px"
                  fontFamily="Heldane Display"
                  fontWeight="500"
                  as="h1"
                  className="text-[2.5rem] !mb-2.5"
                >
                  Welcome to Work Room
                </Typography>
                <p className="text-sm">Where teams go to work with Enterprise AI Agents</p>
                <div className="relative my-6 w-full px-2">
                  <Input
                    variant="ghost"
                    label=""
                    className="!bg-white !min-h-8 placeholder:text-center"
                    iconLeft={IconSearch}
                    placeholder="Search by name or description"
                    onChange={(e: ChangeEvent<HTMLInputElement>) => {
                      setSearchText(e?.target?.value ?? '');
                    }}
                    value={searchText}
                    round
                  />
                </div>
              </div>

              <div className="mt-8 max-w-5xl mx-auto">
                {conversationalAgents.length > 0 && (
                  <div className="flex justify-center mt-8 flex-col w-full">
                    <div className="flex items-center gap-2">
                      <img className="h-[22px]" src="/svg/IconConversationalAgent.svg" alt="Agents" />
                      <p className="text-lg font-bold">Conversational Agents</p>
                    </div>
                    <div className="grid my-6 lg:grid-cols-3 gap-x-3 gap-y-4">
                      {conversationalAgents.map((agent) => (
                        <div key={agent.id}>
                          <AgentCard agent={agent} />
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {workerAgents.length > 0 && (
                  <div className="flex justify-center mt-8 flex-col w-full">
                    <div className="flex items-center gap-2">
                      <img className="h-[22px]" src="/svg/IconWorkerAgent.svg" alt="Agents" />
                      <p className="text-lg font-bold">Worker Agents</p>
                    </div>
                    <div className="grid my-6 lg:grid-cols-3 gap-x-3 gap-y-4">
                      {workerAgents.map((agent) => (
                        <div key={agent.id}>
                          <AgentCard agent={agent} />
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
