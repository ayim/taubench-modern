import { Box, Button, Dialog, Link, Typography } from '@sema4ai/components';
import { useFormContext } from 'react-hook-form';
import { useContext } from 'react';
import { IconLoading } from '@sema4ai/icons';

import { Link as RouterLink } from '../../../../../../common/link';
import { EXTERNAL_LINKS } from '../../../../../../lib/constants';
import {
  ConfigurationStep,
  ConfigurationStepView,
  DataConnectionFormContext,
  DataConnectionFormSchema,
  DataSourceType,
} from '../../form';
import { DataConnectionSelect } from './DataConnectionSelect';

type Props = {
  setDataSourceType: (dataSourceType: DataSourceType | undefined) => void;
};

export const DatabaseSource: ConfigurationStepView<Props> = ({ onClose, setActiveStep, setDataSourceType }) => {
  const {
    databaseInspectionState: { isLoading, error, inspectionResult },
  } = useContext(DataConnectionFormContext);

  const { watch } = useFormContext<DataConnectionFormSchema>();
  const dataConnectionId = watch('dataConnectionId');

  const onResetSourceSelection = () => {
    setDataSourceType(undefined);
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
          <RouterLink to="/data-connections/create" params={{}}>
            Create New
          </RouterLink>
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
        <Button variant="secondary" align="secondary" onClick={onResetSourceSelection} round>
          Back
        </Button>
      </Dialog.Actions>
    </>
  );
};
