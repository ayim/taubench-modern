import { Box, Button, Header, Select } from '@sema4ai/components';
import { useLoaderData } from '@tanstack/react-router';
import { FC } from 'react';
import { useFormContext } from 'react-hook-form';

import type { ListMcpServersResponse } from '~/queries/mcpServers';
import { AgentDeploymentFormSchema, MCPServerSettings } from '../context';
import { McpServerItem } from './McpServerItem';

const allowedTransports = ['auto', 'streamable-http', 'sse', 'stdio'] as const;
const toTransport = (value: string): MCPServerSettings['transport'] =>
  (allowedTransports as readonly string[]).includes(value) ? (value as MCPServerSettings['transport']) : 'auto';

export const McpServerSection: FC = () => {
  const { watch, getValues, setValue, trigger } = useFormContext<AgentDeploymentFormSchema>();
  const { mcpServers } = useLoaderData({ from: '/tenants/$tenantId/agents/create' }) as {
    mcpServers: ListMcpServersResponse;
  };
  const mcpServerSettings = watch('mcpServerSettings') || [];

  const isValid = mcpServerSettings.every((server) => server && server.name && server.url);

  const configuredServerItems = (() => {
    const servers = Object.values(mcpServers);
    const selectedIds = (watch('mcpServerIds') || []) as string[];
    return servers
      .filter((srv) => !selectedIds.includes(srv.mcp_server_id))
      .map((srv) => ({ value: srv.mcp_server_id, label: srv.name }));
  })();

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
      <Box display="flex" gap="$8" alignItems="flex-end" mb="$20">
        {configuredServerItems.length > 0 && (
          <Box style={{ flex: 1 }}>
            <Select
              label="Add existing MCP server"
              placeholder={'Choose a server'}
              items={configuredServerItems}
              onChange={async (selectedId) => {
                if (typeof selectedId !== 'string') return;
                const srv = mcpServers[selectedId];
                if (!srv) return;
                const currentRaw = getValues('mcpServerSettings');
                const current = (currentRaw ?? []) as MCPServerSettings[];
                const transport: MCPServerSettings['transport'] = toTransport(srv.transport);
                const configuredEntry = {
                  name: srv.name,
                  type: 'generic_mcp',
                  url: srv.transport === 'stdio' ? null : (srv.url ?? null),
                  transport,
                  headers: {},
                  command: null,
                  args: null,
                  env: null,
                  cwd: null,
                  force_serial_tool_calls: false,
                  mcpServerId: srv.mcp_server_id,
                } satisfies MCPServerSettings;
                const next = [...current, configuredEntry];
                setValue('mcpServerSettings', next, { shouldDirty: true, shouldValidate: true });
                const ids = new Set(getValues('mcpServerIds') ?? []);
                ids.add(srv.mcp_server_id);
                setValue('mcpServerIds', Array.from(ids), { shouldDirty: true, shouldValidate: true });
                await trigger('mcpServerSettings');
              }}
            />
          </Box>
        )}
        <Button
          round
          variant="outline"
          icon={undefined}
          onClick={async () => {
            const currentRaw = getValues('mcpServerSettings');
            const current = currentRaw ?? [];
            const emptyServer = {
              name: '',
              type: 'generic_mcp' as const,
              url: null,
              transport: 'auto',
              headers: {},
              command: null,
              args: null,
              env: null,
              cwd: null,
              force_serial_tool_calls: false,
            } satisfies MCPServerSettings;

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
