import { FilterGroup } from '@sema4ai/components';
import { WorkItem } from '../../queries';
import { WORK_ITEM_STATUS_CONFIG, WORK_ITEM_STATUS_VALUES } from '../../constants/workItemStatus';
import { WorkItemRowData } from './types';

export const buildAgentMaps = (agents: Array<{ id?: string | null; name?: string | null }>) => {
  const agentsById = new Map<string, string>();
  const agentsByName = new Map<string, string>();
  
  agents.forEach((agent) => {
    if (agent.id && agent.name) {
      agentsById.set(agent.id, agent.name);
      agentsByName.set(agent.name, agent.id);
    }
  });
  
  return { agentsById, agentsByName };
};

export const transformWorkItemsWithAgentNames = (
  workItems: WorkItem[],
  agentsById: Map<string, string>
): WorkItemRowData[] => {
  return workItems.map((item) => ({
    ...item,
    agent_name: item.agent_id ? agentsById.get(item.agent_id) ?? item.agent_id : item.agent_id,
  }));
};

export const buildFilterOptions = (
  agentsByName: Map<string, string>
): Record<'status' | 'agent_name', FilterGroup> => {
  return {
    status: {
      label: 'Status',
      searchable: true,
      options: WORK_ITEM_STATUS_VALUES.map((status) => ({
        label: WORK_ITEM_STATUS_CONFIG[status]?.label || status,
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
  };
};

export const calculatePagination = (
  currentPage: number,
  pageSize: number,
  itemsCount: number,
  hasNextPage: boolean
) => {
  const estimatedTotal = hasNextPage 
    ? currentPage * pageSize + pageSize + 1 
    : currentPage * pageSize + itemsCount;
  
  return { estimatedTotal };
};

