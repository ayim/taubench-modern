/* eslint-disable camelcase */
import { Badge, Box, EmptyState, Progress, Table, TableRowProps, Typography } from '@sema4ai/components';
import { TableWithFilter } from '@sema4ai/layouts';
import { SortRules } from '@sema4ai/layouts/dist/helpers/search';
import { FC, useCallback, useMemo } from 'react';

import { IconChevronRight } from '@sema4ai/icons';
import { ButtonLink } from '../../common/link/ButtonLink';
import { AgentWorkItemsSummary, useWorkItemsSummaryQuery, WorkItemStatus } from '../../queries/workItems';
import { useSparUIContext } from '../../api/context';
import { WORK_ITEM_STATUS_CONFIG, STATUS_ORDER } from '../../constants/workItemStatus';

type WorkItemsOverviewRowData = AgentWorkItemsSummary & {
  total: number;
};

const WorkItemsOverviewRow: FC<TableRowProps<WorkItemsOverviewRowData>> = ({ rowData }) => {
  const { sparAPIClient } = useSparUIContext();

  const handleAgentClick = useCallback(() => {
    const { agent_id } = rowData;

    sparAPIClient.navigate({
      to: '/workItem/$agentId',
      params: { agentId: agent_id },
    });
  }, [sparAPIClient, rowData]);

  const handleStatusClick = useCallback(
    (status: WorkItemStatus) => {
      const { agent_id } = rowData;
      sparAPIClient.navigate({
        to: '/workItems/list',
        params: {},
        search: { agent: agent_id, status },
      });
    },
    [sparAPIClient, rowData],
  );

  return (
    <Table.Row>
      <Table.Cell>
        <Box
          as="button"
          onClick={handleAgentClick}
          style={{ cursor: 'pointer', textAlign: 'left', background: 'none', border: 'none' }}
        >
          <Typography fontWeight="medium">{rowData.agent_name}</Typography>
        </Box>
      </Table.Cell>
      <>
        {STATUS_ORDER.map((status) => {
          const count = rowData.work_items_status_counts[status] || 0;
          const config = WORK_ITEM_STATUS_CONFIG[status];
          return (
            <Table.Cell key={status} align="center">
              {count > 0 ? (
                <Badge
                  forwardedAs="button"
                  onClick={() => handleStatusClick(status)}
                  variant={config.variant}
                  label={String(count)}
                  icon={config.icon}
                  iconColor={config.iconColor}
                  iconAfter={IconChevronRight}
                  iconVisible
                />
              ) : (
                <Typography color="content.subtle.light">0</Typography>
              )}
            </Table.Cell>
          );
        })}
      </>
      <Table.Cell align="center">
        <Typography fontWeight="medium">{rowData.total}</Typography>
      </Table.Cell>
    </Table.Row>
  );
};

export const WorkItemsOverview: FC = () => {
  const { data: summaryData = [], isLoading } = useWorkItemsSummaryQuery({}, { refetchInterval: 5000 });

  const tableData = useMemo<WorkItemsOverviewRowData[]>(
    () =>
      summaryData.map(
        (agent): WorkItemsOverviewRowData => ({
          ...agent,
          total: STATUS_ORDER.reduce((sum, status) => sum + (agent.work_items_status_counts[status] ?? 0), 0),
        }),
      ),
    [summaryData],
  );

  const columns = useMemo(
    () => [
      {
        id: 'agent_name',
        title: 'Agent',
        minWidth: 200,
        sortable: true,
      },
      ...STATUS_ORDER.map((status) => ({
        id: status,
        title: WORK_ITEM_STATUS_CONFIG[status].label,
        width: 130,
        align: 'center' as const,
        sortable: true,
      })),
      {
        id: 'total',
        title: 'Total',
        width: 100,
        align: 'center' as const,
        sortable: true,
      },
    ],
    [],
  );

  const searchRules = useMemo(
    () => ({
      agent_name: {
        value: (item: WorkItemsOverviewRowData) => item.agent_name,
      },
    }),
    [],
  );

  const sortRules = useMemo<SortRules<WorkItemsOverviewRowData>>(
    () => ({
      agent_name: {
        type: 'string',
        value: (item) => item.agent_name,
      },
      ...Object.fromEntries(
        STATUS_ORDER.map((status) => [
          status,
          {
            type: 'number',
            value: (item: WorkItemsOverviewRowData) => item.work_items_status_counts[status] || 0,
          },
        ]),
      ),
      total: {
        type: 'number',
        value: (item) => item.total,
      },
    }),
    [],
  );

  if (isLoading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" height="100%">
        <Progress />
      </Box>
    );
  }

  if (tableData.length === 0) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" height="100%">
        <EmptyState
          title="No agents with work items found"
          description="No agents with work items found."
          action={
            <ButtonLink to="/home" params={{}} round>
              Reset Filters
            </ButtonLink>
          }
        >
          <Typography>No agents with work items found</Typography>
        </EmptyState>
      </Box>
    );
  }

  return (
    <Box display="flex" flexDirection="column" gap={4} pt="$8">
      <Box>
        <TableWithFilter<WorkItemsOverviewRowData, never>
          id="work-items-overview-table"
          columns={columns}
          data={tableData}
          row={WorkItemsOverviewRow}
          searchRules={searchRules}
          sortRules={sortRules}
          label={{ singular: 'agent', plural: 'agents' }}
        />
      </Box>
    </Box>
  );
};
