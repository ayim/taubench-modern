import { Typography } from '@sema4ai/components';
import { IconMcp } from '@sema4ai/icons';
import { AgentCard } from '@sema4ai/layouts';
import { MCPServer } from '../index';

export const MCPServerSection = ({ mcpServers }: { mcpServers: MCPServer[] }) => {
  return (
    <>
      <Typography variant="body-medium" fontWeight="bold">
        MCP Servers
      </Typography>
      <AgentCard.ActionPackageList>
        {mcpServers.map((mcpServer) => (
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
    </>
  );
};
