import { FC, useCallback, useMemo, useState } from 'react';
import { Box, Button, Typography, Menu, useSnackbar } from '@sema4ai/components';
import { IconDotsHorizontal, IconStatusDisabled, IconStatusError } from '@sema4ai/icons';
import { IconDataAccess, IconFileBrand } from '@sema4ai/icons/logos';
import { styled } from '@sema4ai/theme';
import { useDeleteConfirm } from '@sema4ai/layouts';
import { useDropzone } from 'react-dropzone';
import { useParams } from '@tanstack/react-router';

import {
  SemanticModel,
  useDeleteSemanticDataModelMutation,
  useExportSemanticDataModelQuery,
  useUpdateSemanticDataModelMutation,
} from '~/queries/semanticData';
import { RenameDialog } from '~/components/dialogs/RenameDialog';
import { SemanticDataConfiguration } from '../../../../SemanticData/SemanticDataConfiguration';
import { useFeatureFlag, FeatureFlag, useMessageStream } from '../../../../../hooks';
import { downloadFile } from '../../../../../lib/utils';
import {
  parseSemanticModelErrors,
  requiresDataConnection,
  getDataConnectionId,
} from '../../../../../lib/SemanticDataModels';
import { ErrorPopover } from './ErrorPopover';
import { ConfigurationStep } from '../../../../SemanticData/SemanticDataConfiguration/components/form';
import { DataConnectionInformation } from '../../../../DataConnection/DataConnectionInformation';

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
  const { agentId = '', threadId = '' } = useParams({ strict: false });
  const renameThreadId = threadId || undefined;
  const [isConfigurationOpen, setIsConfigurationOpen] = useState(false);
  const [isRenameDialogOpen, setIsRenameDialogOpen] = useState(false);
  const { mutate: deleteSemanticDataModel } = useDeleteSemanticDataModelMutation({});
  const { mutate: updateSemanticDataModel } = useUpdateSemanticDataModelMutation({});
  const { mutateAsync: exportSemanticDataModel } = useExportSemanticDataModelQuery({});
  const { addSnackbar } = useSnackbar();
  const { sendMessage } = useMessageStream({ agentId, threadId });
  const { enabled: canConfigureAgents } = useFeatureFlag(FeatureFlag.canConfigureAgents);
  const { enabled: canCreateAgents } = useFeatureFlag(FeatureFlag.canCreateAgents);
  const [initialStep, setInitialStep] = useState<ConfigurationStep | undefined>(undefined);

  // Determine data source info for analytics
  const dataConnectionId = getDataConnectionId(model);

  const onAddFile = useCallback(
    async (files: File[]) => {
      await sendMessage({ text: '' }, files);
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

  const onToggleEditModelDataConnection = () => {
    setInitialStep(ConfigurationStep.DataConnection);
    setIsConfigurationOpen((prevValue) => !prevValue);
  };

  const onToggleRenameDialog = () => {
    setIsRenameDialogOpen(!isRenameDialogOpen);
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

  const onModelRename = (newName: string) => {
    setIsRenameDialogOpen(false);
    if (!renameThreadId) {
      addSnackbar({ message: 'Unable to rename data model without an active thread.', variant: 'danger' });
      return;
    }

    updateSemanticDataModel(
      {
        agentId,
        threadId: renameThreadId,
        ...model,
        name: newName,
        modelId: model.id,
        dataSelection: [],
        shouldRegenerateModel: false,
        schemas: model.schemas ?? [],
      },
      {
        onSuccess: () => {
          addSnackbar({ message: 'Semantic Data Model renamed successfully', variant: 'success' });
        },
        onError: (error) => {
          addSnackbar({ message: error.message, variant: 'danger' });
        },
      },
    );
  };

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

  const semanticModelErrors = parseSemanticModelErrors(model);

  const connectionError = useMemo(() => {
    if (semanticModelErrors.hasConnectionError) {
      return {
        level: 'error' as const,
        title: 'Connection Failed',
        description: `Unable to connect to the data source. ${canConfigureAgents ? 'Please check your configuration settings.' : 'Please contact your admin to update the connection details.'}`,
      };
    }

    if (semanticModelErrors.hasMissingTableReferenceError) {
      return {
        level: 'error' as const,
        title: 'Missing Table Reference',
        description:
          'Some data could not be matched or processed. Please review your model configuration and ensure the dataset is compatible.',
      };
    }

    return undefined;
  }, [semanticModelErrors]);

  const Icon = requiresDataConnection(model) ? IconDataAccess : IconFileBrand;
  const ErrorIcon = connectionError?.level === 'error' ? IconStatusError : IconStatusDisabled;

  return (
    <Item>
      <Box display="flex" alignItems="center" gap="$4" minWidth={0}>
        <Icon />
        <Box flex={1} minWidth={0} overflow="hidden">
          <DataConnectionInformation
            dataConnectionId={dataConnectionId}
            placement="top"
            error={connectionError}
            action={
              canConfigureAgents && (
                <Button flex={1} round onClick={onToggleEditModelDataConnection}>
                  Configure Connection
                </Button>
              )
            }
          >
            <Typography fontWeight="bold" $nowrap truncate={1}>
              {model.name}
            </Typography>
          </DataConnectionInformation>
        </Box>
        {connectionError && <ErrorIcon color="content.error" />}
        {semanticModelErrors.hasFileReferenceWarning && (
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
      </Box>
      {canCreateAgents && (
        <Menu trigger={<Button variant="outline" size="small" icon={IconDotsHorizontal} round aria-label="Actions" />}>
          <Menu.Item onClick={onToggleEditModel}>View</Menu.Item>
          <Menu.Item onClick={onToggleEditModel}>Edit</Menu.Item>
          <Menu.Item onClick={onToggleRenameDialog}>Rename</Menu.Item>
          <Menu.Item onClick={onExportModel}>Export</Menu.Item>
          <Menu.Item onClick={onDelete}>Delete</Menu.Item>
        </Menu>
      )}
      {isConfigurationOpen && (
        <SemanticDataConfiguration
          initialStep={connectionError ? ConfigurationStep.DataConnection : initialStep}
          onClose={onToggleEditModel}
          modelId={model.id}
        />
      )}
      {isRenameDialogOpen && (
        <RenameDialog
          onClose={onToggleRenameDialog}
          onRename={onModelRename}
          entityName={model.name}
          entityType="Model Name"
        />
      )}
      <input {...getInputProps()} />
    </Item>
  );
};
