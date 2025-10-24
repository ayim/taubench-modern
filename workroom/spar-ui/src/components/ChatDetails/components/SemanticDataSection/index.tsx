import { Box, Button, Typography } from '@sema4ai/components';
import { IconPlusSmall } from '@sema4ai/icons';
import { useState } from 'react';

import { SparUIFeatureFlag } from '../../../../api';
import { useFeatureFlag, useParams } from '../../../../hooks';
import { useAgentSemanticDataQuery } from '../../../../queries/semanticData';
import { SemanticDataConfiguration } from '../../../SemanticData/SemanticDataConfiguration';
import { SemanticModelItem } from './components/SemanticModelItem';

export const SemanticDataSection = () => {
  const [isConfigurationOpen, setIsConfigurationOpen] = useState(false);
  const { agentId } = useParams('/thread/$agentId');
  const { data: semanticDataModels } = useAgentSemanticDataQuery({ agentId });
  const canEditAgent = useFeatureFlag(SparUIFeatureFlag.canEditAgent);
  const { enabled: isChatInteractive } = useFeatureFlag(SparUIFeatureFlag.agentChatInput);

  const onToggleEditModel = () => {
    setIsConfigurationOpen(!isConfigurationOpen);
  };

  if (!canEditAgent && semanticDataModels?.length === 0) return null;

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb="$4">
        <Typography variant="body-medium" fontWeight="bold">
          Data Models
        </Typography>
        {canEditAgent && (
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
        semanticDataModels.map((model) => {
          return <SemanticModelItem key={model.id} model={model} />;
        })
      ) : (
        <Typography>Connect your agent to data from databases or files using Sema4.ai Data Models.</Typography>
      )}
      {isConfigurationOpen && <SemanticDataConfiguration onClose={onToggleEditModel} />}
    </Box>
  );
};
