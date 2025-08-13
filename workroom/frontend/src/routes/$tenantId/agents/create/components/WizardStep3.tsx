import { FC, useEffect, useRef } from 'react';
import { Box } from '@sema4ai/components';
import { useFormContext } from 'react-hook-form';
import { AgentDeploymentFormSchema, MCPServerSettings } from './context';
import { McpServerSection } from './mcpServers/McpServerSection';

type MCPServer = {
  name: string;
  url: string;
  transport: 'auto' | 'sse' | 'streamable-http';
  headers: unknown;
};

type Props = {
  mcpServers: MCPServer[];
};

// Helper functions
const createMCPServerFromTemplate = (serverData: MCPServer): MCPServerSettings => ({
  name: serverData.name,
  url: serverData.url,
  transport: serverData.transport,
  headers: serverData.headers as MCPServerSettings['headers'],
});

export const WizardStep3: FC<Props> = ({ mcpServers }) => {
  const { setValue, watch } = useFormContext<AgentDeploymentFormSchema>();

  // Initialize form with servers from agent template if not already set
  const currentSettings = watch('mcpServerSettings');

  // Auto-populate form with servers from agent template only once on mount
  const hasInitializedRef = useRef(false);
  useEffect(() => {
    if (hasInitializedRef.current) return;
    if (mcpServers.length > 0 && (!currentSettings || currentSettings.length === 0)) {
      const initialSettings = mcpServers.map((server) => createMCPServerFromTemplate(server));
      setValue('mcpServerSettings', initialSettings);
    }
    hasInitializedRef.current = true;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <Box display="flex" flexDirection="column" gap="$24">
      <McpServerSection />
    </Box>
  );
};
