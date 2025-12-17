import { Box, Button, Header, Select } from '@sema4ai/components';
import { useLoaderData } from '@tanstack/react-router';
import { FC } from 'react';
import { useFormContext, useFieldArray } from 'react-hook-form';
import { AgentDeploymentFormSchema } from '../context';
import { McpServerItem } from './McpServerItem';
import { apiHeadersToFormEntries, parseTransport } from '~/lib/mcpServersUtils';

export const McpServerSection: FC = () => {
  const { control, watch, getValues, setValue } = useFormContext<AgentDeploymentFormSchema>();
  const { mcpServers } = useLoaderData({ from: '/tenants/$tenantId/agents/deploy' });

  const {
    fields: serverFields,
    append: appendServer,
    remove: removeServer,
  } = useFieldArray({
    control,
    name: 'mcpServerSettings',
  });

  const selectedServerIds = new Set(watch('mcpServerIds') ?? []);

  const availableServers = Object.values(mcpServers)
    .filter((srv) => !selectedServerIds.has(srv.mcp_server_id))
    .map((srv) => ({ value: srv.mcp_server_id, label: srv.name }));

  const handleAddExistingServer = (serverId: string) => {
    const srv = mcpServers[serverId];
    if (!srv) return;

    appendServer({
      name: srv.name,
      type: 'generic_mcp',
      transport: parseTransport(srv.transport),
      url: srv.url ?? undefined,
      headersKV: apiHeadersToFormEntries(srv.headers).entries,
      force_serial_tool_calls: false,
      mcpServerId: srv.mcp_server_id,
    });

    const ids = getValues('mcpServerIds') ?? [];
    setValue('mcpServerIds', [...ids, srv.mcp_server_id], { shouldDirty: true });
  };

  const handleAddNewServer = () => {
    appendServer({
      name: '',
      type: 'generic_mcp',
      transport: 'auto',
      url: undefined,
      headersKV: [],
      force_serial_tool_calls: false,
    });
  };

  const handleRemoveServer = (index: number) => {
    const server = serverFields[index];
    removeServer(index);

    if ('mcpServerId' in server && server.mcpServerId) {
      const ids = (getValues('mcpServerIds') ?? []).filter((id) => id !== server.mcpServerId);
      setValue('mcpServerIds', ids, { shouldDirty: true });
    }
  };

  return (
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
        <Button round variant="outline" onClick={handleAddNewServer}>
          Add MCP server
        </Button>
      </Box>

      <Box display="flex" flexDirection="column" gap="$16">
        {serverFields.length === 0 && (
          <Box color="content.subtle" fontSize="$12">
            No MCP servers configured yet.
          </Box>
        )}
        {serverFields.map((field, index) => (
          <McpServerItem key={field.id} index={index} onRemove={() => handleRemoveServer(index)} />
        ))}
      </Box>
    </Box>
  );
};
