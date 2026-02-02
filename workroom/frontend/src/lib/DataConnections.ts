import { DataConnection } from '@sema4ai/data-interface';
import { exhaustiveCheck } from '@sema4ai/shared-utils';

export const getGeneralDataConnectionDetails = (dataConnection: DataConnection): Record<string, string> => {
  switch (dataConnection.engine) {
    case 'postgres':
    case 'pgvector':
    case 'redshift':
    case 'mysql':
    case 'mssql':
    case 'timescaledb':
      return {
        host: dataConnection.configuration.host,
        database: dataConnection.configuration.database,
        user: dataConnection.configuration.user,
      };
    case 'oracle':
      return {
        host: dataConnection.configuration.host,
        service_name: dataConnection.configuration.service_name,
        user: dataConnection.configuration.user,
      };
    case 'bigquery':
      return {
        project_id: dataConnection.configuration.project_id,
        dataset: dataConnection.configuration.dataset,
      };
    case 'databricks':
      return {
        hostname: dataConnection.configuration.server_hostname,
        catalog: dataConnection.configuration.catalog ?? 'Default',
      };
    case 'confluence':
      return {
        api_base: dataConnection.configuration.api_base,
      };
    case 'snowflake': {
      const { configuration } = dataConnection;
      const account = (() => {
        if (configuration.credential_type === 'linked') {
          return 'Linked Account';
        }
        if ('account' in configuration) {
          return configuration.account;
        }
        return 'Linked Account';
      })();

      return {
        account,
        warehouse: configuration.warehouse,
      };
    }
    case 'slack':
    case 'salesforce':
    case 'sema4_knowledge_base':
      return {};
    default:
      return exhaustiveCheck(dataConnection);
  }
};
