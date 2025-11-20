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
  DataSourceType,
} from '../../form';

type Props = {
  setDataSourceType: (dataSourceType: DataSourceType | undefined) => void;
};

export const FileSource: ConfigurationStepView<Props> = ({ onClose, setActiveStep, setDataSourceType }) => {
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
    try {
      const inspectionResult = await inspectFile({ fileName: file.name, fileContent: file });
      setDatabaseInspectionState({
        isLoading: false,
        error: undefined,
        inspectionResult,
      });
      setAddedFiles([file.name]);
      setValue('fileRefId', file.name);
    } catch (error) {
      addSnackbar({ message: error instanceof Error ? error.message : 'Failed to inspect file', variant: 'danger' });
    }
  };

  const onRemoveFile = () => {
    setAddedFiles([]);
    setDatabaseInspectionState({
      isLoading: false,
      error: undefined,
      inspectionResult: undefined,
    });
    setValue('fileRefId', undefined);
  };

  const onResetSourceSelection = () => {
    setDataSourceType(undefined);
    setValue('fileRefId', undefined);
  };

  return (
    <>
      <Dialog.Content maxWidth={768}>
        <Typography variant="display-medium" mb="$12">
          Upload Files
        </Typography>
        <Typography variant="body-large" color="content.subtle" mb="$40">
          Upload your data files (.xlsx, .xls, or .csv) to start building your data model. The file will be used to
          extract its structure and columns in the next step — it won’t be stored in your agent.{' '}
          <Link href={EXTERNAL_LINKS.DATA_ACCESS} target="_blank">
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
        <Button variant="secondary" align="secondary" onClick={onResetSourceSelection} round>
          Back
        </Button>
      </Dialog.Actions>
    </>
  );
};
