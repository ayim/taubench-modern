import { FC, Fragment, useState } from 'react';
import { Box, Button, Typography, Menu, Tooltip, useSnackbar } from '@sema4ai/components';
import { IconDatabase, IconDotsHorizontal, IconStatusError } from '@sema4ai/icons';
import { styled } from '@sema4ai/theme';
import { useDeleteConfirm } from '@sema4ai/layouts';

import { SemanticDataConfiguration } from '../../../../SemanticData/SemanticDataConfiguration';
import {
  SemanticModel,
  useDeleteSemanticDataModelMutation,
  useExportSemanticDataModelQuery,
} from '../../../../../queries/semanticData';
import { useParams } from '../../../../../hooks';
import { downloadFile } from '../../../../../lib/utils';
import { ServerResponse } from '../../../../../queries/shared';

type Props = {
  model: SemanticModel;
  validation?: ServerResponse<'post', '/api/v2/semantic-data-models/validate'>['results'][number];
};

const Item = styled(Box)`
  display: flex;
  align-items: center;
  height: ${({ theme }) => theme.sizes.$32};
  justify-content: space-between;
`;

const Trigger = styled.div`
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: ${({ theme }) => theme.space.$4};
  width: 100%;

  > button {
    display: none;
  }

  &:hover {
    > button {
      display: block;
    }
  }
`;

export const SemanticModelItem: FC<Props> = ({ model, validation }) => {
  const { agentId } = useParams('/thread/$agentId');
  const [isConfigurationOpen, setIsConfigurationOpen] = useState(false);
  const { mutate: deleteSemanticDataModel } = useDeleteSemanticDataModelMutation({});
  const { mutateAsync: exportSemanticDataModel } = useExportSemanticDataModelQuery({});
  const { addSnackbar } = useSnackbar();

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

  const errors = validation?.errors || [];

  return (
    <Item>
      <Menu
        trigger={
          <Trigger>
            <Box display="flex" alignItems="center" gap="$4">
              <IconDatabase />
              <Typography fontWeight="bold">{model.name}</Typography>
              {errors.length > 0 && (
                <Tooltip
                  text={errors.map((error) => (
                    <Fragment key={error.message}>
                      {error.message}
                      <br />
                    </Fragment>
                  ))}
                >
                  <IconStatusError color="content.error" />
                </Tooltip>
              )}
            </Box>

            <Button variant="outline" size="small" icon={IconDotsHorizontal} round aria-label="Actions" />
          </Trigger>
        }
      >
        <Menu.Item onClick={onToggleEditModel}>Edit</Menu.Item>
        <Menu.Item onClick={onExportModel}>Export</Menu.Item>
        <Menu.Item onClick={onDelete}>Delete</Menu.Item>
      </Menu>
      {isConfigurationOpen && <SemanticDataConfiguration onClose={onToggleEditModel} modelId={model.id} />}
    </Item>
  );
};
