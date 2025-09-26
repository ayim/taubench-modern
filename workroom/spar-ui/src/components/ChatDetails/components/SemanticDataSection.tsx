import { useState } from 'react';
import { Box, Button, Menu, Typography } from '@sema4ai/components';
import { IconDatabase, IconDotsHorizontal, IconPlusSmall } from '@sema4ai/icons';
import { styled } from '@sema4ai/theme';

import { SemanticDataConfiguration } from '../../SemanticData/SemanticDataConfiguration';
import { useAgentSemanticDataQuery } from '../../../queries/semanticData';
import { useParams } from '../../../hooks';

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

export const SemanticDataSection = () => {
  const { agentId } = useParams('/thread/$agentId');
  const [isConfigureDataModelsOpen, setIsConfigureDataModelsOpen] = useState(false);
  const [selectedModelId, setSelectedModelId] = useState<string>();

  const { data: semanticDataModels } = useAgentSemanticDataQuery({ agentId });

  const onOpenDialog = () => {
    setIsConfigureDataModelsOpen(true);
  };

  const onCloseDialog = () => {
    setIsConfigureDataModelsOpen(false);
    setSelectedModelId(undefined);
  };

  const onEditModel = (modelId: string) => {
    setSelectedModelId(modelId);
  };

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" mb="$4">
        <Typography variant="body-medium" fontWeight="bold">
          Data Models
        </Typography>
        {semanticDataModels?.length === 0 && (
          <Button
            onClick={onOpenDialog}
            variant="outline"
            size="small"
            aria-label="Configure Data Models"
            icon={IconPlusSmall}
            round
          />
        )}
      </Box>
      {semanticDataModels?.length ? (
        semanticDataModels.map((model) => {
          return (
            <Item key={model.name}>
              <Menu
                trigger={
                  <Trigger>
                    <Box display="flex" alignItems="center" gap="$4">
                      <IconDatabase />
                      <Typography fontWeight="bold">{model.name}</Typography>
                    </Box>

                    <Button variant="outline" size="small" icon={IconDotsHorizontal} round aria-label="Actions" />
                  </Trigger>
                }
              >
                <Menu.Item onClick={() => onEditModel(model.id)}>Edit</Menu.Item>
                <Menu.Item onClick={() => {}}>Delete</Menu.Item>
              </Menu>
            </Item>
          );
        })
      ) : (
        <Typography>Connect your agent to data from databases or files using Sema4.ai Data Models.</Typography>
      )}
      {(isConfigureDataModelsOpen || selectedModelId) && (
        <SemanticDataConfiguration onClose={onCloseDialog} modelId={selectedModelId} />
      )}
    </Box>
  );
};
