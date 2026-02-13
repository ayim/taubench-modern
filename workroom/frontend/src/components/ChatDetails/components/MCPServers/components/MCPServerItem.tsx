import { FC, useRef, useState } from 'react';
import { Badge, Box, Button, Tooltip, Transition, Typography } from '@sema4ai/components';
import {
  IconChevronDown,
  IconChevronUp,
  IconLoading,
  IconMcp,
  IconPlusSmall,
  IconStatusCompleted,
} from '@sema4ai/icons';
import { AgentIcon } from '@sema4ai/layouts';
import { styled } from '@sema4ai/theme';

import { useMcpServerCapabilitiesQuery, useMcpServersQuery } from '~/queries/mcpServers';
import { useFormContext } from 'react-hook-form';
import { MCPConfigurationSchema } from './context';

type Props = {
  mcpServer: NonNullable<ReturnType<typeof useMcpServersQuery>['data']>[number];
};

const Toggle = styled(Box)`
  background: none;
`;

export const MCPServerItem: FC<Props> = ({ mcpServer }) => {
  const [isOpen, setIsOpen] = useState(false);
  const { data: capabilities, isLoading: isLoadingCapabilities } = useMcpServerCapabilitiesQuery(
    { mcpServer },
    { enabled: isOpen },
  );

  const { watch, setValue } = useFormContext<MCPConfigurationSchema>();
  const selectedMCPServerIds = watch('mcp_server_ids');

  const active = selectedMCPServerIds?.includes(mcpServer.mcp_server_id);
  const contentRef = useRef<HTMLDivElement>(null);

  const onToggleServer = () => {
    if (active) {
      setValue(
        'mcp_server_ids',
        selectedMCPServerIds?.filter((id) => id !== mcpServer.mcp_server_id),
        { shouldDirty: true },
      );
    } else {
      setValue('mcp_server_ids', [...selectedMCPServerIds, mcpServer.mcp_server_id], { shouldDirty: true });
    }
  };

  const tools = capabilities?.results?.[0]?.tools || [];
  const errors = capabilities?.results?.[0]?.issues || [];

  return (
    <>
      <Box key={mcpServer.mcp_server_id} display="flex" gap="$20">
        {active && (
          <Box pt="$2">
            <Badge
              forwardedAs="button"
              icon={IconStatusCompleted}
              iconColor="content.success"
              aria-description="Active"
              onClick={onToggleServer}
            />
          </Box>
        )}
        {!active && (
          <Box pt="$2">
            <Button
              icon={IconPlusSmall}
              variant="outline"
              size="small"
              round
              aria-label="Add"
              onClick={onToggleServer}
            />
          </Box>
        )}
        <Toggle as="button" display="flex" flex="1" gap="$8" alignItems="center" onClick={() => setIsOpen(!isOpen)}>
          <AgentIcon icon={IconMcp} size="m" variant="brand-secondary" />
          <Typography>{mcpServer.name}</Typography>
          <Box ml="auto">{isOpen ? <IconChevronUp /> : <IconChevronDown />}</Box>
        </Toggle>
      </Box>
      <Box ref={contentRef} pl="$40">
        <Transition.Collapse in={isOpen} nodeRef={contentRef}>
          <Box py="$16" pl="$48">
            {isLoadingCapabilities ? (
              <IconLoading />
            ) : (
              <>
                <Typography mb="$8">MCP URL</Typography>
                <Typography mb="$16" color="content.subtle">
                  {mcpServer.url}
                </Typography>
                <Typography mb="$8">Tools</Typography>
                {tools.map((tool) => (
                  <Tooltip key={tool.name as string} text={tool.description as string}>
                    <Badge label={tool.name as string} variant="secondary" />
                  </Tooltip>
                ))}
                {errors.length > 0 && (
                  <Typography color="content.error" mb="$8">
                    {errors.join('; ')}
                  </Typography>
                )}
              </>
            )}
          </Box>
        </Transition.Collapse>
      </Box>
    </>
  );
};
