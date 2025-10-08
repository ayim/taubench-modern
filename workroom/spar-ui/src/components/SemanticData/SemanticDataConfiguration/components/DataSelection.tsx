import { Box, Button, Dialog, Link, Typography } from '@sema4ai/components';
import { useFormContext } from 'react-hook-form';

import { EXTERNAL_LINKS } from '../../../../lib/constants';
import { InputControlled } from '../../../../common/form/InputControlled';
import { ConfigurationStepView, DataConnectionFormSchema } from './form';
import { DataSelector } from './DataSelector';
import { useDataConnectionInspectQuery } from '../../../../queries/dataConnections';

export const DataSelection: ConfigurationStepView = ({ onClose }) => {
  const { watch } = useFormContext<DataConnectionFormSchema>();

  const { dataConnectionId, dataSelection } = watch();
  const { data: tables = [] } = useDataConnectionInspectQuery({ dataConnectionId });

  return (
    <>
      <Dialog.Content>
        <Box maxWidth={768} margin="0 auto">
          <Typography variant="display-large" mb="$12">
            Select Data
          </Typography>
          <Typography variant="body-large" color="content.subtle" mb="$40">
            Select the tables and columns you want your agent to use. Add a brief explanation of the structure and
            business meaning so the agent can interpret the data correctly.{' '}
            <Link href={EXTERNAL_LINKS.DATA_ACCESS} target="_blank">
              Learn mores
            </Link>
          </Typography>

          <InputControlled
            fieldName="description"
            label="Business Context"
            rows={4}
            autoGrow
            placeholder="Paste or write here anything that helps us understand the business context of your data."
          />

          <Typography my="$16">Select data</Typography>
          <DataSelector data={tables} />
        </Box>
      </Dialog.Content>

      <Dialog.Actions>
        <Button disabled={dataSelection.length === 0} type="submit" round>
          Continue
        </Button>
        <Button variant="secondary" onClick={onClose} round>
          Cancel
        </Button>
      </Dialog.Actions>
    </>
  );
};
