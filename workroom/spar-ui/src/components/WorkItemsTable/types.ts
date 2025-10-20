import { WorkItem, WorkItemStatus } from '../../queries/workItems';

export type WorkItemRowData = Pick<
  WorkItem,
  'work_item_id' | 'work_item_name' | 'agent_id' | 'status' | 'updated_at'
> & {
  agent_name: string | null | undefined;
};

export const workitemStatusValues: WorkItemStatus[] = [
  'CANCELLED',
  'COMPLETED',
  'ERROR',
  'EXECUTING',
  'NEEDS_REVIEW',
  'INDETERMINATE',
  'PENDING',
  'PRECREATED',
];

