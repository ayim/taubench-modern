import {
  Box,
  Column,
  Input,
  SkeletonLoader,
  SortDirection,
  Table,
  TableSkeleton,
  usePagination,
} from '@sema4ai/components';
import { IconSearch } from '@sema4ai/icons';
import { FC, useEffect, useMemo, useState } from 'react';
import RowItem from './ConversationalAgentsRowItem';
import { useParams } from '@tanstack/react-router';
import { Agent } from '~/types';

interface IAgentData {
  id: string;
  name: string;
  state: string;
  lastInteraction: string;
}

type Props = {
  agents: Agent[];
};

const ConversationalAgentsTable: FC<Props> = ({ agents }) => {
  const { tenantId } = useParams({ from: '/tenants/$tenantId/agents/' });

  const [search, setSearch] = useState<string>('');
  const [sort, onSort] = useState<[string, SortDirection] | null>(['id', 'asc']);
  const [agentData, setAgentData] = useState<IAgentData[] | null>(null);
  const pageSize = 5;

  useEffect(() => {
    // Simulating the data fetching and transformation as in WorkerAgentsTable
    const fetchAgentData = () => {
      const mappedData = agents.map((agent: Agent) => ({
        id: agent.id,
        name: agent.name,
        state: 'Ready', // Assuming all are 'Ready' for now
        lastInteraction: new Date(agent.updated_at).toLocaleString(), // Format date
        llmVersion: agent.model && 'name' in agent.model ? agent.model.name : agent.model?.provider,
      }));

      setAgentData(mappedData);
    };

    fetchAgentData();
  }, [agents]);

  // Filter logic
  const filteredData = useMemo(() => {
    if (!agentData) return null; // Return empty array if agentData is undefined or null
    if (!search.trim()) return agentData; // Return all data if search is empty

    return agentData.filter(
      (row) =>
        row.name.toLowerCase().includes(search.toLowerCase()) || row.state.toLowerCase().includes(search.toLowerCase()),
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
    total: sortedData?.length || 0,
    pageSize,
  });

  const paginatedData = useMemo(() => sortedData?.slice(from, to) || [], [sortedData, from, to]);

  const columns: Column[] = [
    { id: 'name', title: 'Name', sortable: true },
    { id: 'state', title: 'State', sortable: true },
    { id: 'lastInteraction', title: 'Last Interaction', sortable: true },
    { id: 'actions', title: '', sortable: false },
  ];

  return (
    <Box width="100%">
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

export default ConversationalAgentsTable;
