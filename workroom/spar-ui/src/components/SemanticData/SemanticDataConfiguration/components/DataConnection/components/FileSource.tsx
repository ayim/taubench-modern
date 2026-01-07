import { useContext, useState } from 'react';
import { Button, Dialog, Dropzone, Link, Typography, useSnackbar } from '@sema4ai/components';
import { useFormContext } from 'react-hook-form';

import { FileList } from './FileList';
import { EXTERNAL_LINKS } from '../../../../../../lib/constants';
import { useDataConnectionFileInspectMutation } from '../../../../../../queries/dataConnections';
import {
  ConfigurationStep,
  ConfigurationStepView,
  DataConnectionFormContext,
  DataConnectionFormSchema,
  tablesToDataSelection,
} from '../../form';

export const FileSource: ConfigurationStepView = ({ onClose, setActiveStep }) => {
  const { addSnackbar } = useSnackbar();
  const { setDatabaseInspectionState, databaseInspectionState } = useContext(DataConnectionFormContext);
  const { mutateAsync: inspectFile } = useDataConnectionFileInspectMutation({
    onError: (error: unknown) => {
      addSnackbar({ message: error instanceof Error ? error.message : 'Failed to inspect file', variant: 'danger' });
    },
  });
  const [addedFiles, setAddedFiles] = useState<string[]>([]);
  const { setValue } = useFormContext<DataConnectionFormSchema>();

  const onDrop = async (files: File[]) => {
    const file = files[0];

    if (file) {
      try {
        const inspectionResult = await inspectFile({ fileName: file.name, fileContent: file });
        setDatabaseInspectionState({
          isLoading: false,
          error: undefined,
          inspectionResult,
          requiresInspection: false,
        });
        setValue('dataSelection', tablesToDataSelection(inspectionResult));

        setAddedFiles([file.name]);
        setValue('fileRefId', file.name);
      } catch (error) {
        addSnackbar({ message: error instanceof Error ? error.message : 'Failed to inspect file', variant: 'danger' });
      }
    }
  };

  const onRemoveFile = () => {
    setAddedFiles([]);
    setDatabaseInspectionState({
      isLoading: false,
      error: undefined,
      inspectionResult: undefined,
      requiresInspection: false,
    });
    setValue('fileRefId', undefined);
  };

  return (
    <>
      <Dialog.Content maxWidth={768}>
        <Typography variant="display-medium" mb="$12">
          Upload a File
        </Typography>
        <Typography variant="body-large" color="content.subtle" mb="$40">
          Upload your data file (.xlsx, .xls, .json or .csv) to start building your semantic data model. The file will
          be used to extract its structure and columns in the next step — it won’t be stored with your agent.{' '}
          <Link href={EXTERNAL_LINKS.SEMANTIC_DATA_MODELS} target="_blank">
            Learn more
          </Link>
        </Typography>

        <Dropzone
          onDrop={onDrop}
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
          description="Supports .xlsx, .xls, .csv files • Max size: 20MB"
          dropzoneConfig={{
            accept: {
              'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
              'application/vnd.ms-excel': ['.xls'],
              'text/csv': ['.csv'],
            },
            maxSize: 20_000_000, // 20MB
          }}
        />
        <FileList files={addedFiles} onRemoveFile={onRemoveFile} />
      </Dialog.Content>

      <Dialog.Actions>
        <Button
          disabled={addedFiles.length === 0 || !databaseInspectionState.inspectionResult?.tables?.length}
          round
          onClick={() => setActiveStep(ConfigurationStep.DataSelection)}
        >
          Continue
        </Button>
        <Button variant="secondary" round onClick={onClose}>
          Cancel
        </Button>
      </Dialog.Actions>
    </>
  );
};
