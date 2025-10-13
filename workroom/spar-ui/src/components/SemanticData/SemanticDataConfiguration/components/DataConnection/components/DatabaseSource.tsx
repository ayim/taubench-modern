import { Box, Button, Dialog, Link, Typography } from '@sema4ai/components';
import { useFormContext } from 'react-hook-form';
import { useContext, useEffect } from 'react';

import { Link as RouterLink } from '../../../../../../common/link';
import { EXTERNAL_LINKS } from '../../../../../../lib/constants';
import {
  useDataConnectionDatabaseInspectMutation,
  useDataConnectionsQuery,
} from '../../../../../../queries/dataConnections';
import { SelectControlled } from '../../../../../../common/form/SelectControlled';
import {
  ConfigurationStep,
  ConfigurationStepView,
  DataConnectionFormContext,
  DataConnectionFormSchema,
} from '../../form';
import { DataConnectionIcon } from '../../../../../DataConnection/components/DataConnectionIcon';

export const DatabaseSource: ConfigurationStepView = ({ onClose, setActiveStep }) => {
  const { inspectedDataTables, setInspectedDataTables } = useContext(DataConnectionFormContext);
  const { data: dataConnections = [] } = useDataConnectionsQuery({});

  const { watch } = useFormContext<DataConnectionFormSchema>();
  const dataConnectionId = watch('dataConnectionId');

  const {
    mutateAsync: inspectDataConnection,
    error: errorInspectingDataConnection,
    isPending: isLoadingInspectingDataConnection,
  } = useDataConnectionDatabaseInspectMutation({});

  useEffect(() => {
    const inspect = async () => {
      if (dataConnectionId) {
        const result = await inspectDataConnection({ dataConnectionId });

        if (result) {
          setInspectedDataTables(result);
        }
      }
    };
    inspect();
  }, [dataConnectionId]);

  const errorMessage = errorInspectingDataConnection ? errorInspectingDataConnection.message : undefined;

  return (
    <>
      <Dialog.Content maxWidth={768}>
        <Typography variant="display-large" mb="$12">
          Connect to Your Database
        </Typography>
        <Typography variant="body-large" color="content.subtle" mb="$40">
          Connect a database so your agent can securely access the data it needs. This connection is the first step
          toward building data models and enabling the agent to work with your information.{' '}
          <Link href={EXTERNAL_LINKS.DATA_ACCESS} target="_blank">
            Learn more
          </Link>
        </Typography>

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

        <Typography color="content.subtle.light" mt="$12">
          Use one of existing data connections or{' '}
          <RouterLink to="/data-connections/create" params={{}}>
            Create New
          </RouterLink>
        </Typography>
      </Dialog.Content>

      <Dialog.Actions>
        <Button
          onClick={() => setActiveStep(ConfigurationStep.DataSelection)}
          disabled={!dataConnectionId || inspectedDataTables.length === 0}
          loading={isLoadingInspectingDataConnection}
          round
        >
          Continue
        </Button>
        <Button variant="secondary" onClick={onClose} round>
          Cancel
        </Button>
      </Dialog.Actions>
    </>
  );
};
