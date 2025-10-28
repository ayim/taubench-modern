import { FC } from 'react';
import { Box } from '@sema4ai/components';

import { useDataConnectionsQuery } from '../../../../../../queries';
import { SelectControlled } from '../../../../../../common/form/SelectControlled';
import { DataConnectionIcon } from '../../../../../DataConnection/components/DataConnectionIcon';

type Props = {
  errorMessage?: string;
};

export const DataConnectionSelect: FC<Props> = ({ errorMessage }) => {
  const { data: dataConnections = [] } = useDataConnectionsQuery({});

  return (
    <SelectControlled
      name="dataConnectionId"
      disabled={dataConnections.length === 0}
      items={dataConnections.map((dataConnection) => ({
        label: dataConnection.name,
        value: dataConnection.id,
      }))}
      explicitError={errorMessage}
      renderItem={({ item }) => {
        const engine = dataConnections.find((dataConnection) => dataConnection.id === item.value)?.engine;
        return (
          <Box display="flex" alignItems="center" gap="$8">
            <DataConnectionIcon engine={engine || ''} />
            {item.label}
          </Box>
        );
      }}
    />
  );
};
