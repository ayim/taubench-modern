import { Box, Tooltip, Typography } from '@sema4ai/components';
import { IconMcp, IconStatusError } from '@sema4ai/icons';
import { AgentCard } from '@sema4ai/layouts';
import { MCPServer } from '../index';

const OfflineMcpServerItem = ({ mcpServer }: { mcpServer: MCPServer }) => (
  <Box display="flex" alignItems="center" gap="$12" py="$12" px="$16">
    <IconMcp size="$24" color="content.subtle" />
    <Box flex="1">
      <Typography variant="body-medium">{mcpServer.name}</Typography>
    </Box>
    <Tooltip text={`MCP server status: ${mcpServer.status}`}>
      <IconStatusError color="background.notification" />
    </Tooltip>
  </Box>
);

export const MCPServerSection = ({ mcpServers }: { mcpServers: MCPServer[] }) => {
  const onlineServers = mcpServers.filter((s) => s.status === 'online');
  const offlineServers = mcpServers.filter((s) => s.status === 'offline');

  return (
    <>
      <Typography variant="body-medium" fontWeight="bold">
        MCP Servers
      </Typography>
      {onlineServers.length > 0 && (
        <AgentCard.ActionPackageList>
          {onlineServers.map((mcpServer) => (
            <AgentCard.ActionPackageList.Item
              key={mcpServer.name}
              name={mcpServer.name}
              description={null}
              mcpTools={mcpServer.actions}
              illustration={<IconMcp />}
              version="1.0.0"
            />
          ))}
        </AgentCard.ActionPackageList>
      )}
      {offlineServers.map((mcpServer) => (
        <OfflineMcpServerItem key={mcpServer.name} mcpServer={mcpServer} />
      ))}
    </>
  );
};
