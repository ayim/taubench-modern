import { Column } from '@sema4ai/components';
import { SortRules } from '@sema4ai/layouts/dist/helpers/search';
import { WorkItemRowData } from './types';

export const workItemsTableColumns: Column[] = [
  { id: 'work_item_id', title: 'ID', resizable: true, sortable: false, minWidth: 150 },
  { id: 'work_item_name', title: 'Name', resizable: true, sortable: false, minWidth: 200 },
  { id: 'agent_name', title: 'Agent', resizable: true, sortable: false, minWidth: 150 },
  { id: 'status', title: 'Status', resizable: false, sortable: false, width: 170 },
  { id: 'updated_at', title: 'Last Updated', resizable: false, sortable: false, width: 130, minWidth: 130 },
  { id: 'actions', title: '', resizable: false, sortable: false, required: true, width: 80 },
];

export const workItemsSortRules: SortRules<WorkItemRowData> = {
  work_item_id: { type: 'string', value: (item) => item.work_item_id },
  work_item_name: { type: 'string', value: (item) => item.work_item_name },
  agent_name: { type: 'string', value: (item) => item.agent_name },
  status: { type: 'string', value: (item) => item.status },
  updated_at: { type: 'date', value: (item) => item.updated_at },
};
