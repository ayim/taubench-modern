import { FC, useContext, useEffect, useMemo } from 'react';
import { Box, Typography } from '@sema4ai/components';
import { IconInformation } from '@sema4ai/icons';
import { useFormContext } from 'react-hook-form';

import { useDataConnectionsQuery } from '~/queries/dataConnections';
import { useSupportedSemanticDataEnginesQuery } from '~/queries/semanticData';

import { SelectControlled } from '~/components/form/SelectControlled';
import { DataConnectionIcon } from '../../../../../DataConnection/components/DataConnectionIcon';
import { getGeneralDataConnectionDetails } from '../../../../../../lib/DataConnections';
import { DataConnectionInformation } from '../../../../../DataConnection/DataConnectionInformation';
import { DataConnectionFormContext, DataConnectionFormSchema } from '../../form';

export const DataConnectionSelect: FC = () => {
  const { data: dataConnections = [] } = useDataConnectionsQuery({});
  const { setValue, watch } = useFormContext<DataConnectionFormSchema>();
  const { data: supportedSemanticDataEngines = [], isLoading: isLoadingSupportedSemanticDataEngines } =
    useSupportedSemanticDataEnginesQuery({});
  const { dataConnectionId, dataConnectionName } = watch();
  const { setDatabaseInspectionState } = useContext(DataConnectionFormContext);

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
    return dataConnections
      .filter((dataConnection) => supportedSemanticDataEngines.includes(dataConnection.engine))
      .sort((a, b) => a.name.localeCompare(b.name));
  }, [dataConnections, supportedSemanticDataEngines]);

  const onDataConnectionUpdate = () => {
    setDatabaseInspectionState({
      isLoading: true,
      error: undefined,
      inspectionResult: undefined,
      requiresInspection: true,
    });
  };

  return (
    <Box display="flex" alignItems="center" gap="$8">
      <SelectControlled
        name="dataConnectionId"
        disabled={dataConnections.length === 0 || isLoadingSupportedSemanticDataEngines}
        items={supportedDataConnections.map((dataConnection) => ({
          label: dataConnection.name,
          value: dataConnection.id,
        }))}
        renderItem={({ item }) => {
          const dataConnection = dataConnections.find((curr) => curr.id === item.value);

          if (!dataConnection) {
            return <>item.label</>;
          }

          const details = getGeneralDataConnectionDetails(dataConnection);
          const firstDetail = Object.entries(details)[0];

          return (
            <Box display="flex" alignItems="center" gap="$8" py="$4">
              <DataConnectionIcon engine={dataConnection?.engine || ''} />
              <Box display="flex" flexDirection="column">
                <Typography variant="body-medium">{item.label}</Typography>
                {firstDetail && (
                  <Typography variant="body-small" color="content.subtle.light">
                    {firstDetail[1]}
                  </Typography>
                )}
              </Box>
            </Box>
          );
        }}
      />
      {dataConnectionId && (
        <DataConnectionInformation
          dataConnectionId={dataConnectionId}
          placement="bottom-end"
          onDataConnectionUpdate={onDataConnectionUpdate}
        >
          <IconInformation color="content.subtle.light" />{' '}
        </DataConnectionInformation>
      )}
    </Box>
  );
};
