import { useState } from 'react';
import { Button, Card, Dialog, Grid, Link, Typography } from '@sema4ai/components';
import { IconDataAccess } from '@sema4ai/icons/logos';
import { IconFile } from '@sema4ai/icons';

import { EXTERNAL_LINKS } from '../../../../../lib/constants';
import { ConfigurationStepView } from '../form';
import { DatabaseSource } from './components/DatabaseSource';
import { FileSource } from './components/FileSource';

export const DataConnection: ConfigurationStepView = ({ onClose, setActiveStep }) => {
  const [dataSourceType, setDataSourceType] = useState<'file' | 'database' | undefined>(undefined);

  if (dataSourceType === 'database') {
    return <DatabaseSource onClose={onClose} setActiveStep={setActiveStep} />;
  }

  if (dataSourceType === 'file') {
    return <FileSource onClose={onClose} setActiveStep={setActiveStep} />;
  }

  return (
    <>
      <Dialog.Content maxWidth={768}>
        <Typography variant="display-large" mb="$12">
          Create Data Model
        </Typography>
        <Typography variant="body-large" color="content.subtle" mb="$40">
          Choose whether to link a database or upload files to define your data model. The model provides structure and
          context, helping your agent accurately interpret and work with your data.{' '}
          <Link href={EXTERNAL_LINKS.DATA_ACCESS} target="_blank">
            Learn more
          </Link>
        </Typography>
        <Grid columns={[1, 1, 2]} gap="$32">
          <Card
            onClick={() => setDataSourceType('database')}
            title="Connect to Database"
            icon={IconDataAccess}
            description="Link your agent directly to data from a database. Select the tables and columns to include in your model."
            as="button"
          />
          <Card
            onClick={() => setDataSourceType('file')}
            title="Upload Files"
            icon={IconFile}
            description="Build a data model based on spreadsheets or CSV files. Choose the data your agent should understand when you upload similar files later."
            as="button"
          />
        </Grid>
      </Dialog.Content>
      <Dialog.Actions>
        <Button disabled round>
          Continue
        </Button>
        <Button variant="secondary" onClick={onClose} round>
          Cancel
        </Button>
      </Dialog.Actions>
    </>
  );
};
