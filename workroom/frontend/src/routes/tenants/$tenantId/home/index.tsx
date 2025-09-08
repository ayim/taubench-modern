import { useState, useMemo, useCallback } from 'react';
import { createFileRoute, Link } from '@tanstack/react-router';
import { Box, Button, Filter, FilterGroup, Grid, ToggleInputButton, Typography } from '@sema4ai/components';
import { AgentCard, AgentIcon } from '@sema4ai/layouts';
import { IconAgents } from '@sema4ai/icons/logos';
import { IconSearch } from '@sema4ai/icons';
import { SearchRules, fuzzyDataSearcher } from '@sema4ai/robocloud-ui-utils';
import { Agent } from '@sema4ai/agent-server-interface';

import { getListAgentsQueryOptions } from '~/queries/agents';
import { isConversationalAgent, isWorkerAgent } from '~/utils';
import { EmptyView } from '~/components/EmptyView';

export const Route = createFileRoute('/tenants/$tenantId/home/')({
  loader: async ({ context: { queryClient, agentAPIClient }, params: { tenantId } }) =>
    queryClient.ensureQueryData(
      getListAgentsQueryOptions({
        agentAPIClient,
        tenantId,
      }),
    ),
  component: HomePage,
});

const agentSearchRules: SearchRules<Agent> = { name: { value: (item) => item.name } };

function HomePage() {
  const { tenantId } = Route.useParams();
  const allAgents = Route.useLoaderData();
  const [search, setSearch] = useState<string>('');
  const [filters, setFilters] = useState({
    type: [] as string[],
  });

  // eslint-disable-next-line react-hooks/exhaustive-deps
  const onAgentSearch = useCallback(fuzzyDataSearcher(agentSearchRules, allAgents || []), [allAgents]);

  const filterOptions = useMemo(() => {
    return {
      type: {
        label: 'Type',
        searchable: true,
        options: [
          { label: 'Conversational', value: 'conversational', itemType: 'checkbox' },
          { label: 'Worker', value: 'worker', itemType: 'checkbox' },
        ],
      } as FilterGroup,
    };
  }, []);

  const searchInput = useMemo(() => {
    return (
      <ToggleInputButton
        aria-label="Search"
        iconLeft={IconSearch}
        value={search}
        placeholder="Search"
        onChange={(e) => setSearch(e.target.value)}
        onClear={() => setSearch('')}
      />
    );
  }, [search]);

  const onResetFilters = useCallback(() => {
    setFilters({
      type: [],
    });
    setSearch('');
  }, []);

  const filteredAgents = useMemo(() => {
    return onAgentSearch(search).filter((agent) => {
      return (
        filters.type.length === 0 ||
        (filters.type.includes('conversational') && isConversationalAgent(agent)) ||
        (filters.type.includes('worker') && isWorkerAgent(agent))
      );
    });
  }, [search, filters, onAgentSearch]);

  if (allAgents.length === 0) {
    return (
      <EmptyView
        title="No Agents Yet"
        description="Agents will appear here once someone deploys one and shares it with you."
        illustration="agents"
        docsLink="MAIN_WORKROOM_HELP"
      />
    );
  }

  return (
    <Box py="$64" px={['$16', '$16', '$40']} maxWidth={1280} mx="auto">
      <Box display="flex" gap="$16" mb="$20">
        <IconAgents size={36} />
        <Typography variant="display-large">Sema4.ai Agents</Typography>
      </Box>
      <Filter
        contentBefore={searchInput}
        options={filterOptions}
        values={filters}
        onChange={setFilters}
        moreLabel="Filter"
      />

      <Grid columns={[1, 1, 2, 3]} gap="$16" mt="$20" mb="$32">
        {filteredAgents.map((agent) => (
          <Link
            to={
              isConversationalAgent(agent)
                ? '/tenants/$tenantId/conversational/$agentId'
                : '/tenants/$tenantId/worker/$agentId'
            }
            params={{ tenantId, agentId: agent.id }}
            key={agent.id}
          >
            <AgentCard
              variant="thumbnail"
              illustration={<AgentIcon mode={isConversationalAgent(agent) ? 'conversational' : 'worker'} size="m" />}
              version={agent.version}
              title={agent.name}
              description={agent.description}
            />
          </Link>
        ))}
      </Grid>

      {!filteredAgents.length && allAgents.length && (
        <Box display="flex" flex="1" justifyContent="center" alignItems="center" maxHeight={420} flexDirection="column">
          <Typography fontWeight="bold" fontSize="$16" lineHeight="$24" textAlign="center" mb="$4">
            No results found
          </Typography>
          <Typography lineHeight="$20" mb="$24">
            There aren&apos;t any results for that query.
          </Typography>
          <Button onClick={onResetFilters} variant="secondary" round>
            Show all Agents
          </Button>
        </Box>
      )}
    </Box>
  );
}
