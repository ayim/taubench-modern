import { Box, Button, Typography } from '@sema4ai/components';
import { IconPlusSmall } from '@sema4ai/icons';
import { ReactNode, useState } from 'react';
import { useParams } from '@tanstack/react-router';

import { UserRole, useUserRole } from '~/hooks/useUserRole';
import { useAgentSemanticDataQuery, useAgentSemanticDataValidationQuery } from '~/queries/semanticData';
import { useFeatureFlag, FeatureFlag } from '../../../../hooks';
import { SemanticDataConfiguration } from '../../../SemanticData/SemanticDataConfiguration';
import { SemanticModelItem } from './components/SemanticModelItem';

type Props = {
  /**
   * A temporary prop to indicate that the SDM feature is a "Preview" feature in Studio.
   */
  titleBadge?: ReactNode;
};

export const SemanticData = ({ titleBadge }: Props) => {
  const [isConfigurationOpen, setIsConfigurationOpen] = useState(false);
  const { agentId = '', threadId = '' } = useParams({ strict: false });
  const { data: semanticDataModelsWithoutValidation, isLoading } = useAgentSemanticDataQuery({ agentId });
  const { data: semanticDataModelsWithValidation } = useAgentSemanticDataValidationQuery({ agentId, threadId });
  const { enabled: isSemanticDataModelsAvailable } = useFeatureFlag(FeatureFlag.semanticDataModels);
  const { enabled: isChatInteractive } = useFeatureFlag(FeatureFlag.agentChatInput);
  const hasAdminRole = useUserRole(UserRole.Admin);

  const semanticDataModels = semanticDataModelsWithValidation || semanticDataModelsWithoutValidation;

  const onToggleEditModel = () => {
    setIsConfigurationOpen(!isConfigurationOpen);
  };

  if (!isSemanticDataModelsAvailable || isLoading) {
    return null;
  }

  if (!hasAdminRole && (!semanticDataModels || semanticDataModels.length === 0)) {
    return null;
  }

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb="$4">
        <Box display="flex" alignItems="center" gap="$4">
          <Typography variant="body-medium" fontWeight="medium">
            Semantic Data Models
          </Typography>
          {titleBadge || null}
        </Box>
        {hasAdminRole && (
          <Button
            disabled={!isChatInteractive}
            onClick={onToggleEditModel}
            variant="outline"
            size="small"
            aria-label="Configure Data Models"
            icon={IconPlusSmall}
            round
          />
        )}
      </Box>
      {semanticDataModels?.length ? (
        semanticDataModels.map((model) => <SemanticModelItem key={model.id} model={model} />)
      ) : (
        <Typography>Connect your agent to data from databases or spreadsheets using Semantic Data Models.</Typography>
      )}
      {isConfigurationOpen && <SemanticDataConfiguration onClose={onToggleEditModel} />}
    </Box>
  );
};
