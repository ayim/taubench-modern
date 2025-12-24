import { Box, Button, Header, Select } from '@sema4ai/components';
import { useParams } from '@tanstack/react-router';
import { FC, useState } from 'react';
import { useFormContext } from 'react-hook-form';
import { useQueryClient } from '@tanstack/react-query';
import { AgentDeploymentFormSchema } from '../context';
import { McpServerCard } from './McpServerCard';
import { NewMcpServerDialog } from '@sema4ai/spar-ui';
import { useListMcpServersQuery } from '~/queries/mcpServers';

export const McpServerSection: FC = () => {
  const { tenantId } = useParams({ from: '/tenants/$tenantId/agents/deploy' });
  const queryClient = useQueryClient();
  const { watch, getValues, setValue } = useFormContext<AgentDeploymentFormSchema>();
  const { data: mcpServers = {} } = useListMcpServersQuery({ tenantId });

  const [isNewServerDialogOpen, setIsNewServerDialogOpen] = useState(false);

  const selectedServerIds = watch('mcpServerIds') ?? [];
  const selectedServerIdsSet = new Set(selectedServerIds);

  const availableServers = Object.values(mcpServers)
    .filter((srv) => !selectedServerIdsSet.has(srv.mcp_server_id))
    .map((srv) => ({ value: srv.mcp_server_id, label: srv.name }));

  const selectedServers = selectedServerIds.map((id) => mcpServers[id]).filter(Boolean);

  const handleAddExistingServer = (serverId: string) => {
    const ids = getValues('mcpServerIds') ?? [];
    setValue('mcpServerIds', [...ids, serverId], { shouldDirty: true });
  };

  const handleRemoveServer = (serverId: string) => {
    const ids = (getValues('mcpServerIds') ?? []).filter((id) => id !== serverId);
    setValue('mcpServerIds', ids, { shouldDirty: true });
  };

  const handleNewServerSuccess = async (mcpServer: unknown) => {
    const server = mcpServer as { mcp_server_id: string };
    if (server?.mcp_server_id) {
      // Invalidate the query to fetch the newly created server
      await queryClient.invalidateQueries({ queryKey: ['mcp-servers', tenantId] });
      const ids = getValues('mcpServerIds') ?? [];
      setValue('mcpServerIds', [...ids, server.mcp_server_id], { shouldDirty: true });
    }
    setIsNewServerDialogOpen(false);
  };

  return (
    <>
      <Box borderColor="border.subtle" borderRadius="$16" p="$24" display="flex" flexDirection="column" gap="$16">
        <Box mb="$16">
          <Header size="medium">
            <Header.Title title="MCP Servers" />
            <Header.Description>Configure Model Context Protocol servers for your agent</Header.Description>
          </Header>
        </Box>

        <Box display="flex" gap="$8" alignItems="flex-end" mb="$20">
          {availableServers.length > 0 && (
            <Box style={{ flex: 1 }}>
              <Select
                label="Add existing MCP server"
                placeholder="Choose a server"
                value=""
                items={availableServers}
                onChange={(selectedId) => handleAddExistingServer(selectedId)}
              />
            </Box>
          )}
          <Button round variant="outline" onClick={() => setIsNewServerDialogOpen(true)}>
            Add MCP server
          </Button>
        </Box>

        <Box display="flex" flexDirection="column" gap="$16">
          {selectedServers.length === 0 && (
            <Box color="content.subtle" fontSize="$12">
              No MCP servers configured yet.
            </Box>
          )}
          {selectedServers.map((server) => (
            <McpServerCard
              key={server.mcp_server_id}
              server={server}
              onRemove={() => handleRemoveServer(server.mcp_server_id)}
            />
          ))}
        </Box>
      </Box>

      <NewMcpServerDialog
        open={isNewServerDialogOpen}
        onClose={() => setIsNewServerDialogOpen(false)}
        onSuccess={handleNewServerSuccess}
        serverTypes={['generic_mcp', 'sema4ai_action_server', 'hosted']}
        showStdioTransport
      />
    </>
  );
};
