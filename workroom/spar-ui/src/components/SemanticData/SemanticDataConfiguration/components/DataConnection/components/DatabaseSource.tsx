/* eslint-disable jsx-a11y/anchor-is-valid */
import { Box, Button, Dialog, Link, Typography } from '@sema4ai/components';
import { useFormContext } from 'react-hook-form';
import { useContext, useState } from 'react';
import { IconChevronDown, IconLoading } from '@sema4ai/icons';

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
  const [showInspectionMismatches, setShowInspectionMismatches] = useState(false);

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

        <DataConnectionSelect />
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

        {error && (
          <Typography color="content.error" mt="$12">
            {error}
          </Typography>
        )}

        {isLoading ? (
          <Box display="flex" alignItems="center" gap="$8" pt="$16">
            <IconLoading /> <Typography>Validating connection...</Typography>
          </Box>
        ) : null}

        {inspectionResult?.inspectionMismatches ? (
          <Box mt="$24">
            <Link
              as="button"
              type="button"
              variant="secondary"
              onClick={() => setShowInspectionMismatches(!showInspectionMismatches)}
              iconAfter={IconChevronDown}
            >
              {showInspectionMismatches ? 'Hide' : 'Show'} Missing Tables and Columns
            </Link>
            {showInspectionMismatches && (
              <Box mt="$12" backgroundColor="background.panels" borderRadius="$16" p="$16" borderColor="border.subtle">
                {inspectionResult.inspectionMismatches.map((mismatch) => (
                  <Box key={mismatch.table}>
                    <Typography variant="body-medium" mb="$4">
                      • {mismatch.table}
                    </Typography>
                    {mismatch.columns.map((column) => (
                      <Typography variant="body-medium" pl="$12" mb="$4">
                        • {column}
                      </Typography>
                    ))}
                  </Box>
                ))}
              </Box>
            )}
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
