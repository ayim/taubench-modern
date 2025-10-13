import { useContext, useState } from 'react';
import { Box, Button, Dialog, Dropzone, Link, Typography, useSnackbar } from '@sema4ai/components';
import { IconCloseSmall, IconDbSchema } from '@sema4ai/icons';
import { useFormContext } from 'react-hook-form';

import { EXTERNAL_LINKS } from '../../../../../../lib/constants';
import { useDataConnectionFileInspectMutation } from '../../../../../../queries/dataConnections';
import {
  ConfigurationStep,
  ConfigurationStepView,
  DataConnectionFormContext,
  DataConnectionFormSchema,
} from '../../form';

export const FileSource: ConfigurationStepView = ({ onClose, setActiveStep }) => {
  const { addSnackbar } = useSnackbar();
  const { setInspectedDataTables, inspectedDataTables } = useContext(DataConnectionFormContext);
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
      const result = await inspectFile({ fileName: file.name, fileContent: file });
      setInspectedDataTables(result.tables);
      setAddedFiles([file.name]);
      setValue('fileRefId', file.name);
    } catch (error) {
      addSnackbar({ message: error instanceof Error ? error.message : 'Failed to inspect file', variant: 'danger' });
    }
  };

  const onRemoveFile = () => {
    setAddedFiles([]);
    setInspectedDataTables([]);
    setValue('fileRefId', undefined);
  };

  return (
    <>
      <Dialog.Content maxWidth={768}>
        <Typography variant="display-large" mb="$12">
          Upload Files
        </Typography>
        <Typography variant="body-large" color="content.subtle" mb="$40">
          Upload your data files (.xlsx, .xls, or .csv) to start building your data model.The file will be used to
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

        {addedFiles.length > 0 && (
          <Box py="$24">
            <Typography fontWeight="medium" mb="$8">
              Added files
            </Typography>
            <Box
              display="flex"
              flexDirection="row"
              borderRadius={8}
              borderWidth={1}
              borderColor="border.subtle"
              backgroundColor="background.panels"
              p={8}
            >
              {addedFiles.map((file) => (
                <Box flex="1" key={file} display="flex" alignItems="center" gap="$8" px="$8">
                  <IconDbSchema />
                  <Typography>{file}</Typography>
                  <Box ml="auto">
                    <Button
                      aria-label="Remove file"
                      variant="ghost-subtle"
                      size="small"
                      icon={IconCloseSmall}
                      onClick={onRemoveFile}
                    />
                  </Box>
                </Box>
              ))}
            </Box>
          </Box>
        )}
      </Dialog.Content>

      <Dialog.Actions>
        <Button
          disabled={addedFiles.length === 0 || inspectedDataTables.length === 0}
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
