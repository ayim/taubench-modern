import type { DataSourceItem } from './DataConnectionRow';

// TODO: Added eslint-disable due to failing tests
export const DataAccessActions = {
  handleCreate: (): void => {
    // eslint-disable-next-line no-alert
    alert('Create new data connection - CRUD operations to be implemented');
  },

  handleEdit: (item: DataSourceItem): void => {
    // eslint-disable-next-line no-alert
    alert(`Edit data source: ${item.name} (ID: ${item.id}) - CRUD operations to be implemented`);
  },

  handleDelete: (item: DataSourceItem): void => {
    // eslint-disable-next-line no-alert
    alert(`Delete data source: ${item.name} (ID: ${item.id}) - CRUD operations to be implemented`);
  },
};
