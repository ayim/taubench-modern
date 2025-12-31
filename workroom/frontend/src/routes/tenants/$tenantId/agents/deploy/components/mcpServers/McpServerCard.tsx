import { FC } from 'react';
import { Box, Button, Typography } from '@sema4ai/components';
import { IconTrash } from '@sema4ai/icons';
import { PackageCard } from '@sema4ai/layouts';
import { ListMcpServersResponse } from '~/queries/mcpServers';

type Props = {
  server: ListMcpServersResponse[string];
  onRemove: () => void;
};

export const McpServerCard: FC<Props> = ({ server, onRemove }) => {
  return (
    <PackageCard
      title={
        <Box display="flex" alignItems="center" gap="$8" width="100%">
          <Typography>{server.name}</Typography>
          <Button variant="outline" size="small" icon={IconTrash} aria-label="Remove MCP server" onClick={onRemove}>
            Remove
          </Button>
        </Box>
      }
      description={server.url ?? 'Hosted MCP server'}
      version={null}
    >
      <Box display="flex" gap="$16" flexWrap="wrap">
        <Box>
          <Typography fontSize="$12" color="content.subtle">
            Type
          </Typography>
          <Typography fontSize="$14">
            {server.type === 'sema4ai_action_server' ? 'Sema4 Action Server' : 'Generic MCP'}
          </Typography>
        </Box>
        {!server.is_hosted && (
          <Box>
            <Typography fontSize="$12" color="content.subtle">
              Transport
            </Typography>
            <Typography fontSize="$14">{server.transport}</Typography>
          </Box>
        )}
      </Box>
    </PackageCard>
  );
};
