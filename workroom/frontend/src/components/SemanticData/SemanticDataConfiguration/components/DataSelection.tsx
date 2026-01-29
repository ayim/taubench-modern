import { useContext } from 'react';
import { Box, Button, Dialog, Link, Typography } from '@sema4ai/components';
import { useFormContext } from 'react-hook-form';

import { InputControlled } from '~/components/form/InputControlled';
import { EXTERNAL_LINKS } from '../../../../lib/constants';
import { ConfigurationStepView, DataConnectionFormContext, DataConnectionFormSchema } from './form';
import { DataSelector } from './DataSelector';

export const DataSelection: ConfigurationStepView = ({ onClose }) => {
  const {
    databaseInspectionState: { inspectionResult },
  } = useContext(DataConnectionFormContext);
  const { watch } = useFormContext<DataConnectionFormSchema>();

  const { dataSelection } = watch();

  return (
    <>
      <Dialog.Content>
        <Box maxWidth={768} margin="0 auto">
          <Typography variant="display-medium" mb="$12">
            Select Data
          </Typography>
          <Typography variant="body-large" color="content.subtle" mb="$40">
            Select the tables/views and columns you want to include in your semantic data model. Add a brief explanation
            of the structure and business meaning so the agent can interpret the data correctly.{' '}
            <Link href={EXTERNAL_LINKS.SEMANTIC_DATA_MODELS} target="_blank">
              Learn more
            </Link>
          </Typography>

          <InputControlled
            fieldName="description"
            label="Business Context"
            rows={4}
            autoGrow
            placeholder="Paste or write here anything that helps us understand the business context of your data. More detailed explanations will lead to a more accurate semantic data model."
          />

          <DataSelector data={inspectionResult?.tables || []} />
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
