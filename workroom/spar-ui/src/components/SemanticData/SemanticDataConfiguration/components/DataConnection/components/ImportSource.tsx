import { useContext } from 'react';
import { Button, Dialog, Dropzone, Link, Typography, useSnackbar } from '@sema4ai/components';
import { useFormContext } from 'react-hook-form';
import { parse as yamlParse } from 'yaml';

import { EXTERNAL_LINKS } from '../../../../../../lib/constants';
import {
  ConfigurationStepView,
  DataConnectionFormContext,
  DataConnectionFormSchema,
  semanticModelToFormSchema,
  hasDataFrameReferences,
  requiresDataConnection,
} from '../../form';
import { DataConnectionSelect } from './DataConnectionSelect';
import { SemanticModel } from '../../../../../../queries/semanticData';

export const ImportSource: ConfigurationStepView = ({ onClose }) => {
  const { addSnackbar } = useSnackbar();
  const { reset, watch } = useFormContext<DataConnectionFormSchema>();
  const { onSubmit } = useContext(DataConnectionFormContext);
  const state = watch();

  const onDrop = async (files: File[]) => {
    const file = files[0];
    try {
      const text = await file.text();
      const model = yamlParse(text);
      const values = semanticModelToFormSchema(model);

      if (typeof values.fileRefId === 'string') {
        values.fileRefId = file.name;
      }

      if (values.dataConnectionId) {
        values.dataConnectionId = undefined;
      }

      reset(values);

      if (values.fileRefId) {
        onSubmit();
      }
    } catch (error) {
      addSnackbar({ message: error instanceof Error ? error.message : 'Failed to validate model', variant: 'danger' });
    }
  };

  const isModelImported = !!state.tables;
  const semanticModel = state.tables ? ({ tables: state.tables } as SemanticModel) : null;
  const hasDataFrames = semanticModel ? hasDataFrameReferences(semanticModel) : false;
  const needsDataConnection = semanticModel ? requiresDataConnection(semanticModel) : false;
  const requiresDataConnectionStep = isModelImported && !state.fileRefId && needsDataConnection;
  // Can skip if model has data frames and doesn't need database connection (data frames only)
  const canSkipConnection = isModelImported && hasDataFrames && !needsDataConnection;
  // Submit is disabled if: no model imported OR (needs connection step AND no connection selected)
  const isSubmitDisabled = !isModelImported || (requiresDataConnectionStep && !state.dataConnectionId);

  return (
    <>
      <Dialog.Content maxWidth={768}>
        {!requiresDataConnectionStep && (
          <>
            <Typography variant="display-medium" mb="$12">
              Upload File
            </Typography>
            <Typography variant="body-large" color="content.subtle" mb="$40">
              Upload a .yaml file containing your semantic data model to begin the import process.{' '}
              <Link href={EXTERNAL_LINKS.SEMANTIC_DATA_MODELS} target="_blank">
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
            {canSkipConnection && (
              <Typography variant="body-medium" color="content.subtle" mt="$16">
                This model references data frames only. No database connection is required.
              </Typography>
            )}
          </>
        )}
        {requiresDataConnectionStep && (
          <>
            <Typography variant="display-large" mb="$12">
              Connect to Your Database
            </Typography>
            <Typography variant="body-large" color="content.subtle" mb="$40">
              Connect the database associated with your uploaded file so your agent can securely access the necessary
              data.{' '}
              <Link href={EXTERNAL_LINKS.SEMANTIC_DATA_MODELS} target="_blank">
                Learn more
              </Link>
            </Typography>
            <DataConnectionSelect />
            {hasDataFrames && (
              <Typography variant="body-medium" color="content.subtle" mt="$16" mb="$8">
                This model also references data frames. You can skip the database connection and import the model using
                only data frames.
              </Typography>
            )}
          </>
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
