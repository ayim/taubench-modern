import { useEffect, useState } from 'react';
import { Box, Button, Link, Typography } from '@sema4ai/components';
import { IconMcp, IconMinusCircle } from '@sema4ai/icons';
import { useFormContext } from 'react-hook-form';

import { useMcpServersQuery } from '~/queries/mcpServers';
import { SelectControlled } from '~/components/form/SelectControlled';
import { NewMcpServerDialog } from '../../MCPServers/MCPServerDialog/NewMcpServerDialog';
import { AgentDeploymentFormSchema, AgentDeploymentFormSection } from '../context';

export const MCPServers: AgentDeploymentFormSection = ({ agentTemplate }) => {
  const [isNewServerDialogOpen, setIsNewServerDialogOpen] = useState(false);
  const { watch, setValue } = useFormContext<AgentDeploymentFormSchema>();
  const { data: mcpServers = [], isLoading } = useMcpServersQuery({});

  const selectedServerIds = watch('mcpServerIds') ?? [];

  const mcpServerItems = mcpServers.map((server) => ({
    value: server.mcp_server_id,
    label: server.name,
  }));

  useEffect(() => {
    if (selectedServerIds.length > 0) {
      return;
    }

    const defaultValues = (agentTemplate.mcp_servers || []).reduce<string[]>((acc, server) => {
      const mcpServerExists = mcpServerItems.find((item) => item.label === server.name);
      if (mcpServerExists) {
        acc.push(mcpServerExists.value);
      }
      return acc;
    }, []);

    if (defaultValues.length > 0) {
      setValue('mcpServerIds', defaultValues);
    }
  }, [mcpServers]);

  const onNewServerClose = (serverId?: string) => {
    if (serverId) {
      setValue('mcpServerIds', [...selectedServerIds, serverId], { shouldDirty: true });
    }
    setIsNewServerDialogOpen(false);
  };

  const onRemoveServer = (index: number) => () => {
    const newServerIds = [...selectedServerIds];
    newServerIds.splice(index, 1);
    setValue('mcpServerIds', newServerIds);
  };

  const availableMcpServerItems = mcpServerItems.filter((curr) => !selectedServerIds.includes(curr.value));

  return (
    <Box display="flex" gap="$18">
      <IconMcp size={24} />
      <Box flex="1">
        <Typography variant="body-large" fontWeight="medium">
          MCP Tools
        </Typography>
        <Typography mb="$24">Select one or more MCP servers to provide the MCP tools to the Agent.</Typography>
        <Box display="flex" flexDirection="column" gap="$16" mb="$8">
          {selectedServerIds.map((mcpServerId, index) => (
            <Box display="flex" alignItems="center" gap="$8" key={mcpServerId}>
              <SelectControlled
                disabled={isLoading}
                name={`mcpServerIds.[${index}]`}
                items={mcpServerItems.filter(
                  (curr) => curr.value === mcpServerId || !selectedServerIds.includes(curr.value),
                )}
              />
              <Button
                icon={IconMinusCircle}
                variant="ghost-subtle"
                size="small"
                onClick={onRemoveServer(index)}
                aria-label="Remove MCP server"
              />
            </Box>
          ))}
          {availableMcpServerItems.length > 0 && (
            <SelectControlled
              disabled={isLoading}
              name={`mcpServerIds.[${selectedServerIds.length}]`}
              items={availableMcpServerItems}
            />
          )}
        </Box>
        <Typography color="content.subtle.light">
          Select one or more MCP servers that provide the MCP tools listed above, or{' '}
          <Link as="button" type="button" onClick={() => setIsNewServerDialogOpen(true)}>
            Create New
          </Link>
        </Typography>
      </Box>
      {isNewServerDialogOpen && <NewMcpServerDialog open onClose={onNewServerClose} serverTypes={['generic_mcp']} />}
    </Box>
  );
};
