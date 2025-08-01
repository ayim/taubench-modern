import {
  Box,
  Checkbox,
  Column,
  Input,
  SkeletonLoader,
  SortDirection,
  Table,
  TableSkeleton,
  usePagination,
} from '@sema4ai/components';
import { IconSearch } from '@sema4ai/icons';
import { FC, useMemo, useState, useCallback } from 'react';
import { useParams, useRouteContext } from '@tanstack/react-router';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { WorkItem } from '~/types';
import { WorkItemsRowItem, WorkItemsRowItemProps } from './WorkItemsRowItem';
import WorkItemsActions from './WorkItemsActions';
import { useRefreshWorkItems, listWorkItemsQueryOptions } from '~/queries/workItems';
import { getListAgentsQueryOptions } from '~/queries/agents';

type Props = {
  // Remove workItems from props since we'll use the query directly
};

const WorkItemsTable: FC<Props> = () => {
  const { tenantId } = useParams({ from: '/$tenantId/workItems/' });
  const { agentAPIClient } = useRouteContext({ from: '/$tenantId' });
  const queryClient = useQueryClient();

  // Use the query directly instead of receiving workItems as props
  const { data: workItemsResponse, isLoading } = useQuery(
    listWorkItemsQueryOptions({
      tenantId,
      agentAPIClient,
    }),
  );

  const { data: agentsResponse = [] } = useQuery(
    getListAgentsQueryOptions({
      tenantId,
      agentAPIClient,
    }),
  );

  const mapAgentsById = useMemo(() => {
    return agentsResponse.reduce(
      (acc, agent) => {
        acc[agent.id] = agent;
        return acc;
      },
      {} as Record<string, Exclude<typeof agentsResponse, undefined>[number]>,
    );
  }, [agentsResponse]);

  // Extract the work items from the response and cast to the correct type
  const workItems = useMemo(
    () =>
      ((Array.isArray(workItemsResponse) ? workItemsResponse : workItemsResponse?.records || []) as WorkItem[]).map(
        (workItem) => {
          const agentName = workItem.agent_id
            ? (mapAgentsById[workItem.agent_id]?.name ?? workItem.agent_id)
            : workItem.agent_id;

          return {
            ...workItem,
            agent_name: agentName,
          };
        },
      ),
    [workItemsResponse, mapAgentsById],
  );

  const [search, setSearch] = useState<string>('');
  const [sort, onSort] = useState<[string, SortDirection] | null>(['created_at', 'desc']);
  const [selectedItems, setSelectedItems] = useState<string[]>([]);
  const [hasStaleData] = useState(true);
  const [isRestarting, setIsRestarting] = useState(false);
  const pageSize = 10;

  const refreshWorkItems = useRefreshWorkItems();
  const isSyncing = refreshWorkItems.isPending;

  // Filter logic
  const filteredData = useMemo(() => {
    if (!workItems) return [];
    if (!search.trim()) return workItems;

    return workItems.filter(
      (row) =>
        row.work_item_id.toLowerCase().includes(search.toLowerCase()) ||
        (row.status && row.status.toLowerCase().includes(search.toLowerCase())) ||
        (row.agent_name && row.agent_name.toLowerCase().includes(search.toLowerCase())),
    );
  }, [search, workItems]);

  // Sort logic
  const sortedData = useMemo(() => {
    if (!filteredData || !sort) return filteredData;
    const [sortKey, sortDirection] = sort;

    return filteredData.slice().sort((a, b) => {
      const compareA = a[sortKey as keyof WorkItem];
      const compareB = b[sortKey as keyof WorkItem];

      if (sortDirection === 'asc') return (compareA || '') > (compareB || '') ? 1 : -1;
      return (compareA || '') < (compareB || '') ? 1 : -1;
    });
  }, [filteredData, sort]);

  // Pagination logic
  const { from, to, paginationProps, setFrom } = usePagination({
    total: sortedData?.length || 0,
    pageSize,
  });

  const paginatedData = useMemo(() => sortedData?.slice(from, to) || [], [sortedData, from, to]);

  // Select all functionality
  const allWorkItemIds = useMemo(() => paginatedData.map((item) => item.work_item_id), [paginatedData]);
  const allSelected = useMemo(
    () => allWorkItemIds.length > 0 && allWorkItemIds.every((id) => selectedItems.includes(id)),
    [allWorkItemIds, selectedItems],
  );
  const someSelected = useMemo(
    () => selectedItems.length > 0 && selectedItems.length < allWorkItemIds.length,
    [selectedItems, allWorkItemIds],
  );

  const handleSelectAll = useCallback(
    (checked: boolean) => {
      if (checked) {
        setSelectedItems(allWorkItemIds);
      } else {
        setSelectedItems([]);
      }
    },
    [allWorkItemIds],
  );

  const columns: Column[] = [
    { id: 'row-selection', title: '', sortable: false },
    { id: 'status', title: 'Status', sortable: true },
    { id: 'name', title: 'Work Item Name', sortable: true },
    { id: 'agent_name', title: 'Agent Name', sortable: true },
    { id: 'view-work-item', title: 'View', sortable: false },
    // { id: 'stage', title: 'Stage', sortable: true },
    // { id: 'state', title: 'State', sortable: true },
    { id: 'created_at', title: 'Date Created', sortable: true },
    { id: 'updated_at', title: 'Last Updated', sortable: true },
    { id: 'actions', title: '', sortable: false },
  ];

  const handleRestartWorkItems = useCallback(async () => {
    if (selectedItems.length === 0) {
      console.log('No work items selected');
      return;
    }

    setIsRestarting(true);
    try {
      console.log(`Restarting ${selectedItems.length} work items...`);

      // process each work item sequentially to avoid stressing the backend
      for (const workItemId of selectedItems) {
        try {
          await agentAPIClient.agentFetch(tenantId, 'post', '/api/v2/work-items/{work_item_id}/restart', {
            params: {
              path: {
                work_item_id: workItemId,
              },
            },
            errorMsg: 'Failed to restart work item',
            silent: false,
          });
          console.log(`Successfully restarted work item: ${workItemId}`);
        } catch (error) {
          console.error(`Failed to restart work item ${workItemId}:`, error);
          // continue with the next work item even if one fails
        }
      }

      // clear selected items after successful restart
      setSelectedItems([]);

      // Use the hook that's now at the top level
      refreshWorkItems.mutate({ tenantId, agentAPIClient });

      console.log('Refetching work items...');
    } catch (error) {
      console.error('Error restarting work items:', error);
    } finally {
      setIsRestarting(false);
    }
  }, [selectedItems, tenantId, agentAPIClient, refreshWorkItems]);

  const handleCompleteWorkItem = useCallback(
    async (workItemId: string) => {
      try {
        await agentAPIClient.agentFetch(tenantId, 'post', '/api/v2/work-items/{work_item_id}/complete', {
          params: {
            path: {
              work_item_id: workItemId,
            },
          },
          errorMsg: 'Failed to complete work item',
          silent: false,
        });
      } catch (error) {
        console.error('Error completing work item:', error);
      }

      // Use the hook that's now at the top level
      refreshWorkItems.mutate({ tenantId, agentAPIClient });
    },
    [tenantId, agentAPIClient, refreshWorkItems],
  );

  const handleRestartWorkItem = useCallback(
    async (workItemId: string) => {
      try {
        await agentAPIClient.agentFetch(tenantId, 'post', '/api/v2/work-items/{work_item_id}/restart', {
          params: {
            path: {
              work_item_id: workItemId,
            },
          },
          errorMsg: 'Failed to restart work item',
          silent: false,
        });
        console.log(`Successfully restarted work item: ${workItemId}`);
      } catch (error) {
        console.error(`Failed to restart work item ${workItemId}:`, error);
      }

      // Refresh the data without triggering sync state
      try {
        const updatedData = await agentAPIClient.agentFetch(tenantId, 'get', '/api/v2/work-items/', {
          params: {},
          errorMsg: 'Failed to refresh work items after restart',
          silent: true,
        });

        // Update the query cache directly without using the mutation
        queryClient.setQueryData([tenantId, 'work-items'], updatedData);
      } catch (error) {
        console.error('Error refreshing data after restart:', error);
      }
    },
    [tenantId, agentAPIClient, queryClient],
  );

  const handleSync = useCallback(async () => {
    console.log('Syncing work items...');
    try {
      await refreshWorkItems.mutateAsync({ tenantId, agentAPIClient });
      console.log('Work items synced successfully');
    } catch (error) {
      console.error('Error syncing work items:', error);
    }
  }, [refreshWorkItems, tenantId, agentAPIClient]);

  const rowProps: WorkItemsRowItemProps = useMemo(
    () => ({
      selectedRows: selectedItems,
      setSelectedRows: setSelectedItems,
      workItems: workItems,
      tenantId,
      isRestarting,
      handleCompleteWorkItem,
      handleRestartWorkItem,
    }),
    [selectedItems, workItems, tenantId, isRestarting, handleCompleteWorkItem, handleRestartWorkItem],
  );

  return (
    <Box width="100%">
      {/* Header with search and action buttons */}
      <Box className="flex justify-between flex-row gap-2 mb-4">
        <Box width="20%">
          <Input
            className="!mr-[1px] focus:outline-none focus:ring-1 focus:ring-inset focus:ring-[#5BA497]"
            iconLeft={IconSearch}
            placeholder="Search"
            value={search}
            onChange={(event) => {
              setSearch(event.target.value);
              setFrom(0);
            }}
            aria-label="Search"
          />
        </Box>

        <WorkItemsActions
          selectedRows={selectedItems}
          handleRestartClick={handleRestartWorkItems}
          handleSyncClick={handleSync}
          hasStaleData={hasStaleData}
          isRestarting={isRestarting}
          isSyncing={isSyncing}
        />
      </Box>

      {/* Selection info and select all checkbox */}
      <Box mb={2} className="flex items-center gap-4">
        {/* Select all checkbox - always in the same position */}
        {paginatedData.length > 0 && (
          <Box className="flex items-center gap-2">
            <Checkbox
              checked={allSelected}
              indeterminate={someSelected}
              disabled={isRestarting}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => handleSelectAll(e.target.checked)}
              aria-label="Select all work items"
              data-testid="select-all-checkbox"
            />
            <span className="text-sm text-gray-600">{allSelected ? 'Deselect all' : 'Select all'}</span>
          </Box>
        )}
      </Box>

      {/* Selection info - appears after checkbox when items are selected */}
      {selectedItems.length > 0 && (
        <Box p={2} backgroundColor="background.subtle" borderRadius="md" className="mt-4">
          <span className="text-sm p-2">
            Selected {selectedItems.length} of {sortedData?.length || 0} work items
          </span>
        </Box>
      )}

      {!isLoading && workItems ? (
        <Table
          className="mt-4"
          columns={columns}
          data={paginatedData}
          sort={sort}
          onSort={onSort}
          row={WorkItemsRowItem}
          rowProps={rowProps}
          layout="auto"
          rowCount="all"
        />
      ) : (
        <SkeletonLoader skeleton={TableSkeleton} loading />
      )}

      {sortedData && sortedData.length > pageSize && <Table.Pagination {...paginationProps} />}
    </Box>
  );
};

export default WorkItemsTable;
