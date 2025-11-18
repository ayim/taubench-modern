import { Button, Dialog, Link, Typography } from '@sema4ai/components';
import { useFormContext } from 'react-hook-form';

import { EXTERNAL_LINKS } from '../../../../lib/constants';
import { InputControlled } from '../../../../common/form/InputControlled';
import { ConfigurationStepView, DataConnectionFormSchema } from './form';
import { DataSelector } from './DataSelector';

export const ModelCreation: ConfigurationStepView = ({ onClose }) => {
  const { watch } = useFormContext<DataConnectionFormSchema>();
  const dataConnectionId = watch('dataConnectionId');

  return (
    <>
      <Dialog.Content>
        <Typography variant="display-large" mb="$12">
          Select Data
        </Typography>
        <Typography variant="body-large" color="content.subtle" mb="$40">
          Select the tables and columns you want your agent to use. Add a brief explanation of the structure and
          business meaning so the agent can interpret the data correctly.{' '}
          <Link href={EXTERNAL_LINKS.DATA_ACCESS} target="_blank">
            Learn more
          </Link>
        </Typography>

        <InputControlled
          fieldName="description"
          label="Business Context"
          rows={4}
          autoGrow
          placeholder="Paste or write here anything that helps us understand the business context of your data."
        />

        <Typography my="$16">Selected data</Typography>
        <DataSelector data={[]} />
      </Dialog.Content>

      <Dialog.Actions>
        <Button disabled={!dataConnectionId} type="submit" round>
          Continue
        </Button>
        <Button variant="secondary" onClick={onClose} round>
          Cancel
        </Button>
      </Dialog.Actions>
    </>
  );
};
