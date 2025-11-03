import { Box, Button, useDebounce, useSnackbar } from '@sema4ai/components';
import { IconRefresh } from '@sema4ai/icons';
import { TableWithFilter } from '@sema4ai/layouts';
import { FC, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';

import { SparUIContext } from '../../api/context';
import { useAgentsQuery, useWorkItemsQuery, WorkItemStatus } from '../../queries';
import { WorkItemRowData } from './types';
import { workItemsTableColumns } from './columns';
import { WorkItemsTableRow } from './components/WorkItemsTableRow';
import { WorkItemsTableActions } from './components/WorkItemsTableActions';
import { createWorkItemsStorageKey, getStoragePrefixFromPathname } from '../../constants/workItemsStorage';
import { buildAgentMaps, transformWorkItemsWithAgentNames, buildFilterOptions, calculatePagination } from './utils';
import { usePersistedQuery } from './usePersistedQuery';

type Props = {
  onDownloadJSON: (data: unknown, options: { filename: string; addTimestamp?: boolean }) => void;
};

export const WorkItemsTable: FC<Props> = ({ onDownloadJSON }) => {
  const { addSnackbar } = useSnackbar();
  const { sparAPIClient } = useContext(SparUIContext);
  const queryClient = useQueryClient();

  const pathname = sparAPIClient.usePathnameFn();
  const storageKeyPrefix = getStoragePrefixFromPathname(pathname);

  const { data: agents = [], refetch: refetchAgents } = useAgentsQuery({});
  const { agentsById, agentsByName } = useMemo(() => buildAgentMaps(agents), [agents]);

  const [selectedItems, setSelectedItems] = useState<string[]>([]);

  const { query, setQuery } = usePersistedQuery({
    storageKey: createWorkItemsStorageKey(storageKeyPrefix, 'QUERY_SETTINGS'),
    agentsById,
    agentsByName,
    pathToNavigateTo: '/workItems/list',
  });

  const pageSize = query.size ?? 50;

  const debouncedSearch = useDebounce(query.search, 250);

  useEffect(() => {
    setSelectedItems([]);
  }, [query.filters, query.search, query.page, query.size]);

  const selectedAgentId = query.filters?.agent_name?.[0] ? agentsByName.get(query.filters.agent_name[0]) : undefined;
  const selectedStatuses = query.filters?.status?.length ? (query.filters.status as WorkItemStatus[]) : undefined;

  const { data: workItemsResponse, refetch: refetchWorkItems } = useWorkItemsQuery({
    agentId: selectedAgentId,
    workItemStatus: selectedStatuses,
    nameSearch: debouncedSearch || undefined,
    limit: pageSize,
    offset: (query.page || 0) * pageSize,
  });

  const workItems = useMemo<WorkItemRowData[]>(
    () => transformWorkItemsWithAgentNames(workItemsResponse?.records ?? [], agentsById),
    [workItemsResponse?.records, agentsById],
  );

  const filterOptions = useMemo(() => buildFilterOptions(agentsByName), [agentsByName]);

  const { estimatedTotal } = calculatePagination(
    query.page || 0,
    pageSize,
    workItems.length,
    workItemsResponse?.next_offset != null,
  );

  const handleRefresh = useCallback(() => {
    refetchAgents();
    refetchWorkItems();
  }, [refetchAgents, refetchWorkItems]);

  useEffect(() => {
    if (selectedItems.length > 0) {
      return undefined;
    }

    const intervalId = setInterval(() => {
      refetchWorkItems();
    }, 2000);

    return () => clearInterval(intervalId);
  }, [selectedItems.length, refetchWorkItems]);

  const handleDownloadSelected = useCallback(() => {
    const selectedWorkItems = workItems.filter((_, index) => selectedItems.includes(String(index)));

    if (selectedWorkItems.length === 0) {
      addSnackbar({ message: 'No items selected', variant: 'danger' });
      return;
    }

    onDownloadJSON(selectedWorkItems, {
      filename: 'work-items',
      addTimestamp: true,
    });

    const plural = selectedWorkItems.length > 1 ? 's' : '';
    addSnackbar({ message: `Downloaded ${selectedWorkItems.length} work item${plural}`, variant: 'success' });
  }, [workItems, selectedItems, onDownloadJSON, addSnackbar]);

  const handleReprocessSelected = useCallback(async () => {
    const selectedWorkItems = workItems.filter((_, index) => selectedItems.includes(String(index)));

    if (selectedWorkItems.length === 0) {
      addSnackbar({ message: 'No items can be restarted', variant: 'danger' });
      return;
    }

    const restartRequests = selectedWorkItems.map((item) =>
      sparAPIClient.queryAgentServer('post', '/api/v2/work-items/{work_item_id}/restart', {
        params: { path: { work_item_id: item.work_item_id ?? '' } },
      }),
    );

    const results = await Promise.allSettled(restartRequests);
    const succeeded = results.filter((r) => r.status === 'fulfilled' && r.value.success).length;
    const failed = results.length - succeeded;

    queryClient.invalidateQueries({ queryKey: ['work-items'] });

    if (succeeded > 0 && failed === 0) {
      const plural = succeeded > 1 ? 's' : '';
      addSnackbar({ message: `Successfully restarted ${succeeded} work item${plural}`, variant: 'success' });
    } else if (succeeded > 0 && failed > 0) {
      const plural = succeeded > 1 ? 's' : '';
      addSnackbar({
        message: `Restarted ${succeeded} work item${plural}, ${failed} failed`,
        variant: 'danger',
      });
    } else {
      addSnackbar({ message: 'Failed to restart work items', variant: 'danger' });
    }

    setSelectedItems([]);
  }, [workItems, selectedItems, sparAPIClient, queryClient, addSnackbar]);

  return (
    <Box display="flex" flexDirection="column" gap={4} pt="$8">
      {selectedItems.length > 0 && (
        <Box display="flex" alignItems="center" mb="$8">
          <WorkItemsTableActions
            selectionCount={selectedItems.length}
            onResetSelection={() => setSelectedItems([])}
            onDownloadRaw={handleDownloadSelected}
            onReprocess={handleReprocessSelected}
          />
        </Box>
      )}
      {agents.length > 0 && (
        <TableWithFilter<WorkItemRowData, 'status' | 'agent_name'>
          id="work-items-table"
          columns={workItemsTableColumns}
          data={workItems}
          row={WorkItemsTableRow}
          filters={filterOptions}
          label={{ singular: 'work item', plural: 'work items' }}
          selectable
          selected={selectedItems}
          onSelect={setSelectedItems}
          isServerSide
          query={query}
          onQuery={setQuery}
          totalEntries={estimatedTotal}
          contentBefore={
            selectedItems.length > 0 ? (
              <Box display="flex" alignItems="center">
                <Button aria-label="Refresh" icon={IconRefresh} variant="ghost" size="small" onClick={handleRefresh} />
              </Box>
            ) : undefined
          }
        />
      )}
    </Box>
  );
};
