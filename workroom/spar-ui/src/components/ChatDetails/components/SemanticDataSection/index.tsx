import { Box, Button, Typography } from '@sema4ai/components';
import { IconPlusSmall } from '@sema4ai/icons';
import { useState } from 'react';

import { SparUIFeatureFlag } from '../../../../api';
import { useFeatureFlag, useParams } from '../../../../hooks';
import { useAgentSemanticDataQuery, useAgentSemanticDataValidationQuery } from '../../../../queries/semanticData';
import { SemanticDataConfiguration } from '../../../SemanticData/SemanticDataConfiguration';
import { SemanticModelItem } from './components/SemanticModelItem';

export const SemanticDataSection = () => {
  const [isConfigurationOpen, setIsConfigurationOpen] = useState(false);
  const { agentId } = useParams('/thread/$agentId');
  const { data: semanticDataModels, isLoading } = useAgentSemanticDataQuery({ agentId });
  const { data: semanticDataValidation } = useAgentSemanticDataValidationQuery({ agentId });
  const { enabled: isSemanticDataModelsAvailable } = useFeatureFlag(SparUIFeatureFlag.semanticDataModels);
  const { enabled: isChatInteractive } = useFeatureFlag(SparUIFeatureFlag.agentChatInput);

  const onToggleEditModel = () => {
    setIsConfigurationOpen(!isConfigurationOpen);
  };

  if (!isSemanticDataModelsAvailable || isLoading) {
    return null;
  }

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb="$4">
        <Typography variant="body-medium" fontWeight="bold">
          Data Models
        </Typography>
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
        semanticDataModels.map((model) => {
          const validation = semanticDataValidation?.find((v) => v.semantic_data_model_id === model.id);
          return <SemanticModelItem key={model.id} model={model} validation={validation} />;
        })
      ) : (
        <Typography>Connect your agent to data from databases or files using Sema4.ai Data Models.</Typography>
      )}
      {isConfigurationOpen && <SemanticDataConfiguration onClose={onToggleEditModel} />}
    </Box>
  );
};
