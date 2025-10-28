import { useContext } from 'react';
import { Box, Button, Dialog, Dropzone, Link, Typography, useSnackbar } from '@sema4ai/components';
import { useFormContext } from 'react-hook-form';
import { parse as yamlParse } from 'yaml';

import { EXTERNAL_LINKS } from '../../../../../../lib/constants';
import {
  ConfigurationStepView,
  DataConnectionFormContext,
  DataConnectionFormSchema,
  semanticModelToFormSchema,
} from '../../form';
import { DataConnectionSelect } from './DataConnectionSelect';

export const ImportSource: ConfigurationStepView = ({ onClose }) => {
  const { addSnackbar } = useSnackbar();
  const { reset, watch } = useFormContext<DataConnectionFormSchema>();
  const { importErrors, setImportErrors, onSubmit } = useContext(DataConnectionFormContext);
  const state = watch();

  const onDrop = async (files: File[]) => {
    const file = files[0];
    setImportErrors([]);
    try {
      const text = await file.text();
      const model = yamlParse(text);
      const values = semanticModelToFormSchema(model);

      if (values.dataConnectionId) {
        values.dataConnectionId = undefined;
        reset(values);
      } else {
        values.fileRefId = file.name;
        reset(values);
        onSubmit();
      }
    } catch (error) {
      addSnackbar({ message: error instanceof Error ? error.message : 'Failed to validate model', variant: 'danger' });
    }
  };

  const isModelImported = !!state.tables;
  const requiresDataConnection = isModelImported && !state.fileRefId;
  const isSubmitDisabled = !isModelImported || (!state.fileRefId && !state.dataConnectionId);

  return (
    <>
      <Dialog.Content maxWidth={768}>
        {!requiresDataConnection && (
          <>
            <Typography variant="display-large" mb="$12">
              Upload File
            </Typography>
            <Typography variant="body-large" color="content.subtle" mb="$40">
              Upload a .yml file containing your data model to begin the import process.{' '}
              <Link href={EXTERNAL_LINKS.DATA_ACCESS} target="_blank">
                Learn more
              </Link>
            </Typography>

            <Dropzone
              onDrop={onDrop}
              dropzoneConfig={{
                accept: {
                  'application/x-yaml': ['.yml', '.yaml'],
                },
              }}
              title={
                <span>
                  Drag & drop or{' '}
                  <Typography color="content.accent" as="span">
                    select file
                  </Typography>{' '}
                  to upload
                </span>
              }
              dropTitle="Drop your files here"
              description="Supports .yml, .yaml files • Max size: 20MB"
            />
          </>
        )}
        {requiresDataConnection && (
          <>
            <Typography variant="display-large" mb="$12">
              Connect to Your Database
            </Typography>
            <Typography variant="body-large" color="content.subtle" mb="$40">
              Connect the database associated with your uploaded file so your agent can securely access the necessary
              data.{' '}
              <Link href={EXTERNAL_LINKS.DATA_ACCESS} target="_blank">
                Learn more
              </Link>
            </Typography>
            <DataConnectionSelect />
          </>
        )}
        {importErrors.length > 0 && (
          <Box pt="$32">
            <Typography mb="$8">Import errors</Typography>
            {importErrors.map((error) => (
              <Typography variant="body-large" color="content.error" mb="$4">
                - {error}
              </Typography>
            ))}
          </Box>
        )}
      </Dialog.Content>

      <Dialog.Actions>
        <Button round type="submit" disabled={isSubmitDisabled}>
          Continue
        </Button>
        <Button variant="secondary" round onClick={onClose}>
          Cancel
        </Button>
      </Dialog.Actions>
    </>
  );
};
