export type WorkItemsNavigationContext = {
  from: 'workItems';
  tab: 'all' | 'overview';
  timestamp: number;
  agent?: string;
  status?: string;
  search?: string;
  page?: string;
};
