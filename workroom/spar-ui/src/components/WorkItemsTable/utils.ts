import qs, { IParseOptions, IStringifyOptions } from 'qs';
import { QuerySettings } from '@sema4ai/layouts';
import { FilterGroup } from '@sema4ai/components';
import { WorkItem, WorkItemStatus } from '../../queries';
import { WORK_ITEM_STATUS_CONFIG, WORK_ITEM_STATUS_VALUES } from '../../constants/workItemStatus';
import { WorkItemRowData } from './types';

const qsStringifyOptions: IStringifyOptions = {
  skipNulls: true,
  encode: false,
  arrayFormat: 'comma',
};

const qsParseOptions: IParseOptions = {
  ignoreQueryPrefix: true,
  comma: true,
};

export const parseQueryFromURL = (agentsById: Map<string, string>): Partial<QuerySettings> => {
  if (typeof window === 'undefined') return {};

  const parsed = qs.parse(window.location.search, qsParseOptions);
  const query: Partial<QuerySettings> = {};

  const statusParam = parsed.status;
  const agentId = parsed.agent;
  
  if (statusParam || agentId) {
    const filters: Record<string, string[]> = { status: [], agent_name: [] };
    
    if (statusParam) {
      const statusArray = Array.isArray(statusParam) ? statusParam : [statusParam];
      const requestedStatuses = statusArray.filter((s): s is string => typeof s === 'string');
      const validStatuses = requestedStatuses.filter((s) => WORK_ITEM_STATUS_VALUES.includes(s as WorkItemStatus));
      
      filters.status = validStatuses;
    }
    
    if (agentId && typeof agentId === 'string') {
      const agentName = agentsById.get(agentId);
      if (agentName) {
        filters.agent_name = [agentName];
      }
    }
    
    query.filters = filters;
  }

  const searchParam = parsed.search;
  if (searchParam && typeof searchParam === 'string') {
    query.search = searchParam;
  }

  const pageParam = parsed.page;
  if (pageParam) {
    const pageNum = typeof pageParam === 'string' ? parseInt(pageParam, 10) : Number(pageParam);
    if (!Number.isNaN(pageNum) && pageNum > 0) {
      query.page = pageNum;
    }
  }

  return query;
};

export const serializeQueryToURL = (query: Partial<QuerySettings>, agentsByName: Map<string, string>): string => {
  if (typeof window === 'undefined') return '';

  const params: Record<string, string | number | string[]> = {};

  if (query.filters) {
    if (query.filters.status?.length) {
      params.status = query.filters.status;
    }
    if (query.filters.agent_name?.length) {
      const agentId = agentsByName.get(query.filters.agent_name[0]);
      if (agentId) {
        params.agent = agentId;
      }
    }
  }

  if (query.search) {
    params.search = query.search;
  }
  
  if (query.page && query.page > 0) {
    params.page = query.page;
  }

  return qs.stringify(params, qsStringifyOptions);
};

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

