import { FC } from 'react';
import { Box } from '@sema4ai/components';
import { AgentPackageInspectionResponse } from '@sema4ai/spar-ui/queries';
import { McpServerSection } from './mcpServers/McpServerSection';

export const McpConfigurationStep: FC<{
  agentTemplate: NonNullable<AgentPackageInspectionResponse>;
}> = ({ agentTemplate }) => {
  return (
    <Box display="flex" flexDirection="column" gap="$24">
      <McpServerSection agentTemplate={agentTemplate} />
    </Box>
  );
};
