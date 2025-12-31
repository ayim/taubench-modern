import { Box, Button, Header, Select } from '@sema4ai/components';
import { useParams } from '@tanstack/react-router';
import { FC, useState } from 'react';
import { useFormContext } from 'react-hook-form';
import { AgentPackageInspectionResponse } from '@sema4ai/spar-ui/queries';
import { AgentDeploymentFormSchema } from '../context';
import { McpServerCard } from './McpServerCard';
import { AgentPackageSecretsSection } from './AgentPackageSecretsSection';
import { NewMcpServerDialog } from '@sema4ai/spar-ui';
import { useListMcpServersQuery } from '~/queries/mcpServers';
import type { McpServerCreateResponse } from '@sema4ai/spar-ui/queries';

export const McpServerSection: FC<{
  agentTemplate: NonNullable<AgentPackageInspectionResponse>;
}> = ({ agentTemplate }) => {
  const { tenantId } = useParams({ from: '/tenants/$tenantId/agents/deploy' });
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

  const handleNewServerSuccess = (mcpServer: McpServerCreateResponse) => {
    const ids = getValues('mcpServerIds') ?? [];
    setValue('mcpServerIds', [...ids, mcpServer.mcp_server_id], { shouldDirty: true });
    setIsNewServerDialogOpen(false);
  };

  return (
    <>
      <AgentPackageSecretsSection agentTemplate={agentTemplate} />

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
