/* eslint-disable jsx-a11y/anchor-is-valid */
import { Box, Button, Dialog, Link, Typography } from '@sema4ai/components';
import { useFormContext } from 'react-hook-form';
import { useContext, useState } from 'react';
import { IconLoading } from '@sema4ai/icons';

import { DataConnection, useSupportedSemanticDataEnginesQuery } from '../../../../../../queries';
import { EXTERNAL_LINKS } from '../../../../../../lib/constants';
import {
  ConfigurationStep,
  ConfigurationStepView,
  DataConnectionFormContext,
  DataConnectionFormSchema,
} from '../../form';
import { DataConnectionSelect } from './DataConnectionSelect';
import { CreateDataConnection } from '../../../../../DataConnection/DataConnectionConfiguration/components/Create';

export const DatabaseSource: ConfigurationStepView = ({ onClose, setActiveStep }) => {
  const {
    databaseInspectionState: { isLoading, error, inspectionResult },
  } = useContext(DataConnectionFormContext);
  const [isCreatingNewDataConnection, setIsCreatingNewDataConnection] = useState(false);
  const { data: supportedSemanticDataEngines = [], isLoading: isLoadingSupportedSemanticDataEngines } =
    useSupportedSemanticDataEnginesQuery({});

  const { setValue, watch } = useFormContext<DataConnectionFormSchema>();
  const dataConnectionId = watch('dataConnectionId');

  const onNewDataConnectionClose = (dataConnection?: DataConnection) => {
    setIsCreatingNewDataConnection(false);
    if (dataConnection) {
      setValue('dataConnectionId', dataConnection.id);
    }
  };

  return (
    <>
      <Dialog.Content maxWidth={768}>
        <Typography variant="display-medium" mb="$12">
          Connect to Your Database
        </Typography>
        <Typography variant="body-large" color="content.subtle" mb="$40">
          Connect a database so your agent can securely access the data it needs. This connection is the first step
          toward building data models and enabling the agent to work with your information.{' '}
          <Link href={EXTERNAL_LINKS.DATA_ACCESS} target="_blank">
            Learn more
          </Link>
        </Typography>

        <DataConnectionSelect errorMessage={error} />
        <Typography color="content.subtle.light" mt="$12">
          Use one of existing data connections or{' '}
          <Link
            as="button"
            type="button"
            onClick={() => setIsCreatingNewDataConnection(true)}
            disabled={isLoadingSupportedSemanticDataEngines}
          >
            Create New
          </Link>
        </Typography>

        {isLoading ? (
          <Box display="flex" alignItems="center" gap="$8" pt="$16">
            <IconLoading /> <Typography>Validating connection...</Typography>
          </Box>
        ) : null}
      </Dialog.Content>

      <Dialog.Actions>
        <Button
          onClick={() => setActiveStep(ConfigurationStep.DataSelection)}
          disabled={!dataConnectionId || !inspectionResult || inspectionResult.tables.length === 0}
          round
        >
          Continue
        </Button>
        <Button variant="secondary" onClick={onClose} round>
          Cancel
        </Button>
      </Dialog.Actions>
      {isCreatingNewDataConnection && (
        <CreateDataConnection supportedEngines={supportedSemanticDataEngines} onClose={onNewDataConnectionClose} />
      )}
    </>
  );
};
