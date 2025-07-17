import { FC, useEffect, useMemo, useState } from 'react';
import {
  Box,
  Table,
  Column,
  usePagination,
  Input,
  SortDirection,
  SkeletonLoader,
  TableSkeleton,
} from '@sema4ai/components';
import { IconSearch } from '@sema4ai/icons';
import RowItem from './WorkerAgentsRowItem';
import { useParams } from '@tanstack/react-router';
import { getChatAPIClient } from '~/lib/chatAPIclient';
import { AgentAPIClient } from '~/lib/AgentAPIClient';
import { Agent } from '~/types';
import { WorkItemStatus } from '@sema4ai/agent-components';

interface IAgentData {
  id: string;
  name: string;
  state: string;
  documentType: string;
  needsAttention: (string | null | undefined)[];
  failed: (string | null | undefined)[];
  inQueue: (string | null | undefined)[];
  processing: (string | null | undefined)[];
  totalProcessed: (string | null | undefined)[];
}

type Props = {
  agents: Agent[];
  agentAPIClient: AgentAPIClient;
};

// Mapping statuses to work item categories
const statusCategoryMapping = {
  needsAttention: ['RETRY_REQUIRED'],
  failed: ['FAILED'],
  inQueue: ['NEW'],
  processing: ['IN_PROGRESS', 'USER_COLLABORATION_NEEDED', 'REQUIRES_FURTHER_REVIEW'],
  totalProcessed: ['SUCCESS', 'COMPLETED_WITH_MANUAL_INTERVENTION'],
};

const WorkerAgentsTable: FC<Props> = ({ agents, agentAPIClient }) => {
  const { tenantId } = useParams({ from: '/$tenantId/agents/' });

  const [search, setSearch] = useState<string>('');
  const [sort, onSort] = useState<[string, SortDirection] | null>(['id', 'asc']);
  const pageSize = 5;
  const [agentData, setAgentData] = useState<IAgentData[] | null>(null);

  const apiClient = useMemo(() => {
    return getChatAPIClient(tenantId || '', agentAPIClient);
  }, [agentAPIClient, tenantId]);

  useEffect(() => {
    const fetchWorkItemsForAgents = async () => {
      const agentPromises = agents.map(async (agent) => {
        try {
          const workItems = await apiClient.getWorkItems({ agent_id: agent.id });

          const needsAttention = workItems
            .filter((item) => statusCategoryMapping.needsAttention.includes(item.status as WorkItemStatus))
            .map((item) => item.id);

          const failed = workItems
            .filter((item) => statusCategoryMapping.failed.includes(item.status as WorkItemStatus))
            .map((item) => item.id);

          const inQueue = workItems
            .filter((item) => statusCategoryMapping.inQueue.includes(item.status as WorkItemStatus))
            .map((item) => item.id);

          const processing = workItems
            .filter((item) => statusCategoryMapping.processing.includes(item.status as WorkItemStatus))
            .map((item) => item.id);

          const totalProcessed = workItems
            .filter((item) => statusCategoryMapping.totalProcessed.includes(item.status as WorkItemStatus))
            .map((item) => item.id);

          return {
            id: agent.id,
            name: agent.name,
            state: 'Ready',
            documentType: agent?.metadata?.worker_config?.document_type || 'Unknown',
            needsAttention,
            failed,
            inQueue,
            processing,
            totalProcessed,
          };
        } catch (error) {
          console.error(`Failed to fetch work items for agent ${agent.name}`, error);

          // Return a "Failed" agent entry in case of an error
          return {
            id: agent.id,
            name: agent.name,
            state: 'Failed',
            documentType: agent?.metadata?.worker_config?.document_type || 'Unknown',
            needsAttention: [],
            failed: [],
            inQueue: [],
            processing: [],
            totalProcessed: [],
          };
        }
      });

      // Waiting for all promises to resolve
      const updatedAgents = await Promise.all(agentPromises);

      setAgentData(updatedAgents);
    };

    fetchWorkItemsForAgents();
  }, [agents, apiClient]);

  // Filter logic
  const filteredData = useMemo(() => {
    if (!agentData) return []; // Return empty array if agentData is undefined or null
    if (!search.trim()) return agentData; // Return all data if search is empty

    return agentData.filter(
      (row) =>
        row.name.toLowerCase().includes(search.toLowerCase()) ||
        row.documentType.toLowerCase().includes(search.toLowerCase()) ||
        row.state.toLowerCase().includes(search.toLowerCase()),
    );
  }, [search, agentData]);

  // Sort logic
  const sortedData = useMemo(() => {
    if (!filteredData || !sort) return filteredData;
    const [sortKey, sortDirection] = sort;

    return filteredData.slice().sort((a, b) => {
      const compareA = a[sortKey as keyof IAgentData];
      const compareB = b[sortKey as keyof IAgentData];

      if (sortDirection === 'asc') return compareA > compareB ? 1 : -1;
      return compareA < compareB ? 1 : -1;
    });
  }, [filteredData, sort]);

  // Pagination logic
  const { from, to, paginationProps, setFrom } = usePagination({
    total: sortedData.length || 0,
    pageSize,
  });

  const paginatedData = useMemo(() => sortedData?.slice(from, to) || [], [sortedData, from, to]);

  const columns: Column[] = [
    { id: 'name', title: 'Name', sortable: true },
    { id: 'state', title: 'State', sortable: true },
    { id: 'documentType', title: 'Document Type', sortable: true },
    { id: 'needsAttention', title: 'WI Needing Attention', sortable: true },
    { id: 'failed', title: 'Failed WI', sortable: true },
    { id: 'inQueue', title: 'In Queue WI', sortable: true },
    { id: 'processing', title: 'Processing WI', sortable: true },
    { id: 'totalProcessed', title: 'Total Processed WI', sortable: true },
  ];

  return (
    <Box width="100%">
      <Box width="100%" className="flex items-end justify-between">
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

      {agentData ? (
        <Table
          className="mt-4"
          columns={columns}
          data={paginatedData as IAgentData[]}
          sort={sort}
          onSort={onSort}
          row={RowItem}
          rowProps={{
            tenantId,
            columns,
          }}
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

export default WorkerAgentsTable;
