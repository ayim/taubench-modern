import { Column } from '@sema4ai/components';
import { SortRules } from '@sema4ai/layouts/dist/helpers/search';
import { WorkItemRowData } from './types';

export const workItemsTableColumns: Column[] = [
  { id: 'work_item_id', title: 'Work Item ID', resizable: true, sortable: false, minWidth: 150 },
  { id: 'work_item_name', title: 'Work Item Name', resizable: true, sortable: false, minWidth: 200 },
  { id: 'agent_name', title: 'Agent Name', resizable: true, sortable: false, minWidth: 150 },
  { id: 'status', title: 'Status', resizable: false, sortable: false, width: 170, align: 'center' as const },
  { id: 'updated_at', title: 'Last Updated', resizable: false, sortable: false, width: 130, minWidth: 130, align: 'center' as const },
  { id: 'actions', title: '', resizable: false, sortable: false, width: 80, align: 'center' as const },
];

export const workItemsSortRules: SortRules<WorkItemRowData> = {
  work_item_id: { type: 'string', value: (item) => item.work_item_id },
  work_item_name: { type: 'string', value: (item) => item.work_item_name },
  agent_name: { type: 'string', value: (item) => item.agent_name },
  status: { type: 'string', value: (item) => item.status },
  updated_at: { type: 'date', value: (item) => item.updated_at },
};
