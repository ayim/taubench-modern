import { Button, Card, Dialog, Grid, Link, Typography } from '@sema4ai/components';
import { IconDataAccess, IconDataModelImport, IconFileBrand } from '@sema4ai/icons/logos';

import { EXTERNAL_LINKS } from '../../../../../lib/constants';
import { ConfigurationStepView, DataSourceType } from '../form';
import { DatabaseSource } from './components/DatabaseSource';
import { FileSource } from './components/FileSource';
import { ImportSource } from './components/ImportSource';

type Props = {
  setDataSourceType: (dataSourceType: DataSourceType | undefined) => void;
  dataSourceType: DataSourceType | undefined;
};

export const DataConnection: ConfigurationStepView<Props> = ({
  onClose,
  setActiveStep,
  setDataSourceType,
  dataSourceType,
}) => {
  if (dataSourceType === DataSourceType.Database) {
    return <DatabaseSource onClose={onClose} setActiveStep={setActiveStep} />;
  }

  if (dataSourceType === DataSourceType.File) {
    return <FileSource onClose={onClose} setActiveStep={setActiveStep} />;
  }

  if (dataSourceType === DataSourceType.Import) {
    return <ImportSource onClose={onClose} setActiveStep={setActiveStep} />;
  }

  return (
    <>
      <Dialog.Content maxWidth={768}>
        <Typography variant="display-medium" mb="$12">
          Add Semantic Data Model
        </Typography>
        <Typography variant="body-large" color="content.subtle" mb="$40">
          Choose whether to connect to a database, upload files, or import an existing data model. We&apos;ll
          automatically create a semantic data model that provides structure and context, helping your agent accurately
          interpret and work with your data in natural language.{' '}
          <Link href={EXTERNAL_LINKS.SEMANTIC_DATA_MODELS} target="_blank">
            Learn more
          </Link>
        </Typography>
        <Grid columns={[1, 1, 3]} gap="$16">
          <Card
            onClick={() => setDataSourceType(DataSourceType.Database)}
            title="Connect to Database"
            icon={IconDataAccess}
            description="Link your agent directly to data from a database. Select the tables and columns to include in your model."
            as="button"
          />
          <Card
            onClick={() => setDataSourceType(DataSourceType.File)}
            title="Upload Files"
            icon={IconFileBrand}
            description="Build a data model based on spreadsheets or CSV files. Choose the data your agent should understand when you upload similar files later."
            as="button"
          />
          <Card
            onClick={() => setDataSourceType(DataSourceType.Import)}
            title="Import Data Model"
            icon={IconDataModelImport}
            description="Bring in an existing data model by importing the model .yaml file."
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
