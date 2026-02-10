import { FC, useState } from 'react';
import { Box, Button, Dialog, Progress, ToggleInputButton, Typography } from '@sema4ai/components';
import { IconPlus, IconSearch } from '@sema4ai/icons';
import { dataFuzzySearcher } from '@sema4ai/components/utils';
import { useFormContext } from 'react-hook-form';

import { NewMcpServerDialog } from '~/components/MCPServers';
import { useMcpServersQuery } from '~/queries/mcpServers';
import { MCPServerItem } from './MCPServerItem';

import { AgentDetailsSchema } from '../../context';

type Props = {
  onClose: () => void;
};

type McpServer = NonNullable<ReturnType<typeof useMcpServersQuery>['data']>[number];

export const ConfigurationDialog: FC<Props> = ({ onClose }) => {
  const [isNewServerDialogOpen, setIsNewServerDialogOpen] = useState(false);
  const [search, setSearch] = useState('');
  const { data: mcpServers = [], isLoading } = useMcpServersQuery({});
  const { setValue, watch } = useFormContext<AgentDetailsSchema>();

  const selectedMCPServerIds = watch('mcp_server_ids');

  const onNewServerClose = (serverId?: string) => {
    setIsNewServerDialogOpen(false);
    if (serverId) {
      setValue('mcp_server_ids', [...selectedMCPServerIds, serverId], { shouldDirty: true });
    }
  };

  const filteredMcpServers = search
    ? dataFuzzySearcher<McpServer>({ name: { value: (item) => item.name } }, mcpServers)(search)
    : mcpServers;

  if (isLoading) {
    return <Progress variant="page" />;
  }

  return (
    <>
      <Dialog open size="page" onClose={onClose}>
        <Dialog.Bar />
        <Dialog.Content>
          <Box maxWidth={720} width="100%" mx="auto">
            <Typography variant="display-medium" mb="$8">
              Edit MCP&apos;s for this Agent
            </Typography>
            <Typography variant="body-large" color="content.subtle" mb="$40">
              Select and edit MCP&apos;s for this agent to provide tools to the Agent.
            </Typography>
            <Box display="flex" alignItems="center" gap="$8" mb="$16">
              <Box flex="1">
                <ToggleInputButton
                  round
                  aria-label="Search"
                  iconLeft={IconSearch}
                  value={search}
                  placeholder="Search"
                  buttonVariant="ghost-subtle"
                  onChange={(e) => setSearch(e.target.value)}
                  onClear={() => setSearch('')}
                  isButtonRound
                />
              </Box>
              <Button
                variant="ghost"
                size="small"
                icon={IconPlus}
                round
                aria-label="Add"
                onClick={() => setIsNewServerDialogOpen(true)}
              >
                MCP Server
              </Button>
            </Box>
            <Box display="flex" flexDirection="column" gap="$8">
              {filteredMcpServers.map((mcpServer) => (
                <MCPServerItem key={mcpServer.mcp_server_id} mcpServer={mcpServer} />
              ))}
              {search && filteredMcpServers.length === 0 && (
                <Typography variant="body-medium" px="$24" py="$16" color="content.subtle">
                  No MCP servers found.
                </Typography>
              )}
              {!search && filteredMcpServers.length === 0 && (
                <Typography variant="body-medium" px="$24" py="$16" color="content.subtle">
                  No MCP servers configured yet.
                </Typography>
              )}
            </Box>
          </Box>
        </Dialog.Content>
        <Dialog.Actions>
          <Button variant="primary" type="button" round onClick={onClose}>
            Save
          </Button>
          <Button variant="secondary" type="button" round onClick={onClose}>
            Cancel
          </Button>
        </Dialog.Actions>
      </Dialog>
      {isNewServerDialogOpen && <NewMcpServerDialog open onClose={onNewServerClose} serverTypes={['generic_mcp']} />}
    </>
  );
};
