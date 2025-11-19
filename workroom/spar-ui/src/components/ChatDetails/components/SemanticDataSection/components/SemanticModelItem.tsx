import { FC, useCallback, useState } from 'react';
import { Box, Button, Typography, Menu, useSnackbar } from '@sema4ai/components';
import { IconDotsHorizontal } from '@sema4ai/icons';
import { IconDataAccess, IconFileBrand } from '@sema4ai/icons/logos';
import { styled } from '@sema4ai/theme';
import { useDeleteConfirm } from '@sema4ai/layouts';
import { useDropzone } from 'react-dropzone';

import { SemanticDataConfiguration } from '../../../../SemanticData/SemanticDataConfiguration';
import {
  SemanticModel,
  useDeleteSemanticDataModelMutation,
  useExportSemanticDataModelQuery,
} from '../../../../../queries/semanticData';
import { useMessageStream, useParams } from '../../../../../hooks';
import { downloadFile } from '../../../../../lib/utils';
import { parseSemanticModelErrors, requiresDataConnection } from '../../../../../lib/SemanticDataModels';
import { ErrorPopover } from './ErrorPopover';

type Props = {
  model: SemanticModel;
};

const Item = styled(Box)`
  display: flex;
  align-items: center;
  height: ${({ theme }) => theme.sizes.$32};
  justify-content: space-between;

  > button {
    display: none;
  }

  &:hover,
  &:has([aria-expanded='true']) {
    > button {
      display: block;
    }
  }
`;

export const SemanticModelItem: FC<Props> = ({ model }) => {
  const { agentId, threadId } = useParams('/thread/$agentId/$threadId');
  const [isConfigurationOpen, setIsConfigurationOpen] = useState(false);
  const { mutate: deleteSemanticDataModel } = useDeleteSemanticDataModelMutation({});
  const { mutateAsync: exportSemanticDataModel } = useExportSemanticDataModelQuery({});
  const { addSnackbar } = useSnackbar();
  const { sendMessage } = useMessageStream({ agentId, threadId });

  const onAddFile = useCallback(
    async (files: File[]) => {
      await sendMessage('', files);
    },
    [sendMessage],
  );

  const { getInputProps, open: onOpenFilePicker } = useDropzone({ onDrop: onAddFile });

  const onDeleteConfirm = useDeleteConfirm(
    {
      entityName: model.name,
      entityType: 'Semantic Data Model',
    },
    [],
  );

  const onToggleEditModel = () => {
    setIsConfigurationOpen(!isConfigurationOpen);
  };

  const onDelete = onDeleteConfirm(() => {
    deleteSemanticDataModel(
      { agentId, modelId: model.id },
      {
        onSuccess: () => {
          addSnackbar({
            message: 'Semantic Data Model deleted successfully',
            variant: 'success',
          });
        },
        onError: (error) => {
          addSnackbar({
            message: error instanceof Error ? error.message : 'Failed to delete Semantic Data Model',
            variant: 'danger',
          });
        },
      },
    );
  });

  const onExportModel = async () => {
    const yamlData = await exportSemanticDataModel({ modelId: model.id });

    const blob = new Blob([yamlData.content], { type: 'text/yaml' });
    const fileName = yamlData.filename;
    downloadFile(blob, fileName);

    addSnackbar({
      message: `Semantic Data Model "${model.name}" exported successfully`,
      variant: 'success',
    });
  };

  const errors = parseSemanticModelErrors(model);

  const Icon = requiresDataConnection(model) ? IconDataAccess : IconFileBrand;

  return (
    <Item>
      <Box display="flex" alignItems="center" gap="$4" minWidth={0}>
        <Icon />
        <Box flex={1} minWidth={0} overflow="hidden">
          <Typography fontWeight="bold" $nowrap truncate={1}>
            {model.name}
          </Typography>
        </Box>
        {errors.hasConnectionError && (
          <ErrorPopover
            title="Connection Failed"
            description="Unable to connect to the data source. Please check your configuration settings."
            action={
              <Button flex={1} round onClick={onToggleEditModel}>
                Configure Connection
              </Button>
            }
            level="error"
          />
        )}
        {errors.hasFileReferenceWarning && (
          <ErrorPopover
            title="Missing File"
            description="This data model requires a data file to be uploaded to the chat. Once uploaded, you can use this model to work with the file’s data."
            action={
              <Button flex={1} round onClick={onOpenFilePicker}>
                Upload File
              </Button>
            }
            level="warning"
          />
        )}
        {errors.hasMissingTableReferenceError && (
          <ErrorPopover
            title="Data Unavailable"
            description="Some data could not be matched or processed. Please review your model configuration and ensure the dataset is compatible."
            action={
              <Button flex={1} round onClick={onToggleEditModel}>
                Review
              </Button>
            }
            level="error"
          />
        )}
      </Box>
      <Menu trigger={<Button variant="outline" size="small" icon={IconDotsHorizontal} round aria-label="Actions" />}>
        <Menu.Item onClick={onToggleEditModel}>View</Menu.Item>
        <Menu.Item onClick={onToggleEditModel}>Edit</Menu.Item>
        <Menu.Item onClick={onExportModel}>Export</Menu.Item>
        <Menu.Item onClick={onDelete}>Delete</Menu.Item>
      </Menu>
      {isConfigurationOpen && <SemanticDataConfiguration onClose={onToggleEditModel} modelId={model.id} />}
      <input {...getInputProps()} />
    </Item>
  );
};
