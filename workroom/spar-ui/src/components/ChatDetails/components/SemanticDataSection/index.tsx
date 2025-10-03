import { useState } from 'react';
import { Box, Button, Typography } from '@sema4ai/components';
import { IconPlusSmall } from '@sema4ai/icons';

import { useAgentSemanticDataQuery } from '../../../../queries/semanticData';
import { useParams } from '../../../../hooks';
import { SemanticModelItem } from './components/SemanticModelItem';
import { SemanticDataConfiguration } from '../../../SemanticData/SemanticDataConfiguration';

export const SemanticDataSection = () => {
  const [isConfigurationOpen, setIsConfigurationOpen] = useState(false);
  const { agentId } = useParams('/thread/$agentId');
  const { data: semanticDataModels } = useAgentSemanticDataQuery({ agentId });

  const onToggleEditModel = () => {
    setIsConfigurationOpen(!isConfigurationOpen);
  };

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" mb="$4">
        <Typography variant="body-medium" fontWeight="bold">
          Data Models
        </Typography>
        {semanticDataModels?.length === 0 && (
          <Button
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
