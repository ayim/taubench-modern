import { Box, Button, Typography } from '@sema4ai/components';
import { IconPlusSmall } from '@sema4ai/icons';
import { ReactNode, useState } from 'react';

import { SparUIFeatureFlag } from '../../../../api';
import { useFeatureFlag, useParams } from '../../../../hooks';
import { useAgentSemanticDataQuery, useAgentSemanticDataValidationQuery } from '../../../../queries/semanticData';
import { SemanticDataConfiguration } from '../../../SemanticData/SemanticDataConfiguration';
import { SemanticModelItem } from './components/SemanticModelItem';

type Props = {
  /**
   * A temporary prop to indicate that the SDM feature is a "Preview" feature in Studio.
   */
  titleBadge?: ReactNode;
};

export const SemanticDataSection = ({ titleBadge }: Props) => {
  const [isConfigurationOpen, setIsConfigurationOpen] = useState(false);
  const { agentId, threadId } = useParams('/thread/$agentId/$threadId');
  const { data: semanticDataModelsWithoutValidation, isLoading } = useAgentSemanticDataQuery({ agentId });
  const { data: semanticDataModelsWithValidation } = useAgentSemanticDataValidationQuery({ agentId, threadId });
  const { enabled: isSemanticDataModelsAvailable } = useFeatureFlag(SparUIFeatureFlag.semanticDataModels);
  const { enabled: isChatInteractive } = useFeatureFlag(SparUIFeatureFlag.agentChatInput);

  const semanticDataModels = semanticDataModelsWithValidation || semanticDataModelsWithoutValidation;

  const onToggleEditModel = () => {
    setIsConfigurationOpen(!isConfigurationOpen);
  };

  if (!isSemanticDataModelsAvailable || isLoading) {
    return null;
  }

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb="$4">
        <Box display="flex" alignItems="center" gap="$4">
          <Typography variant="body-medium" fontWeight="bold">
            Data
          </Typography>
          {titleBadge || null}
        </Box>
        <Button
          disabled={!isChatInteractive}
          onClick={onToggleEditModel}
          variant="outline"
          size="small"
          aria-label="Configure Data Models"
          icon={IconPlusSmall}
          round
        />
      </Box>
      {semanticDataModels?.length ? (
        semanticDataModels.map((model) => <SemanticModelItem key={model.id} model={model} />)
      ) : (
        <Typography>Connect your agent to data from databases or files using Sema4.ai Data Models.</Typography>
      )}
      {isConfigurationOpen && <SemanticDataConfiguration onClose={onToggleEditModel} />}
    </Box>
  );
};
