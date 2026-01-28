import type { DataConnection } from '~/queries/dataConnections';

export type DataConnectionRowItem = Omit<DataConnection, 'configuration'> & {
  isOrganizationalConnection?: boolean;
};
