import { Box, Button, Filter, FilterGroup, Menu, Table, ToggleInputButton, Typography } from '@sema4ai/components';
import { IconChevronDown, IconDownloadCloud, IconRefresh, IconSearch, IconSeparator } from '@sema4ai/icons';
import { components } from '@sema4ai/agent-server-interface';
import { useQuery } from '@tanstack/react-query';
import { useParams, useRouteContext } from '@tanstack/react-router';
import { FC, useCallback, useMemo, useState } from 'react';
import { snakeCaseToCamelCase } from '~/lib/utils';
import { getListAgentsQueryOptions } from '~/queries/agents';
import { listWorkItemsQueryOptions } from '~/queries/workItems';
import { workitemsTableColumns, WorkItemsTableRow } from './WorkItemsRowItem';

type Props = {
  // Remove workItems from props since we'll use the query directly
};

const workitemStatusValues: components['schemas']['WorkItemStatus'][] = [
  'CANCELLED',
  'COMPLETED',
  'ERROR',
  'EXECUTING',
  'NEEDS_REVIEW',
  'INDETERMINATE',
  'PENDING',
  'PRECREATED',
];

const TableFilter = () => {
  const [search, setSearch] = useState<string>('');
  const [selectedStates, setSelectedStates] = useState<Record<'Status' | 'LastRun', string[]>>({
    Status: [],
    LastRun: [],
  });

  const stateOptions = useMemo<Record<'Status' | 'LastRun', FilterGroup>>(
    () => ({
      Status: {
        label: 'Status',
        searchable: true,
        options: workitemStatusValues.map((status) => ({
          label: snakeCaseToCamelCase(status),
          value: status,
          itemType: 'checkbox',
        })),
      },
      LastRun: {
        label: 'Last Run',
        searchable: false,
        options: [
          { label: '1 day', value: '1 day', itemType: 'item' },
          { label: '2 days', value: '2 days', itemType: 'item' },
          { label: '3 days', value: '3 days', itemType: 'item' },
          { label: '4 days', value: '4 days', itemType: 'item' },
        ],
        closeMenuOnItemSelect: true,
      },
    }),
    [],
  );

  return (
    <Filter
      contentBefore={
        <ToggleInputButton
          iconLeft={IconSearch}
          placeholder="Search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          aria-label="Search"
          onClear={() => setSearch('')}
          buttonVariant="ghost-subtle"
          round
        />
      }
      onChange={setSelectedStates}
      options={stateOptions}
      values={selectedStates}
    />
  );
};

const TableActions: FC<{
  selectionCount: number;
  onResetSelection: () => void;
  onReprocess?: () => void;
  onDownloadPdf?: () => void;
  onDownloadRaw?: () => void;
}> = ({ selectionCount, onResetSelection, onReprocess, onDownloadPdf, onDownloadRaw }) => {
  return (
    <Box display="flex" gap="$4" alignItems="center" px="$20" py="$8">
      <Button.Group collapse maxWidth="max-content">
        {(onDownloadPdf || onDownloadRaw) && (
          <Menu
            trigger={
              <Button round icon={IconDownloadCloud} iconAfter={IconChevronDown}>
                Download
              </Button>
            }
          >
            {onDownloadRaw && (
              <Menu.Item icon={IconDownloadCloud} onClick={onDownloadRaw}>
                Raw
              </Menu.Item>
            )}
            {onDownloadPdf && (
              <Menu.Item icon={IconDownloadCloud} onClick={onDownloadPdf}>
                PDF
              </Menu.Item>
            )}
          </Menu>
        )}
        {onReprocess && (
          <Button round icon={IconRefresh} variant="secondary" onClick={onReprocess}>
            Reproccess
          </Button>
        )}
        <Button round variant="ghost" onClick={onResetSelection}>
          Reset Selection
        </Button>
      </Button.Group>
      <IconSeparator color="border.primary" />
      <Typography pl="$12" color="content.subtle" variant="body-medium">
        {selectionCount} selected
      </Typography>
    </Box>
  );
};

const WorkItemsTable: FC<Props> = () => {
  const { tenantId } = useParams({ from: '/tenants/$tenantId' });
  const { agentAPIClient } = useRouteContext({ from: '/tenants/$tenantId' });

  const { agentId } = useParams({ strict: false });

  // Getting all workitems
  const { data: listWorkItemsResponse } = useQuery(
    listWorkItemsQueryOptions({
      tenantId,
      agentAPIClient,
      agentId,
    }),
  );

  // Getting all agents
  const { data: listAgentsResponse = [] } = useQuery(
    getListAgentsQueryOptions({
      tenantId,
      agentAPIClient,
    }),
  );

  // From agents list creating a map of agentId -> Agent
  const mapAgentsById = useMemo(() => {
    return listAgentsResponse.reduce(
      (acc, agent) => {
        acc[agent.id] = agent;
        return acc;
      },
      {} as Record<string, Exclude<typeof listAgentsResponse, undefined>[number]>,
    );
  }, [listAgentsResponse]);

  // Extract the work items from the response and adding agentName in it
  const workItems = useMemo(() => {
    return (listWorkItemsResponse?.records || []).map((workItem) => {
      const agentName = workItem.agent_id ? mapAgentsById[workItem.agent_id]?.name : workItem.agent_id;
      return {
        ...workItem,
        agent_name: agentName,
      };
    });
  }, [listWorkItemsResponse, mapAgentsById]);

  const [selectedItems, setSelectedItems] = useState<string[]>([]);
  const [resize, setResize] = useState<Record<string, number>>({});

  const getWorkItemId = useCallback((row: (typeof workItems)[number]) => row.work_item_id, []);

  return (
    <Box flexGrow={1} display="flex" flexDirection="column" gap={4} overflow="hidden" height="100%" pt="$20">
      <Box px="$16">
        <TableFilter />
      </Box>
      {selectedItems.length > 0 && (
        <TableActions
          selectionCount={selectedItems.length}
          onResetSelection={() => setSelectedItems([])}
          onDownloadPdf={() => {}}
          onDownloadRaw={() => {}}
          onReprocess={() => {}}
        />
      )}
      <Box flexGrow={1} style={{ overflowY: 'auto', overflowX: 'hidden' }} px="$16">
        <Table
          columns={workitemsTableColumns}
          data={workItems}
          selectable
          selected={selectedItems}
          onSelect={setSelectedItems}
          rowCount={workItems.length}
          resize={resize}
          onResize={setResize}
          sticky
          keyId={getWorkItemId}
          row={WorkItemsTableRow}
        />
      </Box>
      {/* <Box>Pagination</Box> */}
    </Box>
  );
};

export default WorkItemsTable;
