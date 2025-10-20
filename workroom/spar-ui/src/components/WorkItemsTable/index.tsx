import { Box, Button, FilterGroup, useSnackbar } from '@sema4ai/components';
import { IconRefresh } from '@sema4ai/icons';
import { TableWithFilter } from '@sema4ai/layouts';
import { FC, useCallback, useContext, useMemo, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';

import { SparUIContext } from '../../api/context';
import { useAgentsQuery, useWorkItemsQuery, WorkItemStatus } from '../../queries';
import { WorkItemRowData, workitemStatusValues } from './types';
import { workItemsSortRules, workItemsTableColumns } from './columns';
import { WorkItemsTableRow } from './components/WorkItemsTableRow';
import { WorkItemsTableActions } from './components/WorkItemsTableActions';
import { snakeCaseToCamelCase } from '../../common/helpers';

const PAGE_SIZE = 50;

export const WorkItemsTable: FC = () => {
  const { addSnackbar } = useSnackbar();
  const { sparAPIClient } = useContext(SparUIContext);
  const queryClient = useQueryClient();

  const [filters, setFilters] = useState<Record<'status' | 'agent_name', string[]>>({
    status: [],
    agent_name: [],
  });
  const [page, setPage] = useState(0);
  const [selectedItems, setSelectedItems] = useState<string[]>([]);
  const [search, setSearch] = useState('');

  const { data: agents = [], refetch: refetchAgents } = useAgentsQuery({});

  const { agentsById, agentsByName } = useMemo(() => {
    const byId = new Map<string, string>();
    const byName = new Map<string, string>();

    agents.forEach((agent) => {
      if (agent.id && agent.name) {
        byId.set(agent.id, agent.name);
        byName.set(agent.name, agent.id);
      }
    });

    return { agentsById: byId, agentsByName: byName };
  }, [agents]);

  const selectedAgentId = filters.agent_name.length > 0 ? agentsByName.get(filters.agent_name[0]) : undefined;

  const { data: workItemsResponse, refetch: refetchWorkItems } = useWorkItemsQuery({
    agentId: selectedAgentId,
    workItemStatus: filters.status.length > 0 ? (filters.status as WorkItemStatus[]) : undefined,
    nameSearch: search || undefined,
    limit: PAGE_SIZE,
    offset: page * PAGE_SIZE,
  });

  const workItems = useMemo<WorkItemRowData[]>(
    () =>
      (workItemsResponse?.records ?? []).map((item) => ({
        work_item_id: item.work_item_id,
        work_item_name: item.work_item_name,
        agent_id: item.agent_id,
        status: item.status,
        updated_at: item.updated_at,
        agent_name: item.agent_id ? agentsById.get(item.agent_id) ?? item.agent_id : item.agent_id,
      })),
    [workItemsResponse?.records, agentsById],
  );

  const filterOptions = useMemo<Record<'status' | 'agent_name', FilterGroup>>(
    () => ({
      status: {
        label: 'Status',
        searchable: true,
        options: workitemStatusValues.map((status) => ({
          label: snakeCaseToCamelCase(status),
          value: status,
          itemType: 'checkbox',
        })),
      },
      agent_name: {
        label: 'Agent Name',
        searchable: true,
        options: Array.from(agentsByName.keys())
          .sort()
          .map((name) => ({
            label: name,
            value: name,
            itemType: 'radio',
          })),
      },
    }),
    [agentsByName],
  );

  const hasNextPage = workItemsResponse?.next_offset != null;
  const estimatedTotal = hasNextPage ? page * PAGE_SIZE + PAGE_SIZE + 1 : page * PAGE_SIZE + workItems.length;

  const handleRefresh = useCallback(() => {
    refetchAgents();
    refetchWorkItems();
  }, [refetchAgents, refetchWorkItems]);

  const handleSearchChange = useCallback(
    (searchValue: string) => {
      setSearch(searchValue);
      setPage(0);
      setSelectedItems([]);
    },
    [],
  );

  const handleFilterChange = useCallback(
    (newFilters: Record<string, string[]>) => {
      const typedFilters = newFilters as Record<'status' | 'agent_name', string[]>;
      setFilters(typedFilters);
      setPage(0);
      setSelectedItems([]);
    },
    [],
  );

  const handlePageChange = useCallback((newPage: number) => {
    setPage(newPage);
    setSelectedItems([]);
  }, []);

  const handleDownloadSelected = useCallback(() => {
    const selectedIndices = selectedItems.map(Number);
    const selectedWorkItems = workItems.filter((_, index) => selectedIndices.includes(index));

    if (selectedWorkItems.length === 0) {
      addSnackbar({ message: 'No items selected', variant: 'danger' });
      return;
    }

    const json = JSON.stringify(selectedWorkItems, null, 2);
    const blob = new Blob([json], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `work-items-${new Date().toISOString()}.json`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);

    addSnackbar({ message: `Downloaded ${selectedWorkItems.length} work item${selectedWorkItems.length > 1 ? 's' : ''}`, variant: 'success' });
  }, [workItems, selectedItems, addSnackbar]);

  const handleReprocessSelected = useCallback(async () => {
    const selectedIndices = selectedItems.map(Number);
    const restartableItems = workItems.filter((_, index) => selectedIndices.includes(index));

    if (restartableItems.length === 0) {
      addSnackbar({ message: 'No items can be restarted', variant: 'danger' });
      return;
    }

    const results = await Promise.allSettled(
      restartableItems.map((item) =>
        sparAPIClient.queryAgentServer('post', '/api/v2/work-items/{work_item_id}/restart', {
          params: { path: { work_item_id: item.work_item_id ?? '' } },
        }),
      ),
    );

    const succeeded = results.filter((r) => r.status === 'fulfilled' && r.value.success).length;
    const failed = results.length - succeeded;

    queryClient.invalidateQueries({ queryKey: ['work-items'] });

    if (succeeded > 0 && failed === 0) {
      addSnackbar({
        message: `Successfully restarted ${succeeded} work item${succeeded > 1 ? 's' : ''}`,
        variant: 'success',
      });
    } else if (succeeded > 0 && failed > 0) {
      addSnackbar({
        message: `Restarted ${succeeded} work item${succeeded > 1 ? 's' : ''}, ${failed} failed`,
        variant: 'danger',
      });
    } else {
      addSnackbar({ message: 'Failed to restart work items', variant: 'danger' });
    }

    setSelectedItems([]);
  }, [workItems, selectedItems, sparAPIClient, queryClient, addSnackbar]);

  return (
    <Box flexGrow={1} display="flex" flexDirection="column" gap={4} overflow="hidden" height="100%" pt="$20">
      {selectedItems.length > 0 && (
        <Box flexShrink={0}>
          <WorkItemsTableActions
            selectionCount={selectedItems.length}
            onResetSelection={() => setSelectedItems([])}
            onDownloadRaw={handleDownloadSelected}
            onReprocess={handleReprocessSelected}
          />
        </Box>
      )}
      <Box flexGrow={1} overflow="hidden">
        <TableWithFilter<WorkItemRowData, 'status' | 'agent_name', { rowData: WorkItemRowData }>
          id="work-items-table"
          columns={workItemsTableColumns}
          data={workItems}
          row={WorkItemsTableRow}
          filters={filterOptions}
          filter={filters}
          label={{ singular: 'work item', plural: 'work items' }}
          selectable
          selected={selectedItems}
          onSelect={setSelectedItems}
          sortRules={workItemsSortRules}
          page={page}
          onSearchChange={handleSearchChange}
          onFilterChange={handleFilterChange}
          onPageChange={handlePageChange}
          totalEntries={estimatedTotal}
          contentBefore={
            <Box display="flex" alignItems="center">
            <Button 
              aria-label="Refresh" 
              icon={IconRefresh} 
              variant="ghost" 
              size="small" 
              onClick={handleRefresh}
            />
            </Box>
          }
        />
      </Box>
    </Box>
  );
};
