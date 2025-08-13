import { FC } from 'react';
import { Box, Select } from '@sema4ai/components';

type DataSource = {
  id: string;
  engine: string;
  name: string;
  description?: string;
};

type Props = {
  agentTemplateDataSources: DataSource[];
};

// Mock data connections
const mockDataConnections = [
  { label: 'PostgreSQL Production', value: 'pg-prod' },
  { label: 'PostgreSQL Staging', value: 'pg-staging' },
  { label: 'MySQL Analytics', value: 'mysql-analytics' },
];

export const WizardStep5: FC<Props> = ({ agentTemplateDataSources }) => {
  return (
    <Box display="flex" flexDirection="column" gap="$24">
      <Box>
        <h3>Data Sources</h3>
        <p>Configure data source connections for your agent.</p>
      </Box>

      {agentTemplateDataSources.map((dataSource) => (
        <Box key={dataSource.id}>
          <Select
            label={`${dataSource.name} Connection`}
            description={dataSource.description || `Configure connection for ${dataSource.name}`}
            items={mockDataConnections}
            onChange={(value) => {
              console.log(`Data source ${dataSource.name} connected to:`, value);
            }}
          />
        </Box>
      ))}

      {agentTemplateDataSources.length === 0 && (
        <Box p="$24" borderRadius="$8" backgroundColor="background.subtle">
          <p>No data sources required for this agent.</p>
        </Box>
      )}
    </Box>
  );
};
