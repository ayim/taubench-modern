import { Box, Button, SideNavigation, Tooltip, Typography } from '@sema4ai/components';
import { IconLayoutRight, IconWriteNote } from '@sema4ai/icons';
import { AgentIcon, useSidebarMenu } from '@sema4ai/layouts';
import { styled } from '@sema4ai/theme';
import { FC, ReactNode } from 'react';

import { useNavigate, useParams, useThreadStartingMessage } from '../../hooks';
import { useCreateThread } from '../../hooks/useCreateThread';
import { useAgentQuery } from '../../queries/agents';
import { ThreadSearch } from '../ThreadSearch';
import { AgentContextMenu } from '../Agents';

type Props = {
  children: ReactNode;
};

const ThreadsToggle = styled(Button)<{ $expanded?: boolean }>`
  display: ${({ $expanded }) => ($expanded ? 'none' : 'block')};
  position: relative;
`;

export const Container = styled.header<{ $sidebarExpanded: boolean }>`
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.space.$16};
  height: ${({ theme }) => theme.sizes.$64};
  padding: ${({ theme }) => theme.space.$14} ${({ theme }) => theme.space.$20};
  padding-left: ${({ theme, $sidebarExpanded }) => (!$sidebarExpanded ? theme.space.$64 : theme.space.$20)};
  outline: 1px solid ${({ theme }) => theme.colors.border.primary.color};

  ${({ theme }) => theme.screen.m} {
    height: 52px;
    padding-left: 52px;
  }
`;

export const ThreadHeader: FC<Props> = ({ children }) => {
  const navigate = useNavigate();
  const { agentId } = useParams('/thread/$agentId/$threadId');
  const { triggerProps, triggerRef } = useSidebarMenu('threads-list');
  const { expanded: mainMenuExpanded } = useSidebarMenu('main-menu');
  const { onNewThread, isCreatingThread } = useCreateThread();
  const startingMessage = useThreadStartingMessage({ agentId });

  const { data: agent, isLoading } = useAgentQuery({ agentId });


  const onAgentDelete = () => {
    navigate({ to: '/home', params: {} });
  };

  if (isLoading || !agent) {
    return null;
  }

  return (
    <Container $sidebarExpanded={mainMenuExpanded}>
      <ThreadsToggle
        variant="ghost-subtle"
        icon={IconLayoutRight}
        aria-label="Toggle thread view"
        {...triggerProps}
        ref={triggerRef}
      />
      <Box display="flex" alignItems="center" gap="$12" minWidth={0}>
        <AgentIcon mode="conversational" size="s" identifier={agent.id || ''} />
        <Box maxWidth="100%" overflow="hidden">
          <Typography variant="body-large" fontWeight="medium" $nowrap truncate={1}>
            {agent.name}
          </Typography>
        </Box>
        <AgentContextMenu agent={agent} onAgentDelete={onAgentDelete} />
      </Box>
      <Box display="flex" alignItems="center" gap="$8" ml="auto">
        <Tooltip text="New Thread" placement="bottom">
          <SideNavigation.Item
            icon={IconWriteNote}
            disabled={isCreatingThread}
            round
            aria-label="New Thread"
            onClick={() => onNewThread({ startingMessage })}
          />
        </Tooltip>
        {children}
        <ThreadSearch />
      </Box>
    </Container>
  );
};
