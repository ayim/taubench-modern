import { useState, useMemo, useCallback } from 'react';
import { createFileRoute, Link, useRouteContext } from '@tanstack/react-router';
import {
  Box,
  Button,
  Filter,
  FilterGroup,
  Grid as GridBase,
  ToggleInputButton,
  Typography,
  Progress,
} from '@sema4ai/components';
import { AgentCard, AgentIcon } from '@sema4ai/layouts';
import { IconArrowRight, IconSearch } from '@sema4ai/icons';
import { AgentContextMenu, AgentDeploymentForm, sortByCreatedAtDesc } from '@sema4ai/spar-ui';
import { SearchRules, fuzzyDataSearcher } from '@sema4ai/robocloud-ui-utils';
import { AgentPackageInspectionResponse, useAgentsQuery } from '@sema4ai/spar-ui/queries';
import { components } from '@sema4ai/agent-server-interface';
import { styled } from '@sema4ai/theme';
import { IconAgents } from '@sema4ai/icons/logos';

import { Page } from '~/components/layout/Page';
import { isConversationalAgent, isWorkerAgent } from '~/utils';
import { EmptyView } from '~/components/EmptyView';
import { ADMINISTRATION_ACCESS_PERMISSION } from '~/lib/userPermissions';
import { CreateAgentDialog } from './components/CreateAgentDialog';

export const Route = createFileRoute('/tenants/$tenantId/home/')({
  component: HomePage,
});

const agentSearchRules: SearchRules<components['schemas']['AgentCompat']> = { name: { value: (item) => item.name } };

const Grid = styled(GridBase)`
  grid-auto-rows: 1fr;
`;

function HomePage() {
  const { tenantId } = Route.useParams();
  const { data: allAgents = [], isLoading } = useAgentsQuery({});
  const { permissions } = useRouteContext({ from: '/tenants/$tenantId' });
  const [search, setSearch] = useState<string>('');
  const [agentPackageUploadData, setAgentPackageUploadData] = useState<{
    agentTemplate: NonNullable<AgentPackageInspectionResponse>;
    agentPackage: File;
  } | null>(null);
  const [filters, setFilters] = useState({
    type: [] as string[],
  });

  // eslint-disable-next-line react-hooks/exhaustive-deps
  const onAgentSearch = useCallback(fuzzyDataSearcher(agentSearchRules, allAgents), [allAgents]);

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
        buttonVariant="ghost-subtle"
        round
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
    return onAgentSearch(search)
      .filter((agent) => {
        return (
          filters.type.length === 0 ||
          (filters.type.includes('conversational') && isConversationalAgent(agent)) ||
          (filters.type.includes('worker') && isWorkerAgent(agent))
        );
      })
      .sort(sortByCreatedAtDesc);
  }, [search, filters, onAgentSearch]);

  if (isLoading) {
    return <Progress variant="page" />;
  }

  if (agentPackageUploadData) {
    return (
      <Box height="100%">
        <Box px="$40" py="$64" maxWidth={768} margin="0 auto">
          <AgentDeploymentForm {...agentPackageUploadData} onCancel={() => setAgentPackageUploadData(null)} />
        </Box>
      </Box>
    );
  }

  if (allAgents.length === 0) {
    return (
      <Box as="section">
        <EmptyView
          title="No Agents Yet"
          description="Agents will appear here once someone deploys one and shares it with you."
          illustration="agents"
          docsLink="MAIN_WORKROOM_HELP"
          action={
            permissions[ADMINISTRATION_ACCESS_PERMISSION] ? (
              <CreateAgentDialog setAgentPackageUploadData={setAgentPackageUploadData} />
            ) : null
          }
        />
      </Box>
    );
  }

  return (
    <Page
      title="Sema4.ai Agents"
      icon={IconAgents}
      actions={
        permissions[ADMINISTRATION_ACCESS_PERMISSION] ? (
          <CreateAgentDialog setAgentPackageUploadData={setAgentPackageUploadData} />
        ) : null
      }
    >
      <Filter
        contentBefore={searchInput}
        options={filterOptions}
        values={filters}
        onChange={setFilters}
        moreLabel="Filter"
      />

      <Grid columns={[1, 2, 2, 3, 4]} gap="$16" mt="$20" mb="$32">
        {filteredAgents.map((agent) => {
          return (
            agent.id && (
              <Link
                key={agent.id}
                to={
                  isConversationalAgent(agent)
                    ? '/tenants/$tenantId/conversational/$agentId'
                    : '/tenants/$tenantId/worker/$agentId'
                }
                params={{ tenantId, agentId: agent.id }}
              >
                <AgentCard
                  variant="thumbnail"
                  illustration={
                    <AgentIcon
                      mode={isConversationalAgent(agent) ? 'conversational' : 'worker'}
                      size="m"
                      identifier={agent.id || ''}
                    />
                  }
                  version={agent.version}
                  title={agent.name}
                  description={agent.description}
                >
                  <AgentCard.Footer>
                    <Box display="flex" justifyContent="flex-end" gap="$4">
                      {permissions[ADMINISTRATION_ACCESS_PERMISSION] && <AgentContextMenu agent={agent} />}
                      <Button size="small" icon={IconArrowRight} aria-label="publish" round />
                    </Box>
                  </AgentCard.Footer>
                </AgentCard>
              </Link>
            )
          );
        })}
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
    </Page>
  );
}
