import { FC, useEffect, useMemo } from 'react';
import { Box } from '@sema4ai/components';
import { useFormContext } from 'react-hook-form';

import { useDataConnectionsQuery, useSupportedSemanticDataEnginesQuery } from '../../../../../../queries';
import { SelectControlled } from '../../../../../../common/form/SelectControlled';
import { DataConnectionIcon } from '../../../../../DataConnection/components/DataConnectionIcon';
import { DataConnectionFormSchema } from '../../form';

type Props = {
  errorMessage?: string;
};

export const DataConnectionSelect: FC<Props> = ({ errorMessage }) => {
  const { data: dataConnections = [] } = useDataConnectionsQuery({});
  const { setValue, watch } = useFormContext<DataConnectionFormSchema>();
  const { data: supportedSemanticDataEngines = [], isLoading: isLoadingSupportedSemanticDataEngines } =
    useSupportedSemanticDataEnginesQuery({});
  const { dataConnectionId, dataConnectionName } = watch();

  // Make default data connection selection based on data connection name from imported Data Model
  useEffect(() => {
    if (!dataConnectionId && dataConnectionName && dataConnections.length > 0) {
      const dataConnectionMatch = dataConnections.find((dataConnection) => dataConnection.name === dataConnectionName);

      if (dataConnectionMatch) {
        setValue('dataConnectionId', dataConnectionMatch.id);
      }
    }
  }, [dataConnections, dataConnectionId, dataConnectionName]);

  const supportedDataConnections = useMemo(() => {
    if (!supportedSemanticDataEngines) {
      return [];
    }
    return dataConnections.filter((dataConnection) => supportedSemanticDataEngines.includes(dataConnection.engine));
  }, [dataConnections, supportedSemanticDataEngines]);

  return (
    <SelectControlled
      name="dataConnectionId"
      disabled={dataConnections.length === 0 || isLoadingSupportedSemanticDataEngines}
      items={supportedDataConnections.map((dataConnection) => ({
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
