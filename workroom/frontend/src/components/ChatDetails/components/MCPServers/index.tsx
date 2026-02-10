import { useMemo, useState } from 'react';
import { useFormContext } from 'react-hook-form';
import { Box, Button, Divider, Tooltip, Typography } from '@sema4ai/components';
import { IconMcp, IconPlusSmall, IconStatusError } from '@sema4ai/icons';
import { AgentCard } from '@sema4ai/layouts';
import { useParams } from '@tanstack/react-router';

import { useMcpServersQuery } from '~/queries/mcpServers';
import { FeatureFlag, useFeatureFlag } from '~/hooks';
import { useAgentDetailsQuery } from '~/queries/agents';
import { ConfigurationDialog } from './components/ConfigurationDialog';

import { AgentDetailsSchema } from '../context';

type MCPServer = NonNullable<ReturnType<typeof useAgentDetailsQuery>['data']>['mcp_servers'][number];

type MCPItem = {
  name: string;
  status: MCPServer['status'] | 'unknown';
  actions: MCPServer['actions'];
};

const OfflineMcpServerItem = ({ mcpServer }: { mcpServer: MCPItem }) => (
  <>
    <Box display="flex" alignItems="center" gap="$8" py="$16">
      <IconMcp size="$24" />
      <Box flex="1">
        <Typography variant="body-medium" fontWeight="medium">
          {mcpServer.name}
        </Typography>
      </Box>
      {mcpServer.status === 'unknown' ? null : (
        <Tooltip text={`MCP server status: ${mcpServer.status}`}>
          <IconStatusError color="background.notification" />
        </Tooltip>
      )}
    </Box>
    <Divider />
  </>
);

export const MCPServers = () => {
  const { agentId = '' } = useParams({ strict: false });
  const { data: agentDetails } = useAgentDetailsQuery({ agentId });
  const { data: allMCPServers = [] } = useMcpServersQuery({});
  const { enabled: canConfigureAgents } = useFeatureFlag(FeatureFlag.canConfigureAgents);
  const [isConfigurationOpen, setIsConfigurationOpen] = useState(false);
  const { watch } = useFormContext<AgentDetailsSchema>();

  const activeMCPServerIds = watch('mcp_server_ids');

  const mcpServers = useMemo(() => {
    if ((!agentDetails && !allMCPServers) || !activeMCPServerIds) {
      return [];
    }

    return activeMCPServerIds
      .map<MCPItem | null>((id) => {
        const mcpServer = allMCPServers.find((curr) => curr.mcp_server_id === id);

        if (!mcpServer) {
          return null;
        }

        const mcpDetails = agentDetails?.mcp_servers.find((curr) => curr.name === mcpServer?.name);

        return {
          name: mcpServer.name,
          status: mcpDetails?.status || 'unknown',
          actions: mcpDetails?.actions || [],
        };
      })
      .filter((curr) => curr !== null)
      .sort((a, b) => (a.status === 'online' ? -1 : 1) - (b.status === 'online' ? -1 : 1));
  }, [allMCPServers, activeMCPServerIds, agentDetails]);

  if (!canConfigureAgents && mcpServers.length === 0) {
    return null;
  }

  return (
    <>
      <Box display="flex" flexDirection="column">
        <Box display="flex" justifyContent="space-between" alignItems="center" mb="$4">
          <Box display="flex" alignItems="center" gap="$4">
            <Typography variant="body-medium" fontWeight="bold">
              MCP Servers
            </Typography>
          </Box>
          {canConfigureAgents && (
            <Button
              variant="outline"
              size="small"
              aria-label="Configure MCPs"
              icon={IconPlusSmall}
              round
              onClick={() => setIsConfigurationOpen(true)}
            />
          )}
        </Box>
        {mcpServers.length === 0 && (
          <Typography variant="body-medium" color="content.subtle.light">
            No MCP servers configured yet
          </Typography>
        )}
        {mcpServers.map((mcpServer) => {
          return mcpServer.status === 'online' ? (
            <AgentCard.ActionPackageList.Item
              key={mcpServer.name}
              name={mcpServer.name}
              description={null}
              mcpTools={mcpServer.actions}
              illustration={<IconMcp />}
              version="1.0.0"
            />
          ) : (
            <OfflineMcpServerItem key={mcpServer.name} mcpServer={mcpServer} />
          );
        })}
      </Box>
      {isConfigurationOpen && <ConfigurationDialog onClose={() => setIsConfigurationOpen(false)} />}
    </>
  );
};
