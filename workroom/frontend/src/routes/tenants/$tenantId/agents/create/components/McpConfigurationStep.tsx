import { FC } from 'react';
import { Box } from '@sema4ai/components';
import { McpServerSection } from './mcpServers/McpServerSection';
export const McpConfigurationStep: FC = () => {
  return (
    <Box display="flex" flexDirection="column" gap="$24">
      <McpServerSection />
    </Box>
  );
};
