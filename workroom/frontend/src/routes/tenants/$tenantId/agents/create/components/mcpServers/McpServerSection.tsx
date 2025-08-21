import { FC } from 'react';
import { Box, Header, Button } from '@sema4ai/components';
import { IconPlus } from '@sema4ai/icons';
import { useFormContext } from 'react-hook-form';

import { AgentDeploymentFormSchema, MCPServerSettings } from '../context';
import { McpServerItem } from './McpServerItem';

export const McpServerSection: FC = () => {
  const { watch, getValues, setValue, trigger } = useFormContext<AgentDeploymentFormSchema>();
  const mcpServerSettings = watch('mcpServerSettings') || [];

  const isValid = mcpServerSettings.every((server) => server && server.name && server.url);

  return (
    <Box borderColor="border.subtle" borderRadius="$16" p="$24" display="flex" flexDirection="column" gap="$16">
      <Box mb="$16">
        <Header size="medium">
          <Header.Title title="MCP Servers" />
          <Header.Description>Configure Model Context Protocol servers for your agent</Header.Description>
        </Header>
      </Box>

      {!isValid && (
        <Box color="content.subtle" fontSize="$12">
          Please fill in required fields for each server (name and URL).
        </Box>
      )}
      <Box>
        <Button
          round
          variant="outline"
          icon={IconPlus}
          onClick={async () => {
            const current = (getValues('mcpServerSettings') || []) as MCPServerSettings[];
            const emptyServer: MCPServerSettings = {
              name: '',
              url: '',
              transport: 'auto',
              headers: {},
            } as MCPServerSettings;
            const next = [...current, emptyServer];
            setValue('mcpServerSettings', next, { shouldDirty: true, shouldValidate: true });
            await trigger('mcpServerSettings');
          }}
        >
          Add MCP server
        </Button>
      </Box>

      <Box display="flex" flexDirection="column" gap="$16">
        {mcpServerSettings.length === 0 && (
          <Box color="content.subtle" fontSize="$12">
            No MCP servers configured yet.
          </Box>
        )}
        {mcpServerSettings.map((mcpServer, index) => {
          const key = mcpServer.name || String(index);
          return <McpServerItem key={key} index={index} mcpServer={mcpServer} />;
        })}
      </Box>
    </Box>
  );
};
